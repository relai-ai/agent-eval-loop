"""Tests for the checkers that setup copies into relai/bin/. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import json
import os
import shutil
import unittest

from helpers import GOOD_TASK_TOML, HARBOR_TEST_VERSION, Repo, container_engine, harbor_job, harbor_trial, trajectory


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()

    def tearDown(self) -> None:
        self.repo.close()


class CheckTaskTest(Base):
    def test_good_task_passes(self):
        task = self.repo.task()
        result = self.repo.run("check_task.py", str(task))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_semantic_criterion_needs_a_judge(self):
        toml = GOOD_TASK_TOML.replace('type = "judge"', 'type = "code"')
        task = self.repo.task(toml=toml)
        result = self.repo.run("check_task.py", str(task))
        self.assertEqual(result.returncode, 1)
        self.assertIn("semantic criterion needs a judge", result.stdout)

    def test_host_variable_template_is_rejected(self):
        toml = GOOD_TASK_TOML.replace("[verifier]", '[verifier.env]\nKEY = "${{OPENAI_API_KEY}}"\n\n[verifier]')
        task = self.repo.task(toml=toml)
        result = self.repo.run("check_task.py", str(task))
        self.assertIn("reads a host variable", result.stdout)

    def test_cache_folder_and_env_file_are_rejected(self):
        task = self.repo.task()
        (task / "environment" / ".ruff_cache" / "x").mkdir(parents=True)
        (task / "environment" / ".ruff_cache" / "x" / "f").write_text("y")
        (task / "environment" / ".env").write_text("A=b\n")
        result = self.repo.run("check_task.py", str(task))
        self.assertEqual(result.returncode, 1)
        self.assertIn(".ruff_cache is a cache or dependency folder", result.stdout)
        self.assertEqual(result.stdout.count(".ruff_cache"), 1, "one error per cache folder")
        self.assertIn("is an env file", result.stdout)

    def test_secret_value_from_env_file_is_found_but_not_printed(self):
        secret = "sk-test-value-1234567890"
        (self.repo.relai / ".env").write_text(f"OPENAI_API_KEY={secret}\n")
        task = self.repo.task()
        (task / "environment" / "config.json").write_text(json.dumps({"key": secret}))
        result = self.repo.run("check_task.py", str(task))
        self.assertIn("contains the value of OPENAI_API_KEY", result.stdout)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_json_secret_diagnostics_include_names_and_labels_but_not_values(self):
        canary = "synthetic-checker-credential-0123456789"
        pattern_canary = "AKIA" + "0" * 16  # Synthetic match for the AWS access-key pattern.
        self.repo.write("relai/.env", f"AUDIT_TEST_KEY={canary}\n")
        task = self.repo.task()
        (task / "environment" / "config.json").write_text(
            json.dumps({"key": canary, "aws_key": pattern_canary}))

        result = self.repo.run("check_task.py", str(task), "--json", "--no-harbor")

        self.assertEqual(result.returncode, 1)
        # The CLI emits a suite report followed by one JSON document per task.
        _, end = json.JSONDecoder().raw_decode(result.stdout)
        report = json.loads(result.stdout[end:])
        self.assertFalse(report["ok"])
        self.assertIn("environment/config.json contains the value of AUDIT_TEST_KEY from relai/.env",
                      report["errors"])
        self.assertIn("environment/config.json contains what looks like a AWS access key", report["errors"])
        for value in (canary, pattern_canary):
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_copy_of_live_file_in_image_inputs_is_rejected(self):
        self.repo.write("src/prompts/system.md", "You are a helpful retail agent.\n")
        self.repo.write("relai/relai.toml", '[target]\nlive_paths = ["src/prompts/**"]\n')
        task = self.repo.task()
        shutil.copy(self.repo.root / "src/prompts/system.md", task / "environment" / "system.md")
        result = self.repo.run("check_task.py", str(task))
        self.assertIn("is a copy of live file src/prompts/system.md", result.stdout)

    def test_separate_verifier_needs_trajectory_artifact(self):
        toml = GOOD_TASK_TOML.replace('artifacts = ["/logs/agent/trajectory.json"]\n', "")
        task = self.repo.task(toml=toml)
        result = self.repo.run("check_task.py", str(task))
        self.assertIn("add '/logs/agent/trajectory.json' to top-level artifacts", result.stdout)

    def test_changed_frozen_test_warns(self):
        task = self.repo.task()
        self.assertEqual(self.repo.run("freeze.py", str(task)).returncode, 0)
        (task / "tests" / "judge.md").write_text("Full marks for anything.\n")
        result = self.repo.run("check_task.py", str(task))
        self.assertIn("changed since it was frozen", result.stdout)

    def test_harborignore_is_rejected(self):
        task = self.repo.task()
        (task / "tests" / ".harborignore").write_text("judge.md\n")
        result = self.repo.run("check_task.py", str(task), "--no-harbor")
        self.assertIn("tests/.harborignore: Harbor leaves the files it matches out", result.stdout)

    def test_copying_live_files_into_harness_image_warns(self):
        self.repo.write("src/prompts/system.md", "You are a helpful retail agent.\n")
        self.repo.write("relai/relai.toml", '[target]\nlive_paths = ["src/prompts/**"]\n')
        self.repo.write("relai/harness/Dockerfile", "FROM python:3.12-slim\nCOPY . /app\n")
        result = self.repo.run("check_task.py", str(self.repo.task()), "--no-harbor")
        self.assertIn("copies '.', which includes live file src/prompts/system.md", result.stdout)

    @unittest.skipUnless(shutil.which("uv"), "needs uv")
    def test_harbor_rejects_what_static_checks_miss(self):
        self.repo.write("relai/relai.toml", f'[harbor]\nversion = "{HARBOR_TEST_VERSION}"\n')
        toml = GOOD_TASK_TOML.replace('environment_mode = "separate"', 'environment_mode = "seperate"')
        result = self.repo.run("check_task.py", str(self.repo.task(toml=toml)))
        self.assertIn("Harbor cannot load it", result.stdout)

    @unittest.skipUnless(container_engine(), "needs a docker- or podman-compatible engine")
    def test_shared_verifier_with_non_executable_test_sh(self):
        toml = GOOD_TASK_TOML.replace('environment_mode = "separate"\n', "")
        task = self.repo.task(toml=toml)
        (task / "tests" / "test.sh").chmod(0o644)
        result = self.repo.run("check_task.py", str(task), "--verifier", "--no-harbor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(container_engine(), "needs a docker- or podman-compatible engine")
    def test_verifier_runs_on_synthetic_trajectories(self):
        task = self.repo.task()
        result = self.repo.run("check_task.py", str(task), "--verifier")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(container_engine(), "needs a docker- or podman-compatible engine")
    def test_verifier_missing_declared_metric_fails(self):
        task = self.repo.task()
        (task / "tests" / "evaluate.py").write_text(
            "import pathlib\npathlib.Path('/logs/verifier/reward.json').write_text('{\"reward\": 1}')\n")
        result = self.repo.run("check_task.py", str(task), "--verifier")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no numeric score for declared evaluator looks-up-order", result.stdout)


class CheckTrajectoryTest(Base):
    def check(self, doc: dict, *args: str):
        path = self.repo.root / "t.json"
        path.write_text(json.dumps(doc))
        return self.repo.run("check_trajectory.py", str(path), "--no-harbor", *args)

    def test_answered_turns_pass(self):
        doc = trajectory([{"source": "user", "message": "a"}, {"source": "agent", "message": "b"},
                          {"source": "user", "message": "c"}, {"source": "agent", "message": "d"}])
        result = self.check(doc, "--turns", "2")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_unanswered_user_step_fails(self):
        doc = trajectory([{"source": "user", "message": "a"}, {"source": "user", "message": "b"},
                          {"source": "agent", "message": "c"}])
        result = self.check(doc)
        self.assertIn("has no agent step after it", result.stdout)

    def test_tool_call_without_result_warns_and_without_id_fails(self):
        doc = trajectory([{"source": "user", "message": "a"},
                          {"source": "agent", "message": "", "tool_calls": [
                              {"tool_call_id": "1", "function_name": "f", "arguments": {}},
                              {"function_name": "g", "arguments": {}}]}])
        result = self.check(doc)
        self.assertIn("has no result in the same step", result.stdout)
        self.assertIn("has no tool_call_id", result.stdout)

    def test_closing_user_message_needs_no_reply(self):
        doc = trajectory([{"source": "agent", "message": "Hi, how can I help?"}, {"source": "user", "message": "a"},
                          {"source": "agent", "message": "b"}, {"source": "user", "message": "###STOP###"}])
        result = self.check(doc)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("the last user step", result.stdout)

    def test_rewritten_history_fails(self):
        earlier = trajectory([{"source": "user", "message": "a"}, {"source": "agent", "message": "b"}])
        later = trajectory([{"source": "user", "message": "a"}, {"source": "agent", "message": "changed"}])
        prev = self.repo.root / "prev.json"
        prev.write_text(json.dumps(earlier))
        result = self.check(later, "--previous", str(prev))
        self.assertIn("not an exact prefix", result.stdout)

    def test_no_sign_of_real_model_warns(self):
        doc = trajectory([{"source": "user", "message": "a"}, {"source": "agent", "message": "b"}])
        doc["agent"].pop("model_name")
        self.assertIn("nothing shows a real model call", self.check(doc).stdout)

    @unittest.skipUnless(shutil.which("uv"), "needs uv")
    def test_harbor_validator_rejects_bad_schema(self):
        doc = trajectory([{"source": "user", "message": "a"}, {"source": "agent", "message": "b", "bogus": 1}])
        path = self.repo.root / "t.json"
        path.write_text(json.dumps(doc))
        self.repo.write("relai/relai.toml", f'[harbor]\nversion = "{HARBOR_TEST_VERSION}"\n')
        result = self.repo.run("check_trajectory.py", str(path))
        self.assertIn("Harbor's ATIF validator rejected it", result.stdout)


class CheckWikiTest(Base):
    def test_malformed_monetary_fragment_errors_without_printing_evidence(self):
        path = self.repo.write("relai/wiki/attachments/refund.json",
                               '{\n  "private-customer": "secret-customer",\n  "amount": 36.13.000000001\n}\n')
        before = path.read_bytes()
        result = self.repo.run("check_wiki.py", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        errors = json.loads(result.stdout)["errors"]
        self.assertEqual(len(errors), 1)
        self.assertIn("wiki/attachments/refund.json:3:18: invalid JSON", errors[0])
        self.assertNotIn("secret-customer", result.stdout + result.stderr)
        self.assertNotIn("36.13", result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_valid_attachment_values_and_aliases_are_not_rewritten(self):
        path = self.repo.write("relai/wiki/attachments/export.json",
                               '{ "amount": 36.13000000000001, "quoted": "36.13", '
                               '"customer_alias": "CUSTOMER_001", "note": "uncertain" }\n')
        before = path.read_bytes()
        result = self.repo.run("check_wiki.py", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["errors"], [])
        self.assertEqual(path.read_bytes(), before)

    def test_nonstandard_json_constants_fail_without_printing_evidence(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                path = self.repo.write("relai/wiki/attachments/constants.json",
                                       '{"private": "secret-customer", "amount": ' + constant + '}')
                before = path.read_bytes()
                result = self.repo.run("check_wiki.py", "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["errors"],
                                 ["wiki/attachments/constants.json: invalid JSON (non-standard numeric constant)"])
                self.assertNotIn("secret-customer", result.stdout + result.stderr)
                self.assertEqual(path.read_bytes(), before)

    def test_quoted_constants_and_large_json_numbers_remain_valid(self):
        path = self.repo.write("relai/wiki/attachments/constants.json",
                               '{"strings": ["NaN", "Infinity", "-Infinity"], "large_number": 1e999}')
        before = path.read_bytes()
        result = self.repo.run("check_wiki.py", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["errors"], [])
        self.assertEqual(path.read_bytes(), before)

    def test_nested_unlinked_json_and_invalid_utf8_are_checked(self):
        self.repo.write("relai/wiki/attachments/deep/unlinked.json", '{"broken": }')
        path = self.repo.write("relai/wiki/attachments/deep/encoding.json", "")
        path.write_bytes(b'{"private": "\xff"}')
        self.repo.write("relai/wiki/attachments/deep/notes.txt", "not JSON")
        self.repo.write("relai/wiki/attachments/deep/stream.jsonl", "not JSON either")
        result = self.repo.run("check_wiki.py", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        errors = json.loads(result.stdout)["errors"]
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("deep/unlinked.json:1:12: invalid JSON" in error for error in errors))
        self.assertTrue(any("deep/encoding.json: invalid UTF-8 at byte 13" in error for error in errors))
        self.assertNotIn("private", result.stdout + result.stderr)

    def test_unreadable_attachment_reports_filename_without_content(self):
        path = self.repo.write("relai/wiki/attachments/private.json", '{"secret": "not-for-output"}')
        path.chmod(0)
        try:
            if os.access(path, os.R_OK):
                self.skipTest("current user can read permission-denied files")
            result = self.repo.run("check_wiki.py", "--json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("wiki/attachments/private.json: cannot read JSON", result.stdout)
            self.assertNotIn("not-for-output", result.stdout + result.stderr)
        finally:
            path.chmod(0o600)

    def test_attachment_symlinks_are_not_followed(self):
        outside = self.repo.write("outside/private.json", '{"secret-outside": }')
        inside = self.repo.write("relai/wiki/attachments/valid.json", "{}")
        root = inside.parent
        try:
            (root / "external.json").symlink_to(outside)
            (root / "external-dir").symlink_to(outside.parent, target_is_directory=True)
            (root / "internal.json").symlink_to(inside)
            (root / "missing.json").symlink_to(outside.parent / "absent.json")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        result = self.repo.run("check_wiki.py", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        errors = json.loads(result.stdout)["errors"]
        self.assertEqual(len(errors), 4)
        for name in ("external.json", "external-dir", "internal.json", "missing.json"):
            self.assertTrue(any(f"attachments/{name}: attachment scan cannot follow a symlink" in e for e in errors))
        self.assertNotIn("invalid JSON", result.stdout)
        self.assertNotIn("secret-outside", result.stdout + result.stderr)

    def test_symlinked_attachment_root_is_not_followed(self):
        outside = self.repo.write("outside/private.json", '{"secret-outside": }')
        root = self.repo.relai / "wiki" / "attachments"
        root.mkdir(parents=True, exist_ok=True)
        root.rmdir()
        try:
            root.symlink_to(outside.parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        result = self.repo.run("check_wiki.py", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["errors"],
                         ["wiki/attachments: attachment scan cannot follow a symlink"])
        self.assertNotIn("secret-outside", result.stdout + result.stderr)

    def test_duplicate_ids_missing_titles_and_dangling_covers(self):
        self.repo.write("relai/wiki/requirements/refunds.md", "# Refunds\nFull refund within 30 days.\n")
        self.repo.write("relai/wiki/risks/refunds.md", "no title\n")
        toml = GOOD_TASK_TOML.replace('behavior =', 'covers = ["refunds", "missing-page"]\nbehavior =')
        self.repo.task(toml=toml)
        result = self.repo.run("check_wiki.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("is also used by", result.stdout)
        self.assertIn("first line must be a '# ' title", result.stdout)
        self.assertIn("covers 'missing-page', which is not a wiki page", result.stdout)
        self.assertNotIn("covers 'refunds'", result.stdout)

    def test_benchmark_row_covers_are_checked(self):
        self.repo.write("relai/wiki/requirements/refunds.md", "# Refunds\nFull refund within 30 days.\n")
        self.repo.write("relai/benchmarks/cases/rows/0/task.toml",
                        '[metadata.relai]\nid = "0"\ncovers = ["no-such-page"]\n')
        result = self.repo.run("check_wiki.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("benchmarks/cases/rows/0/task.toml covers 'no-such-page'", result.stdout)


    def test_local_attachments_warn_without_blocking_and_external_links_are_ignored(self):
        self.repo.write("relai/wiki/attachments/trace.json", "{}")
        self.repo.write("relai/wiki/attachments/trace with spaces.txt", "evidence")
        self.repo.write("relai/wiki/requirements/refunds.md", """# Refunds
