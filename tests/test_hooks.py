"""Tests for the plugin's coding-agent hooks. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest

from helpers import PLUGIN, Repo

HOOK = PLUGIN / "hooks" / "relai_hook.py"


class HookBase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()

    def tearDown(self) -> None:
        self.repo.close()

    def hook(self, name: str, file_path, tool: str = "Edit", raw: str | None = None, host: str | None = None,
             tool_input: dict | None = None, python: str = sys.executable) -> dict | None:
        event = {"hook_event_name": "PreToolUse" if name == "guard-frozen" else "PostToolUse",
                 "cwd": str(self.repo.root), "tool_name": tool,
                 "tool_input": tool_input if tool_input is not None else {"file_path": str(file_path)}}
        command = [python, str(HOOK), name, *(["--host", host] if host else [])]
        result = subprocess.run(command, input=raw if raw is not None else json.dumps(event),
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None


class GuardFrozenTest(HookBase):
    def test_asks_before_editing_a_frozen_test(self):
        task = self.repo.task()
        self.assertEqual(self.repo.run("freeze.py", str(task)).returncode, 0)
        out = self.hook("guard-frozen", task / "tests" / "evaluate.py")["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("changes a frozen test: tests/orders", out["permissionDecisionReason"])
        self.assertIn("freeze.py --reason", out["additionalContext"])

    def test_new_file_in_a_frozen_test_and_relative_paths(self):
        task = self.repo.task()
        self.repo.run("freeze.py", str(task))
        self.assertIsNotNone(self.hook("guard-frozen", task / "tests" / "new_check.py", tool="Write"))
        self.assertIsNotNone(self.hook("guard-frozen", "relai/tests/orders/task.toml"))

    def test_silent_for_unfrozen_tests_readmes_and_other_files(self):
        task = self.repo.task()
        self.assertIsNone(self.hook("guard-frozen", task / "task.toml"))  # not frozen yet
        self.repo.run("freeze.py", str(task))
        self.assertIsNone(self.hook("guard-frozen", task / "README.md"))  # outside the digest
        self.assertIsNone(self.hook("guard-frozen", self.repo.relai / "decisions.md"))
        self.assertIsNone(self.hook("guard-frozen", self.repo.root / "src" / "agent.py"))
        self.assertIsNone(self.hook("guard-frozen", task / "task.toml", tool="Read"))

    def test_an_open_repair_stops_asking_until_the_test_is_refrozen(self):
        task = self.repo.task()
        self.assertEqual(self.repo.run("freeze.py", str(task)).returncode, 0)
        refused = self.repo.run("freeze.py", str(task), "--begin-repair")
        self.assertNotEqual(refused.returncode, 0, "a repair needs a reason")
        opened = self.repo.run("freeze.py", str(task), "--begin-repair", "--reason", "rubric typo")
        self.assertEqual(opened.returncode, 0, opened.stderr)
        self.assertIn("repair open", self.repo.run("freeze.py", "--check").stdout)
        out = self.hook("guard-frozen", task / "tests" / "evaluate.py")["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", out)
        self.assertIn("open repair", out["additionalContext"])
        (task / "tests" / "evaluate.py").write_text((task / "tests" / "evaluate.py").read_text() + "\n# repaired\n")
        self.assertEqual(self.repo.run("freeze.py", str(task), "--reason", "rubric typo").returncode, 0)
        out = self.hook("guard-frozen", task / "tests" / "evaluate.py")["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "ask", "re-freezing closes the repair")
        self.assertIn("--begin-repair", out["permissionDecisionReason"])

    def test_frozen_benchmark_case(self):
        case = self.repo.relai / "benchmarks" / "bench" / "cases" / "c1"
        self.repo.write("relai/benchmarks/bench/cases/c1/task.toml", "[task]\nname = \"c1\"\n")
        self.assertEqual(self.repo.run("freeze.py", str(case)).returncode, 0)
        out = self.hook("guard-frozen", case / "task.toml")
        self.assertIn("benchmarks/bench/cases/c1", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_fails_open_on_bad_input(self):
        self.assertIsNone(self.hook("guard-frozen", "", raw="not json"))
        (self.repo.relai / "frozen.json").write_text("{broken")
        self.assertIsNone(self.hook("guard-frozen", self.repo.relai / "tests" / "orders" / "task.toml"))


def older_python() -> str | None:
    """A python3 older than 3.11 on this machine (such as macOS's /usr/bin/python3), if any."""
    for candidate in ("/usr/bin/python3", shutil.which("python3.9"), shutil.which("python3.10")):
        if not candidate:
            continue
        try:
            out = subprocess.run([candidate, "-c", "import sys; print(sys.version_info >= (3, 8) and sys.version_info < (3, 11))"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
        except OSError:
            continue
        if out == "True":
            return candidate
    return None


class OlderPythonTest(HookBase):
    def setUp(self) -> None:
        super().setUp()
        self.python = older_python()
        if not self.python:
            self.skipTest("no python3 older than 3.11 on this machine")

    def test_frozen_tests_are_still_guarded(self):
        task = self.repo.task()
        self.assertEqual(self.repo.run("freeze.py", str(task)).returncode, 0)
        out = self.hook("guard-frozen", task / "tests" / "evaluate.py", python=self.python)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_check_edit_says_once_that_checks_cannot_run(self):
        task = self.repo.task()
        first = self.hook("check-edit", task / "task.toml", python=self.python)
        self.assertIn("need Python 3.11+", first["systemMessage"])
        self.assertIn("need Python 3.11+", first["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.hook("check-edit", task / "task.toml", python=self.python), "shown once")
        self.assertIsNone(self.hook("check-edit", self.repo.write("src/agent.py", "x = 1\n"), python=self.python))


class CheckEditTest(HookBase):
    def test_silent_when_the_task_passes(self):
        task = self.repo.task()
        self.assertIsNone(self.hook("check-edit", task / "tests" / "evaluate.py"))

    def test_reports_task_problems(self):
        task = self.repo.task()
        (task / "task.toml").write_text((task / "task.toml").read_text().replace('type = "judge"', 'type = "code"'))
        out = self.hook("check-edit", task / "task.toml")["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PostToolUse")
        self.assertIn("relai/bin/check_task.py relai/tests/orders --no-harbor", out["additionalContext"])
        self.assertIn("semantic criterion needs a judge", out["additionalContext"])

    def test_reports_wiki_problems(self):
        page = self.repo.write("relai/wiki/requirements/Bad_Id.md", "no title\n")
        out = self.hook("check-edit", page, tool="Write")["hookSpecificOutput"]
        self.assertIn("relai/bin/check_wiki.py", out["additionalContext"])

    def test_task_toml_edit_checks_cited_wiki_ids(self):
        task = self.repo.task()
        toml = (task / "task.toml").read_text().replace('id = "orders"', 'id = "orders"\ncovers = ["no-such-page"]', 1)
        (task / "task.toml").write_text(toml)
        out = self.hook("check-edit", task / "task.toml")["hookSpecificOutput"]
        self.assertIn("check_wiki.py", out["additionalContext"])
        self.assertIn("no-such-page", out["additionalContext"])

    def test_problems_are_not_blamed_on_the_edit_and_timeouts_are_reported(self):
        task = self.repo.task()
        (task / "task.toml").write_text((task / "task.toml").read_text().replace('type = "judge"', 'type = "code"'))
        context = self.hook("check-edit", task / "task.toml")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("may predate this edit", context)
        sys.path.insert(0, str(HOOK.parent))
        try:
            import relai_hook
        finally:
            sys.path.pop(0)
        self.repo.write("relai/bin/slow.py", "import time\ntime.sleep(5)\n")
        original = relai_hook.CHECK_TIMEOUT_SEC
        relai_hook.CHECK_TIMEOUT_SEC = 0.5
        try:
            report = relai_hook.run_checker(self.repo.relai, "slow.py")
        finally:
            relai_hook.CHECK_TIMEOUT_SEC = original
        self.assertIn("did not finish", report)

    def test_silent_outside_relai(self):
        path = self.repo.write("src/agent.py", "x = 1\n")
        self.assertIsNone(self.hook("check-edit", path))


def patch(*headers: str) -> dict:
    body = "\n".join(f"*** {h}\n+x" for h in headers)
    return {"command": f"*** Begin Patch\n{body}\n*** End Patch\n"}


class CodexTest(HookBase):
    def test_warns_without_asking_when_a_patch_changes_a_frozen_test(self):
        task = self.repo.task()
        self.repo.run("freeze.py", str(task))
        out = self.hook("guard-frozen", None, tool="apply_patch", host="codex",
                        tool_input=patch("Update File: src/agent.py", "Update File: relai/tests/orders/task.toml"))
        out = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", out)  # Codex runs the tool anyway on "ask"
        self.assertIn("RELAI warning", out["additionalContext"])
        self.assertIn("tests/orders", out["additionalContext"])

    def test_silent_for_patches_outside_frozen_tests(self):
        task = self.repo.task()
        self.repo.run("freeze.py", str(task))
        self.assertIsNone(self.hook("guard-frozen", None, tool="apply_patch", host="codex",
                                    tool_input=patch("Add File: src/new.py", "Update File: relai/tests/orders/README.md")))

    def test_patch_paths_run_the_checkers(self):
        task = self.repo.task()
        (task / "task.toml").write_text((task / "task.toml").read_text().replace('type = "judge"', 'type = "code"'))
        self.repo.write("relai/wiki/requirements/Bad_Id.md", "no title\n")
        out = self.hook("check-edit", None, tool="apply_patch", host="codex",
                        tool_input=patch("Update File: relai/tests/orders/task.toml",
                                         "Add File: relai/wiki/requirements/Bad_Id.md"))
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("semantic criterion needs a judge", context)
        self.assertEqual(context.count("check_wiki.py` reported"), 1)


class HookRegistrationTest(unittest.TestCase):
    def commands(self, name: str) -> list[str]:
        config = json.loads((PLUGIN / "hooks" / name).read_text())
        return [h["command"] for groups in config["hooks"].values() for group in groups for h in group["hooks"]]

    def test_claude_hooks_run_the_hook_script(self):
        commands = self.commands("hooks.json")
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/relai_hook.py", command)
            self.assertIn(command.split()[-1], ("guard-frozen", "check-edit"))

    def test_codex_manifest_points_at_codex_hooks(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual(manifest["hooks"], "./hooks/codex-hooks.json")
        commands = self.commands("codex-hooks.json")
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertIn("${PLUGIN_ROOT}/hooks/relai_hook.py", command)
            self.assertTrue(command.endswith("--host codex"))


if __name__ == "__main__":
    unittest.main()