[trace](../attachments/trace.json#message-2)
[encoded](../attachments/trace%20with%20spaces.txt)
[angle](<../attachments/trace with spaces.txt>)
[missing](../attachments/missing.json)
[web](https://example.invalid/absent.json)
[malformed-external](https://[broken/absent.json)
[protocol-relative](//[broken/absent.json)
[email](mailto:example@example.invalid)
[section](#policy)
""")
        result = self.repo.run("check_wiki.py", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["errors"], [])
        self.assertEqual(len(data["warnings"]), 1)
        self.assertIn("missing.json", data["warnings"][0])

    def test_missing_markdown_page_still_errors(self):
        self.repo.write("relai/wiki/requirements/refunds.md", "# Refunds\n[missing](absent.md#policy)\n")
        result = self.repo.run("check_wiki.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("link to absent.md#policy does not resolve", result.stdout)


class FreezeTest(Base):
    def test_refreeze_needs_reason_and_keeps_history(self):
        task = self.repo.task()
        self.assertEqual(self.repo.run("freeze.py", str(task)).returncode, 0)
        (task / "tests" / "judge.md").write_text("changed\n")
        refused = self.repo.run("freeze.py", str(task))
        self.assertEqual(refused.returncode, 1)
        self.assertIn("needs --reason", refused.stdout)
        self.assertIn("CHANGED", self.repo.run("freeze.py", "--check").stdout)
        self.assertEqual(self.repo.run("freeze.py", str(task), "--reason", "rubric typo").returncode, 0)
        state = json.loads((self.repo.relai / "frozen.json").read_text())
        self.assertEqual([h["reason"] for h in state["tests"]["tests/orders"]["history"]], ["first freeze", "rubric typo"])

    def test_readme_edits_do_not_unfreeze(self):
        task = self.repo.task()
        self.repo.run("freeze.py", str(task))
        (task / "README.md").write_text("docs\n")
        self.assertIn("tests/orders: frozen", self.repo.run("freeze.py", "--check").stdout)

    def test_check_lists_benchmark_rows(self):
        self.repo.task()
        self.repo.task("row", toml=None)
        row = self.repo.root / "relai/benchmarks/cases/rows/0"
        row.parent.mkdir(parents=True, exist_ok=True)
        (self.repo.root / "relai/tests/row").rename(row)
        out = self.repo.run("freeze.py", "--check").stdout
        self.assertIn("tests/orders: unfrozen", out)
        self.assertIn("benchmarks/cases/rows/0: unfrozen", out)
        self.assertEqual(self.repo.run("freeze.py", str(row)).returncode, 0)
        self.assertIn("benchmarks/cases/rows/0: frozen", self.repo.run("freeze.py", "--check").stdout)

    def test_check_finds_changed_imported_cases(self):
        self.repo.task("imported")
        source = self.repo.relai / "tests/imported"
        case = self.repo.relai / "benchmarks/bx/cases/case-a"
        case.parent.mkdir(parents=True)
        source.rename(case)
        self.assertEqual(self.repo.run("freeze.py", str(case)).returncode, 0)
        (case / "instruction.md").write_text("changed probe")
        result = self.repo.run("freeze.py", "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("benchmarks/bx/cases/case-a: CHANGED", result.stdout)

    def test_same_directory_name_in_two_places_stays_distinct(self):
        for bench in ("refunds", "exchanges"):
            self.repo.task(f"template", toml=None)
            src = self.repo.root / "relai/tests/template"
            dst = self.repo.root / f"relai/benchmarks/{bench}/template"
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
        self.assertEqual(self.repo.run("freeze.py", str(self.repo.root / "relai/benchmarks/refunds/template")).returncode, 0)
        result = self.repo.run("freeze.py", str(self.repo.root / "relai/benchmarks/exchanges/template"))
        self.assertEqual(result.returncode, 0, result.stdout)


class SummarizeTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.task = self.repo.task()
        self.repo.run("freeze.py", str(self.task))

    def test_statuses_stay_apart(self):
        job = harbor_job(self.repo.root / "runs" / "a", "job", 4, errored=1)
        harbor_trial(job, "t1", self.task, {"looks-up-order": 1.0}, feedback={"looks-up-order": "ok"},
                     judges={"explains": {"score": 0.5, "feedback": "partly"}})
        harbor_trial(job, "t2", self.task, {}, feedback={},
                     judges={"explains": {"score": 1.0, "feedback": "ok"}})
        harbor_trial(job, "t3", self.task, {"looks-up-order": 1.0}, feedback={"looks-up-order": "ok"})
        harbor_trial(job, "t4", self.task, None, exception="AgentTimeoutError", with_trajectory=False)
        harbor_trial(job, "t5", self.task, None, exception="RuntimeError",
                     judges={"explains": {"score": 0.0, "feedback": "judged a crashed run"}})
        harbor_trial(job, "t6", self.task, {"looks-up-order": 0.0}, exception="AgentTimeoutError",
                     feedback={"looks-up-order": "timed out"}, judges={"explains": {"score": 0.0, "feedback": "x"}})
        result = self.repo.run("summarize.py", "--details", str(self.repo.root / "runs" / "a"), "--json",
                               str(self.repo.root / "s.json"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads((self.repo.root / "s.json").read_text())["run"]
        self.assertEqual(summary["status_counts"], {"scored": 2, "evaluator error": 1, "judges pending": 1,
                                                    "runtime failure": 2, "unscored": 0, "task not found": 0})
        self.assertAlmostEqual(summary["tests"]["tests/orders"]["mean"], 0.375)
        self.assertIn("scored, but the runner recorded AgentTimeoutError", result.stdout)
        self.assertIn("1 errored trial", result.stdout)

    def test_comparison_and_notice_when_test_changed(self):
        for name, score, checksum in (("base", 0.0, "c1"), ("cand", 1.0, "c1"), ("changed", 1.0, "c2")):
            job = harbor_job(self.repo.root / "runs" / name, "job", 3)
            for i in range(3):
                harbor_trial(job, f"t{i}", self.task, {"looks-up-order": score}, checksum=checksum,
                             feedback={"looks-up-order": "f"}, judges={"explains": {"score": score, "feedback": "f"}})
        ok = self.repo.run("summarize.py", "--details", str(self.repo.root / "runs" / "cand"),
                           "--baseline", str(self.repo.root / "runs" / "base"))
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertIn("| tests/orders | 0.00 | 1.00 | 1.00 |", ok.stdout)
        self.assertIn("higher", ok.stdout)
        self.assertNotIn("improved", ok.stdout)
        changed = self.repo.run("summarize.py", "--details", str(self.repo.root / "runs" / "changed"),
                                "--baseline", str(self.repo.root / "runs" / "base"))
        self.assertEqual(changed.returncode, 0)
        self.assertIn("tests/orders: different test versions between runs", changed.stdout)
        self.assertIn("| tests/orders | 0.00 | 1.00 | 1.00 |", changed.stdout)

    def test_one_attempt_describes_change_without_inference(self):
        for name, score in (("b", 1.0), ("c", 0.0)):
            job = harbor_job(self.repo.root / "runs" / name, "job", 1)
            harbor_trial(job, "t", self.task, {"looks-up-order": score}, feedback={"looks-up-order": "f"},
                         judges={"explains": {"score": score, "feedback": "f"}})
        result = self.repo.run("summarize.py", "--details", str(self.repo.root / "runs" / "c"),
                               "--baseline", str(self.repo.root / "runs" / "b"))
        self.assertIn("lower", result.stdout)
        self.assertIn("does not establish confidence", result.stdout)
        self.assertNotIn("regressed", result.stdout)

    def test_relative_task_path_resolves_from_the_jobs_dir(self):
        runs = self.repo.root / "relai" / "work" / "runs"
        job = harbor_job(runs, "job", 1)
        (job / "config.json").write_text(json.dumps({"jobs_dir": "relai/work/runs"}))
        trial = harbor_trial(job, "t", self.task, {"looks-up-order": 1.0}, feedback={"looks-up-order": "f"},
                             judges={"explains": {"score": 1.0, "feedback": "f"}})
        data = json.loads((trial / "result.json").read_text())
        data["task_id"]["path"] = "relai/tests/orders"
        (trial / "result.json").write_text(json.dumps(data))
        other_cwd = self.repo.root / "relai" / "work"
        result = __import__("subprocess").run(
            [__import__("sys").executable, str(self.repo.relai / "bin" / "summarize.py"), str(runs)],
            capture_output=True, text=True, cwd=other_cwd)
        self.assertIn("Trials: 1 (scored 1)", result.stdout)

    def test_missing_task_is_reported_not_skipped(self):
        job = harbor_job(self.repo.root / "runs" / "m", "job", 1)
        trial = harbor_trial(job, "t", self.task, {"looks-up-order": 1.0})
        data = json.loads((trial / "result.json").read_text())
        data["task_id"]["path"] = "no/such/task"
        (trial / "result.json").write_text(json.dumps(data))
        result = self.repo.run("summarize.py", "--details", str(self.repo.root / "runs" / "m"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("task not found", result.stdout)

    def test_unfrozen_test_is_reported(self):
        other = self.repo.task("unfrozen")
        job = harbor_job(self.repo.root / "runs" / "x", "job", 1)
        harbor_trial(job, "t", other, {"looks-up-order": 1.0}, feedback={"looks-up-order": "f"},
                     judges={"explains": {"score": 1.0, "feedback": "f"}})
        result = self.repo.run("summarize.py", "--details", str(self.repo.root / "runs" / "x"))
        self.assertIn("tests/unfrozen is not frozen", result.stdout)

    def test_unfrozen_smoke_test_in_harness_is_not_reported(self):
        self.repo.task("smoke")
        smoke = self.repo.relai / "harness" / "smoke"
        smoke.parent.mkdir(parents=True, exist_ok=True)
        (self.repo.relai / "tests" / "smoke").rename(smoke)
        job = harbor_job(self.repo.root / "runs" / "s", "job", 1)
        harbor_trial(job, "t", smoke, {"looks-up-order": 1.0}, feedback={"looks-up-order": "f"},
                     judges={"explains": {"score": 1.0, "feedback": "f"}})
        result = self.repo.run("summarize.py", "--details", str(self.repo.root / "runs" / "s"))
        self.assertIn("harness/smoke", result.stdout)
        self.assertNotIn("not frozen", result.stdout)


HARBOR_TOML = """\
[runtime]
env = ["OPENAI_API_KEY"]

[scoring]
pass_mark = 0.8

[harbor]
version = "0.25.0"
agent = "acme_agent:AcmeAgent"
pythonpath = ["relai/harness"]
agent_env = { RELAI_PASS_ENV = "OPENAI_API_KEY" }

[harbor.image]
tag = "acme-evals:deps"
dockerfile = "relai/harness/Dockerfile"
context = "relai/harness"
"""


class CloudBuildTest(Base):
    """Fixed rule 8 and relai.toml [harbor]. Registry lookups are answered here, never by the network."""

    PUBLIC = {"python:3.12-slim", "ghcr.io/astral-sh/uv:0.8.14"}

    def load(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("check_task", self.repo.relai / "bin" / "check_task.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def checker(self, public=PUBLIC):
        module, self.asked = self.load(), []
        module.pullable = lambda image: self.asked.append(image) or (image in public)
        return module

    def check(self, task, **kwargs):
        module = self.checker(**kwargs)
        report = module.Report()
        module.check_static(task, self.repo.relai, report, cloud=True)
        return report

    def check_harbor(self, toml: str):
        self.repo.write("relai/relai.toml", toml)
        module = self.checker()
        report = module.Report()
        module.check_harbor(self.repo.relai, report, cloud=True)
        return report

    def declare_harness(self) -> None:
        self.repo.write("relai/relai.toml", HARBOR_TOML)
        self.repo.write("relai/harness/acme_agent.py", "class AcmeAgent:\n    pass\n")
        self.repo.write("relai/harness/Dockerfile",
                        "FROM python:3.12-slim\nCOPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /usr/local/bin/uv\n")

    def run_main(self, task, module, *extra):
        import contextlib
        import io
        import sys
        from unittest.mock import patch

        output = io.StringIO()
        with patch.object(sys, "argv", ["check_task.py", str(task), "--no-harbor",
                                       "--relai-dir", str(self.repo.relai), *extra]), \
                contextlib.redirect_stdout(output):
            status = module.main()
        return status, output.getvalue()

    def test_default_local_cli_accepts_private_images_without_registry_calls(self):
        self.declare_harness()
        task = self.repo.task()
        self.repo.write("relai/harness/Dockerfile", "FROM registry.internal/team/base:1\n")
        (task / "environment/Dockerfile").write_text(
            "ARG BASE=localhost:5000/team/base:1\nFROM ${BASE} AS build\nFROM acme-evals:deps\n")
        self.repo.write("relai/relai.toml", HARBOR_TOML + '\n[judge]\nmode = "subagent"\n')
        module = self.load()
        def no_registry_calls(image):
            raise AssertionError(f"local check contacted registry for {image}")
        module.pullable = no_registry_calls
        status, output = self.run_main(task, module)
        self.assertEqual(status, 0, output)
        self.assertNotIn("hosted runner has no", output)

    def test_cloud_cli_retains_hosted_builder_restrictions(self):
        self.declare_harness()
        task = self.repo.task()
        (task / "environment/Dockerfile").write_text("FROM localhost:5000/team/base:1\n")
        status, output = self.run_main(task, self.checker(), "--cloud")
        self.assertEqual(status, 1, output)
        self.assertIn("registry on this machine or its network", output)

    def test_local_cli_keeps_evaluator_and_secret_checks(self):
        self.declare_harness()
        task = self.repo.task(toml=GOOD_TASK_TOML.replace('type = "judge"', 'type = "code"'))
        canary = "synthetic-local-secret-value"
        self.repo.write("relai/.env", f"TEST_KEY={canary}\n")
        self.repo.write("relai/tests/orders/leak.txt", canary)
        status, output = self.run_main(task, self.checker())
        self.assertEqual(status, 1, output)
        self.assertIn("semantic criterion needs a judge", output)
        self.assertIn("contains the value of TEST_KEY", output)
        self.assertNotIn(canary, output)

    def test_local_only_from_is_flagged(self):
        task = self.repo.task()
        (task / "environment" / "Dockerfile").write_text("FROM acme-evals:deps\nCOPY scenario.json /app/\n")
        errors = self.check(task).errors
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("environment/Dockerfile: FROM acme-evals:deps: no registry serves this image", errors[0])
        self.assertIn("declare it as the harness image", errors[0])

    def test_declared_harness_image_and_public_images_pass(self):
        self.declare_harness()
        task = self.repo.task()
        (task / "environment" / "Dockerfile").write_text(
            "# Only this test's scenario.\n\nFROM acme-evals:deps\nCOPY scenario.json /app/\n")
        self.assertEqual(self.check(task).errors, [])
        self.assertNotIn("acme-evals:deps", self.asked, "a runner builds the harness; it is never pulled")
        suite = self.check_harbor(HARBOR_TOML)
        self.assertEqual((suite.errors, suite.warnings), ([], []))
        self.assertEqual(sorted(self.asked), sorted(self.PUBLIC), "the harness recipe's own images are checked")

    def test_harness_image_must_be_the_only_and_first_from(self):
        self.declare_harness()
        task = self.repo.task()
        cases = {"ARG VERSION=1\nFROM acme-evals:deps\n": "no other FROM and no instruction before it",
                 "FROM python:3.12-slim AS build\nFROM acme-evals:deps\n": "no other FROM and no instruction before it",
                 "FROM python:3.12-slim\nCOPY --from=acme-evals:deps /app /app\n": "start FROM it instead",
                 "# syntax=docker/dockerfile:1\nFROM acme-evals:deps\n": "parser directives (# syntax=docker/dockerfile:1)"}
        for text, message in cases.items():
            with self.subTest(text=text):
                (task / "environment" / "Dockerfile").write_text(text)
                self.assertIn(message, " ".join(self.check(task).errors))

    def test_heredoc_bodies_are_not_instructions(self):
        self.declare_harness()
        task = self.repo.task()
        (task / "environment" / "Dockerfile").write_text(
            "﻿FROM acme-evals:deps\nRUN <<EOF python3\nfrom pathlib import Path\nEOF\n"
            "COPY <<-'PY' /app/x.py\n\tfrom os import path\n\tPY\nRUN --mount=type=bind,from=acme-tools:local,target=/t true\n")
        errors = self.check(task).errors
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("RUN --mount from=acme-tools:local: no registry serves", errors[0])
        self.assertNotIn("pathlib", self.asked)

    def test_build_arguments_pinned_platforms_and_local_registries_are_flagged(self):
        task = self.repo.task()
        cases = {"ARG BASE=python:3.12-slim\nFROM ${BASE}\n": "reads a build argument",
                 "FROM localhost:5000/acme:1\n": "a registry on this machine or its network (localhost:5000)",
                 "FROM 192.168.1.5:5000/acme:1\n": "its network (192.168.1.5:5000)",
                 "FROM [::1]:5000/acme:1\n": "its network ([::1]:5000)",
                 "FROM registry.localhost/acme:1\n": "its network (registry.localhost)"}
        for text, message in cases.items():
            with self.subTest(text=text):
                (task / "environment" / "Dockerfile").write_text(text)
                self.assertIn(message, " ".join(self.check(task).errors))
        (task / "environment" / "Dockerfile").write_text(
            "FROM --platform=$BUILDPLATFORM python:3.12-slim AS build\nRUN echo hi > /x\n"
            "FROM python:3.12-slim\nCOPY --from=build /x /x\nCOPY --from=0 /x /y\n")
        report = self.check(task)
        self.assertEqual(report.errors, [])
        self.assertNotIn("pins --platform", " ".join(report.warnings))
        for platform in ("linux/amd64", "linux/arm64"):
            with self.subTest(platform=platform):
                (task / "environment" / "Dockerfile").write_text(f"FROM --platform={platform} python:3.12-slim\n")
                report = self.check(task)
                self.assertEqual(report.errors, [])
                self.assertIn(f"pins --platform={platform}", " ".join(report.warnings))

    def test_copy_from_a_local_only_image_is_flagged(self):
        task = self.repo.task()
        (task / "tests" / "Dockerfile").write_text(
            "FROM python:3.12-slim\nCOPY --from=acme-tools:local \\\n    /bin/tool /usr/local/bin/\nCOPY . /tests/\n")
        errors = self.check(task).errors
        self.assertTrue(any(e.startswith("tests/Dockerfile: COPY --from=acme-tools:local: no registry serves")
                            for e in errors), errors)

    def test_docker_image_cannot_be_the_harness(self):
        self.declare_harness()
        toml = GOOD_TASK_TOML.replace("[verifier]", '[environment]\ndocker_image = "acme-evals:deps"\n\n[verifier]')
        errors = self.check(self.repo.task(toml=toml)).errors
        self.assertIn("Harbor pulls docker_image from a registry and never builds it", " ".join(errors))

    def test_unreachable_registry_is_a_note_not_an_error(self):
        task = self.repo.task()
        module = self.load()
        module.pullable = lambda image: None
        report = module.Report()
        module.check_static(task, self.repo.relai, report, cloud=True)
        self.assertEqual(report.errors, [])
        self.assertIn("FROM python:3.12-slim: its registry could not be reached", " ".join(report.notes))

    def test_registry_is_asked_anonymously_with_a_token_from_its_challenge(self):
        import io
        import urllib.error

        realm = {"registry.example.io": "https://auth.example.io/token", "basic.example.io": None,
                 "busy.example.io": "https://busy.example.io/token", "plain.example.io": "http://plain.example.io/t"}
        seen = []

        def registry_open(request, timeout):
            url = request if isinstance(request, str) else request.full_url
            seen.append(url)
            host = url.split("/")[2]
            if host == "auth.example.io":
                return io.BytesIO(json.dumps({"token": "anon"}).encode())
            if host == "busy.example.io" and "/token" in url:
                raise urllib.error.HTTPError(url, 503, "Busy", {}, None)
            if request.get_header("Authorization") != "Bearer anon":
                challenge = f'Bearer realm="{realm[host]}",service="{host}"' if realm[host] else 'Basic realm="x"'
                raise urllib.error.HTTPError(url, 401, "Unauthorized", {"WWW-Authenticate": challenge}, None)
            if "/v2/acme/public/manifests/1" not in url:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            response = io.BytesIO()
            response.status = 200
            return response

        module = self.load()
        module.registry_open = registry_open
        self.assertTrue(module.pullable("registry.example.io/acme/public:1"))
        self.assertFalse(module.pullable("registry.example.io/acme/built-here:1"))
        self.assertFalse(module.pullable("basic.example.io/acme/public:1"), "credentials required")
        self.assertIsNone(module.pullable("busy.example.io/acme/public:1"), "a busy token service is not a refusal")
        self.assertIsNone(module.pullable("plain.example.io/acme/public:1"), "only an https realm is asked")
        self.assertIn("https://auth.example.io/token?service=registry.example.io&scope=repository%3Aacme%2Fpublic%3Apull",
                      seen)
        self.assertNotIn("http://plain.example.io/t", " ".join(seen))
        self.assertEqual(module.image_reference("python:3.12-slim"), ("docker.io", "library/python", "3.12-slim"))
        self.assertEqual(module.image_reference("localhost:5000/a/b@sha256:ab"), ("localhost:5000", "a/b", "sha256:ab"))

    def test_subagent_judges_are_flagged_for_a_hosted_runner(self):
        self.declare_harness()
        judged_task = self.repo.task()  # GOOD_TASK_TOML declares a judge evaluator
        code_only = self.repo.task("codes", toml=GOOD_TASK_TOML.split("[[metadata.relai.evaluators]]\nid = \"explains\"")[0])
        module = self.load()
        self.assertTrue(module.has_judges([code_only, judged_task]))
        self.assertFalse(module.has_judges([code_only]))
        for mode, judged, warned in (("subagent", True, True), ("subagent", False, False), ("api", True, False)):
            with self.subTest(mode=mode, judged=judged):
                self.repo.write("relai/relai.toml", HARBOR_TOML + f'\n[judge]\nmode = "{mode}"\n')
                module = self.checker()
                report = module.Report()
                module.check_harbor(self.repo.relai, report, judged=judged, cloud=True)
                self.assertEqual(any('[judge].mode is "subagent"' in w for w in report.warnings), warned, report.warnings)
        self.repo.write("relai/relai.toml", "[judge]\nmode = \"subagent\"\n")
        module = self.checker()
        report = module.Report()
        module.check_harbor(self.repo.relai, report, judged=True, cloud=True)
        self.assertNotIn('[judge].mode is "subagent"', " ".join(report.warnings), "only a suite with [harbor] is warned")

    def test_harbor_table_contract(self):
        self.declare_harness()
        missing = self.check_harbor(HARBOR_TOML.replace("pass_mark = 0.8\n", "")
                                    .replace("acme_agent:AcmeAgent", "other_agent:Agent")
                                    .replace("RELAI_PASS_ENV", "OPENAI_API_KEY")
                                    .replace("relai/harness/Dockerfile", "relai/harness/Containerfile"))
        errors = " ".join(missing.errors)
        self.assertIn("[scoring].pass_mark is not set yet", " ".join(missing.warnings))
        self.assertNotIn("pass_mark", errors)
        for message in ("no other_agent.py under any",
                        "sets OPENAI_API_KEY, a secret named in [runtime].env", "is not a file under the repository root"):
            self.assertIn(message, errors)
        self.assertIn("must be a number from 0 to 1",
                      " ".join(self.check_harbor(HARBOR_TOML.replace("0.8", "80")).errors))
        self.assertIn("no [harbor] table", " ".join(self.check_harbor("[target]\nname = 'x'\n").warnings))
        for version in ('', 'version = "latest"\n', 'version = ">=0.25"\n'):
            with self.subTest(version=version):
                unpinned = self.check_harbor(HARBOR_TOML.replace('version = "0.25.0"\n', version))
                self.assertIn("[harbor].version must be the exact Harbor release", " ".join(unpinned.errors))
        outside = self.check_harbor(HARBOR_TOML.replace('context = "relai/harness"', 'context = ".."')
                                    .replace('["relai/harness"]', '["relai/harness", "/tmp"]'))
        self.assertIn("[harbor.image].context '..' is not a directory under the repository root", outside.errors)
        self.assertIn("[harbor].pythonpath '/tmp' is not a directory under the repository root", outside.errors)
        odd = self.check_harbor(HARBOR_TOML.replace('env = ["OPENAI_API_KEY"]', 'env = [{ name = "X" }]'))
        self.assertEqual(odd.errors, [])
        (self.repo.relai / ".env").write_text("OPENAI_API_KEY=sk-test-value-1234567890\n")
        leaked = self.check_harbor(HARBOR_TOML.replace('"OPENAI_API_KEY" }', '"sk-test-value-1234567890" }'))
        self.assertIn("relai.toml contains the value of OPENAI_API_KEY from relai/.env", leaked.errors)
        self.repo.write("relai/harness/node_modules/x/index.js", "")
        self.assertIn("add Dockerfile.dockerignore beside the Dockerfile",
                      " ".join(self.check_harbor(HARBOR_TOML).warnings))


class TemplateContentsTest(unittest.TestCase):
    def test_template_ships_only_the_shared_checkers(self):
        from helpers import TEMPLATE
        shipped = sorted(p.name for p in (TEMPLATE / "bin").iterdir() if p.name != "__pycache__")
        self.assertEqual(shipped, ["_common.py", "benchmark.py", "check_task.py", "check_trajectory.py",
                                   "check_wiki.py", "freeze.py", "summarize.py"])


class SplitTest(unittest.TestCase):
    def test_split_must_be_development_or_held_out(self):
        repo = Repo()
        try:
            for value, ok in (("held-out", True), ("training", False)):
                toml = GOOD_TASK_TOML.replace("[metadata.relai]\nid = \"{id}\"",
                                              f"[metadata.relai]\nid = \"{{id}}\"\nsplit = \"{value}\"")
                task = repo.task(f"t-{value}", toml)
                out = repo.run("check_task.py", str(task), "--no-harbor").stdout
                self.assertEqual("split must be" not in out, ok, out)
        finally:
            repo.close()


if __name__ == "__main__":
    unittest.main()
