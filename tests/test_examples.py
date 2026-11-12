"""Tests for the example scripts in examples/: launcher, judge, evaluator helper and trace triage.
Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import EXAMPLES, TEMPLATE, Repo, harbor_trial, trajectory


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(TEMPLATE / "bin"))  # examples are copied beside _common.py
    spec.loader.exec_module(module)
    return module


ADAPTER = """\
import json, os, sys
path = os.environ["RELAI_TRAJECTORY_PATH"]
steps = []
for line in sys.stdin:
    request = json.loads(line)
    steps += [{"step_id": len(steps) + 1, "source": "user", "message": request["message"]},
              {"step_id": len(steps) + 2, "source": "agent", "message": "echo: " + request["message"]}]
    if os.environ.get("SKIP_RECORDING") != "1":
        with open(path, "w") as handle:
            json.dump({"schema_version": "ATIF-v1.7", "agent": {"name": "a", "version": "1"}, "steps": steps}, handle)
    if os.environ.get("RELAI_USER_SIM_KEY"):
        print("leaked", file=sys.stderr)
    print(json.dumps({"reply": "echo: " + request["message"]}), flush=True)
"""


class LauncherTest(unittest.TestCase):
    def run_launcher(self, env_extra: dict, scenario=None) -> tuple[subprocess.CompletedProcess, Path]:
        tmp = Path(tempfile.mkdtemp(prefix="relai-launcher-"))
        (tmp / "adapter.py").write_text(ADAPTER)
        (tmp / "scenario.json").write_text(scenario if isinstance(scenario, str) else
                                           json.dumps(scenario or {"turns": ["first", "second"]}))
        traj = tmp / "trajectory.json"
        result = subprocess.run(
            [sys.executable, str(EXAMPLES / "launcher.py"), "--scenario", str(tmp / "scenario.json"),
             "--trajectory", str(traj), "--adapter", f"{sys.executable} {tmp / 'adapter.py'}"],
            capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", **env_extra}, timeout=60)
        return result, traj

    def test_fixed_turns_drive_the_adapter_and_hide_the_sim_key(self):
        result, traj = self.run_launcher({"RELAI_USER_SIM_KEY": "secret-key-value"})
        self.assertEqual(result.returncode, 0, result.stderr)
        steps = json.loads(traj.read_text())["steps"]
        self.assertEqual([s["message"] for s in steps], ["first", "echo: first", "second", "echo: second"])
        self.assertNotIn("leaked", result.stderr)

    def test_configuration_problems_are_named_without_a_traceback(self):
        user = {"user": {"instructions": "be a customer", "model": "anthropic:some-model"}}
        cases = [({}, "not json", "cannot read the scenario file"),
                 ({}, {"user": {"instructions": "be a customer"}}, 'needs "model"'),
                 ({}, user, "RELAI_USER_SIM_KEY")]
        for env, scenario, message in cases:
            with self.subTest(message=message):
                result, _ = self.run_launcher(env, scenario)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_recording_is_reported(self):
        result, _ = self.run_launcher({"SKIP_RECORDING": "1"})
        self.assertEqual(result.returncode, 4)
        self.assertIn("no readable trajectory", result.stderr)


class JudgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()
        self.judge = load("judge")
        self.task = self.repo.task()
        self.ev = {"id": "explains", "type": "judge", "rubric": "tests/judge.md", "criterion": "c",
                   "min_score": 0.0, "max_score": 1.0}
        self.repo.write("relai/.env", "ANTHROPIC_API_KEY=sk-ant-test-0123456789abcdefghij\n")
        self.repo.write("relai/relai.toml", '[judge]\nmodel = "synthetic"\n')

    def tearDown(self) -> None:
        self.repo.close()

    def fake(self, response: dict):
        calls = []

        def post(url, headers, body):
            calls.append((url, headers, body))
            return response
        self.judge.post = post
        return calls

    def test_a_missing_model_is_an_error_not_a_silent_default(self):
        calls = self.fake({})
        traj = trajectory([{"source": "user", "message": "hi"}, {"source": "agent", "message": "ok"}])
        for config in ({}, {"provider": "openai"}):
            with self.subTest(config=config), self.assertRaises(SystemExit) as raised:
                self.judge.judge_one(config, self.repo.relai, self.task, self.ev, traj, {})
            self.assertIn("there is no default", str(raised.exception))
        self.assertEqual(calls, [])

    def test_anthropic_request_shape_and_valid_score(self):
        calls = self.fake({"stop_reason": "end_turn", "model": "claude-opus-5-5",
                           "content": [{"type": "thinking", "thinking": ""},
                                       {"type": "text", "text": '{"score": 0.5, "feedback": "half"}'}]})
        traj = trajectory([{"source": "user", "message": "token sk-ant-test-0123456789abcdefghij"},
                           {"source": "agent", "message": "ok"}])
        secrets = {"ANTHROPIC_API_KEY": "sk-ant-test-0123456789abcdefghij"}
        result = self.judge.judge_one({"model": "claude-opus-5-5"}, self.repo.relai, self.task, self.ev, traj, secrets)
        self.assertEqual(result["score"], 0.5)
        url, headers, body = calls[0]
        self.assertIn("anthropic.com", url)
        self.assertEqual(body["model"], "claude-opus-5-5")
        self.assertEqual(body["fallbacks"], "default")
        self.assertEqual(body["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("tool_choice", body)
        self.assertNotIn("temperature", body)
        self.assertNotIn("sk-ant-test-0123456789abcdefghij", body["messages"][0]["content"])

    def test_out_of_bounds_score_and_refusal_are_errors(self):
        self.fake({"stop_reason": "end_turn", "content": [{"type": "text", "text": '{"score": 3, "feedback": "x"}'}]})
        self.assertIn("outside", self.judge.judge_one({"model": "synthetic"}, self.repo.relai, self.task, self.ev, trajectory([]), {})["error"])
        self.fake({"stop_reason": "refusal", "content": []})
        self.assertIn("declined", self.judge.judge_one({"model": "synthetic"}, self.repo.relai, self.task, self.ev, trajectory([]), {})["error"])

    def test_invalid_verdicts_retain_usage_and_retry_history(self):
        run = self.repo.relai / "work/runs/synthetic"
        trial = harbor_trial(run, "t1", self.task, {"looks-up-order": 1})
        responses = iter([
            {"score": 3, "feedback": "out of bounds"},
            {"score": 1, "feedback": ""},
            {"score": 1, "feedback": "valid"},
        ])
        calls = []
        def post(url, headers, body):
            verdict = next(responses)
            calls.append(body)
            return {"model": "synthetic-served", "stop_reason": "end_turn",
                    "usage": {"input_tokens": 100, "cost": 0.02},
                    "content": [{"type": "text", "text": json.dumps(verdict)}]}
        self.judge.post = post
        argv = ["judge.py", str(run), "--relai-dir", str(self.repo.relai)]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.judge.main(), 1)
            self.assertEqual(self.judge.main(), 1)
            self.assertEqual(self.judge.main(), 0)
            self.assertEqual(self.judge.main(), 0, "completed scores are still skipped")
        out = trial / "judges/explains.json"
        history = [json.loads(line) for line in out.with_suffix(".attempts.jsonl").read_text().splitlines()]
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(history), 3)
        self.assertIn("outside", history[0]["error"])
        self.assertEqual(history[1]["error"], "judge returned no feedback")
        self.assertEqual(history[2]["score"], 1)
        self.assertEqual(json.loads(out.read_text()), history[-1])
        self.assertAlmostEqual(sum(attempt["cost_usd"] for attempt in history), 0.06)
        for attempt in history:
            self.assertEqual(attempt["usage"]["input_tokens"], 100)
            self.assertEqual(attempt["model"], "synthetic-served")
            self.assertTrue(attempt["judged_at"])

    def test_retry_keeps_legacy_result_and_force_appends_one_attempt(self):
        run = self.repo.relai / "work/runs/synthetic"
        trial = harbor_trial(run, "t1", self.task, {"looks-up-order": 1})
        out = trial / "judges/explains.json"
        out.parent.mkdir()
        legacy = {"error": "prior invalid verdict", "usage": {"cost": 0.01}, "cost_usd": 0.01}
        out.write_text(json.dumps(legacy))
        calls = self.fake({"stop_reason": "end_turn", "model": "synthetic",
                           "usage": {"cost": 0.02},
                           "content": [{"type": "text", "text": '{"score": 1, "feedback": "ok"}'}]})
        argv = ["judge.py", str(run), "--relai-dir", str(self.repo.relai)]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.judge.main(), 0)
        with patch.object(sys, "argv", argv + ["--force"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.judge.main(), 0)
        history = [json.loads(line) for line in out.with_suffix(".attempts.jsonl").read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0], legacy)
        self.assertAlmostEqual(sum(attempt["cost_usd"] for attempt in history), 0.05)
        self.assertEqual(json.loads(out.read_text()), history[-1])

    def test_billed_refusals_and_invalid_json_keep_usage_in_history(self):
        self.repo.write("relai/.env", "ANTHROPIC_API_KEY=synthetic-anthropic-token\nOPENAI_API_KEY=synthetic-openai-token\n")
        for provider in ("anthropic", "openai"):
            with self.subTest(provider=provider):
                self.repo.write("relai/relai.toml", f'[judge]\nprovider = "{provider}"\nmodel = "configured"\n')
                run = self.repo.relai / "work/runs" / provider
                trial = harbor_trial(run, "t1", self.task, {"looks-up-order": 1})
                if provider == "anthropic":
                    responses = [
                        {"stop_reason": "refusal", "content": []},
                        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "not-json"}]},
                    ]
                else:
                    responses = [
                        {"choices": [{"message": {"refusal": "synthetic refusal"}}]},
                        {"choices": [{"message": {"content": "not-json"}}]},
                    ]
                for response in responses:
                    self.fake({**response, "model": "served", "usage": {"input_tokens": 50, "cost": 0.03}})
                    argv = ["judge.py", str(run), "--relai-dir", str(self.repo.relai)]
                    with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(self.judge.main(), 1)
                out = trial / "judges/explains.json"
                history = [json.loads(line) for line in out.with_suffix(".attempts.jsonl").read_text().splitlines()]
                self.assertEqual(len(history), 2)
                self.assertAlmostEqual(sum(row["cost_usd"] for row in history), 0.06)
                for row in history:
                    self.assertEqual(row["model"], "served")
                    self.assertEqual(row["usage"]["input_tokens"], 50)
                    self.assertTrue(row["error"])
                    self.assertTrue(row["judged_at"])
                self.assertEqual(json.loads(out.read_text()), history[-1])


class OutboundRedactionTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.judge = load("judge")
        self.triage = load("triage")
        self.triage.judge = self.judge
        self.task = self.repo.task()
        self.ev = {"id": "explains", "rubric": "tests/judge.md", "criterion": "Explain the result."}
        self.config = {"provider": "openai-compatible", "model": "synthetic",
                       "base_url": "https://offline.invalid/v1", "api_key_env": "AUDIT_PROVIDER_KEY"}
        self.calls = []

        def post(url, headers, body):
            self.calls.append((headers, body))
            return {"choices": [{"message": {"content": '{"score": 1, "feedback": "ok"}'}}]}
        self.judge.post = post

    def tearDown(self):
        self.repo.close()

    def test_judge_redacts_named_environment_credentials_without_scanning_other_variables(self):
        self.repo.write("relai/relai.toml", '''
            [runtime]
            env = ["AUDIT_TOOL_TOKEN"]
            [judge]
            provider = "openrouter"
            [triage]
            provider = "openai-compatible"
            api_key_env = "AUDIT_TRIAGE_KEY"
        ''')
        known = {"AUDIT_PROVIDER_KEY": "opaque-provider-0123456789",
                 "AUDIT_TOOL_TOKEN": "opaque-tool-0123456789",
                 "OPENROUTER_API_KEY": "opaque-router-0123456789",
                 "AUDIT_TRIAGE_KEY": "opaque-triage-0123456789"}
        unrelated = "unrelated-value-0123456789"
        with patch.dict(os.environ, {**known, "AUDIT_UNRELATED": unrelated}):
            doc = trajectory([{"source": "user", "message": " ".join([*known.values(), unrelated])}])
            result = self.judge.judge_one(self.config, self.repo.relai, self.task, self.ev, doc, {})
        self.assertEqual(result["score"], 1)
        headers, body = self.calls[0]
        self.assertEqual(headers["authorization"], "Bearer " + known["AUDIT_PROVIDER_KEY"])
        outgoing = body["messages"][1]["content"]
        for value in known.values():
            self.assertNotIn(value, outgoing)
        self.assertIn(unrelated, outgoing, "only declared variables are read for exact-value redaction")

    def test_judge_retains_file_redaction_when_environment_overrides_and_redacts_the_whole_prompt(self):
        old = "opaque-provider-original"
        current = old + "-current-secret-suffix"
        extra = "opaque-file-extra-0123456789"
        self.repo.write("relai/.env", f"AUDIT_PROVIDER_KEY={old}\nEXTRA_KEY={extra}\n")
        self.repo.write("relai/tests/orders/tests/judge.md", f"Rubric reference {current} {extra}.")
        ev = {**self.ev, "criterion": f"Criterion reference {old}."}
        with patch.dict(os.environ, {"AUDIT_PROVIDER_KEY": current}):
            result = self.judge.judge_one(self.config, self.repo.relai, self.task, ev,
                                         trajectory([{"source": "user", "message": current}]), {})
        self.assertEqual(result["score"], 1)
        headers, body = self.calls[0]
        self.assertEqual(headers["authorization"], "Bearer " + current)
        outgoing = body["messages"][1]["content"]
        for value in [old, current, extra, "current-secret-suffix"]:
            self.assertNotIn(value, outgoing)

    def test_default_provider_environment_key_is_redacted(self):
        canary = "opaque-default-provider-0123456789"
        for provider, name in [("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY"),
                               ("openrouter", "OPENROUTER_API_KEY")]:
            with self.subTest(provider=provider), patch.dict(os.environ, {name: canary}):
                calls = []
                def post(url, headers, body):
                    calls.append((headers, body))
                    return {"stop_reason": "end_turn", "content": [{"type": "text", "text":
                            '{"score": 1, "feedback": "ok"}'}], "choices": [{"message": {"content":
                            '{"score": 1, "feedback": "ok"}'}}]}
                self.judge.post = post
                self.judge.judge_one({"provider": provider, "model": "synthetic"}, self.repo.relai,
                                     self.task, self.ev, trajectory([{"source": "user", "message": canary}]), {})
                self.assertNotIn(canary, json.dumps(calls[0][1]))
                self.assertIn(canary, json.dumps(calls[0][0]), "credential lookup keeps its existing precedence")

    def test_complete_private_keys_are_removed_from_actual_outgoing_prompt(self):
        canaries = []
        blocks = []
        for label in ("PRIVATE KEY", "RSA PRIVATE KEY", "OPENSSH PRIVATE KEY", "EC PRIVATE KEY"):
            body = "synthetic-key-body-" + label.replace(" ", "-")
            canaries.append(body)
            blocks.append(f"-----BEGIN {label}-----\n{body}\n-----END {label}-----")
        certificate = "-----BEGIN CERTIFICATE-----\nsynthetic-public-certificate\n-----END CERTIFICATE-----"
        self.repo.write("relai/tests/orders/tests/judge.md", blocks[0])
        with patch.dict(os.environ, {"AUDIT_PROVIDER_KEY": "opaque-provider-0123456789"}):
            result = self.judge.judge_one(self.config, self.repo.relai, self.task, self.ev,
                trajectory([{"source": "user", "message": "before\n" + "\n".join(blocks) +
                            "\nafter\n" + certificate}]), {})
        self.assertEqual(result["score"], 1)
        outgoing = self.calls[0][1]["messages"][1]["content"]
        for body in canaries:
            self.assertNotIn(body, outgoing)
        self.assertNotIn("END PRIVATE KEY", outgoing)
        self.assertIn("[redacted private key]", outgoing)
        self.assertIn("before", outgoing)
        self.assertIn("after", outgoing)
        self.assertIn("synthetic-public-certificate", outgoing)

    def test_triage_redacts_context_and_trace_before_the_real_transport_path(self):
        canary = "opaque-triage-env-0123456789"
        def post(url, headers, body):
            self.calls.append((headers, body))
            verdict = {"intent": "synthetic", "outcome": "success", "failure": "", "evidence": [],
                       "weak_signals": [], "risks": [], "requirements": [], "closest_test": "",
                       "needs_human": False, "human_question": ""}
            return {"choices": [{"message": {"content": json.dumps(verdict)}}]}
        self.judge.post = post
        self.repo.write("relai/relai.toml", '''
            [triage]
            provider = "openai-compatible"
            model = "synthetic"
            base_url = "https://offline.invalid/v1"
            api_key_env = "AUDIT_PROVIDER_KEY"
        ''')
        self.repo.write("policy.md", "Policy context " + canary)
        self.repo.write("traces.jsonl", json.dumps({"id": "t1", "trace": "Trace error " + canary}) + "\n")
        args = SimpleNamespace(input=str(self.repo.root / "traces.jsonl"), ingest="redaction", limit=0,
                               concurrency=1, max_chars=1000, context_file=str(self.repo.root / "policy.md"))
        with patch.dict(os.environ, {"AUDIT_PROVIDER_KEY": canary}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.triage.cmd_run(args, self.repo.relai), 0)
        headers, body = self.calls[0]
        self.assertEqual(headers["authorization"], "Bearer " + canary)
        self.assertNotIn(canary, body["messages"][1]["content"])

    def test_provider_diagnostic_is_redacted_in_judge_and_triage_artifacts_and_output(self):
        import urllib.error
        canary = "opaque-diagnostic-credential-0123456789"
        self.repo.write("relai/relai.toml", '''
            [judge]
            provider = "openai-compatible"
            model = "synthetic"
            base_url = "https://offline.invalid/v1"
            api_key_env = "AUDIT_PROVIDER_KEY"
            [triage]
            provider = "openai-compatible"
            model = "synthetic"
            base_url = "https://offline.invalid/v1"
            api_key_env = "AUDIT_PROVIDER_KEY"
        ''')
        # Exercise the transport's HTTP-body diagnostic, then its real callers and writers.
        self.judge = load("judge")
        self.triage.judge = self.judge
        def fail(*args, **kwargs):
            raise urllib.error.HTTPError("https://offline.invalid", 400, "bad request", {},
                                         io.BytesIO(("diagnostic echoed " + canary).encode()))
        run = self.repo.relai / "work/runs/diagnostic"
        trial = harbor_trial(run, "t1", self.task, {"looks-up-order": 1})
        self.repo.write("traces.jsonl", json.dumps({"id": "t1", "trace": "hello"}) + "\n")
        args = SimpleNamespace(input=str(self.repo.root / "traces.jsonl"), ingest="diagnostic", limit=0,
                               concurrency=1, max_chars=1000, context_file=None)
        output = io.StringIO()
        with patch.dict(os.environ, {"AUDIT_PROVIDER_KEY": canary}), \
                patch.object(self.judge.urllib.request, "urlopen", side_effect=fail), \
                patch.object(sys, "argv", ["judge.py", str(run), "--relai-dir", str(self.repo.relai)]), \
                contextlib.redirect_stdout(output):
            self.assertEqual(self.judge.main(), 1)
            self.assertEqual(self.triage.cmd_run(args, self.repo.relai), 1)
        paths = [trial / "judges/explains.json", trial / "judges/explains.attempts.jsonl",
                 self.repo.relai / "work/discover/diagnostic/errors.jsonl"]
        for path in paths:
            diagnostic = path.read_text()
            self.assertNotIn(canary, diagnostic)
            self.assertIn("[redacted", diagnostic)
            self.assertIn("HTTP 400", diagnostic)
        self.assertNotIn(canary, output.getvalue())

    def test_invalid_score_diagnostic_redacts_declared_credential(self):
        canary = "opaque-score-credential-0123456789"
        self.judge.post = lambda *args: {"choices": [{"message": {
            "content": json.dumps({"score": canary, "feedback": "invalid"})}}]}
        with patch.dict(os.environ, {"AUDIT_PROVIDER_KEY": canary}):
            result = self.judge.judge_one(self.config, self.repo.relai, self.task, self.ev, trajectory([]), {})
        self.assertNotIn(canary, result["error"])
        self.assertIn("outside", result["error"])

    def test_self_test_redacts_provider_diagnostic_in_console_output(self):
        import urllib.error
        canary = "opaque-self-test-credential-0123456789"
        self.repo.write("relai/relai.toml", '''
            [judge]
            provider = "openai-compatible"
            model = "synthetic"
            base_url = "https://offline.invalid/v1"
            api_key_env = "AUDIT_PROVIDER_KEY"
        ''')
        self.judge = load("judge")  # Restore the real transport, mocked only at urlopen.
        error = urllib.error.HTTPError("https://offline.invalid", 400, "bad request", {},
                                       io.BytesIO(("diagnostic echoed " + canary).encode()))
        output, stderr = io.StringIO(), io.StringIO()
        argv = ["judge.py", "--self-test", str(self.task), "--relai-dir", str(self.repo.relai)]
        with contextlib.closing(error), \
                patch.dict(os.environ, {"AUDIT_PROVIDER_KEY": canary}), \
                patch.object(self.judge.urllib.request, "urlopen", side_effect=error) as request, \
                patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(stderr):
            self.assertEqual(self.judge.main(), 1)
        request.assert_called_once()
        self.assertIn("FAIL explains:", output.getvalue())
        self.assertIn("HTTP 400", output.getvalue())
        self.assertIn("[redacted AUDIT_PROVIDER_KEY (environment)]", output.getvalue())
        self.assertNotIn(canary, output.getvalue() + stderr.getvalue())


class EvaluateHelperTest(unittest.TestCase):
    def test_rerun_replaces_prior_errors_and_scores(self):
        evaluate = load("evaluate")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            first = evaluate.Results()
            with first.check("check"):
                raise RuntimeError("prior failure")
            first.write(out)
            repaired = evaluate.Results()
            repaired.score("check", 1, "now works")
            repaired.write(out)
            self.assertEqual(json.loads((out / "errors.json").read_text()), {})
            self.assertEqual(json.loads((out / "reward.json").read_text()), {"check": 1})
            with repaired.check("check"):
                raise RuntimeError("failed again")
            self.assertNotIn("check", repaired.rewards)
            self.assertNotIn("check", repaired.feedback)
            repaired.score("check", 1, "repaired in the same instance")
            self.assertNotIn("check", repaired.errors)

    def test_turns_tool_calls_and_results(self):
        evaluate = load("evaluate")
        doc = trajectory([{"source": "user", "message": "a"},
                          {"source": "agent", "message": "", "tool_calls": [
                              {"tool_call_id": "1", "function_name": "get_order", "arguments": {"id": 7}}],
                           "observation": {"results": [{"source_call_id": "1", "content": "paid"}]}},
                          {"source": "agent", "message": "It is paid."},
                          {"source": "user", "message": "b"}, {"source": "agent", "message": "bye"}])
        turns = evaluate.turns(doc)
        self.assertEqual(len(turns), 2)
        self.assertEqual(evaluate.replies(turns[0]).strip(), "It is paid.")
        self.assertEqual(evaluate.tool_calls(doc)[0]["result"], "paid")
        results = evaluate.Results()
        results.score("looks-up", 1.0, "called get_order")
        with results.check("broken"):
            raise KeyError("missing")
        out = Path(tempfile.mkdtemp())
        results.write(out)
        self.assertEqual(json.loads((out / "reward.json").read_text()), {"looks-up": 1.0})
        self.assertIn("KeyError", json.loads((out / "errors.json").read_text())["broken"])
        expected = evaluate.Results(["looks-up", "forgotten"])
        expected.score("looks-up", 1.0, "called get_order")
        expected.write(out)
        self.assertIn("never ran", json.loads((out / "errors.json").read_text())["forgotten"])


class TriageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()

    def tearDown(self) -> None:
        self.repo.close()

    def test_triage_needs_its_own_model_and_never_falls_back_to_the_judge(self):
        self.repo.write("relai/relai.toml", '[judge]\nprovider = "anthropic"\nmodel = "capable"\n')
        triage = load("triage")
        with self.assertRaises(SystemExit) as raised:
            triage.model_config(self.repo.relai)
        self.assertIn("[triage]", str(raised.exception))
        self.assertIn("does not fall back to [judge]", str(raised.exception))

    def test_a_run_larger_than_the_pilot_needs_yes_and_makes_no_call_without_it(self):
        self.repo.write("relai/relai.toml", '[triage]\nprovider = "openrouter"\nmodel = "cheap"\n')
        rows = [json.dumps({"id": f"t{i}", "trace": "hello"}) for i in range(25)]
        self.repo.write("traces.jsonl", "\n".join(rows) + "\n")
        triage = load("triage")
        triage.judge = load("judge")
        args = SimpleNamespace(input=str(self.repo.root / "traces.jsonl"), ingest="gate", limit=0,
                               concurrency=1, max_chars=1000, context_file=None, yes=False)
        stderr = io.StringIO()
        with patch.object(triage.judge, "call_model_full", side_effect=AssertionError("no call without --yes")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 2)
        self.assertIn("--yes", stderr.getvalue())
        self.assertIn("--limit 20", stderr.getvalue())
        args.limit = 20  # the pilot runs without --yes
        with patch.object(triage.judge, "call_model_full", return_value=({"outcome": "success"}, "cheap", {})), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 0)
        args.limit, args.yes = 0, True
        with patch.object(triage.judge, "call_model_full", return_value=({"outcome": "success"}, "cheap", {})), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 0)

    def test_all_errors_in_first_batch_report_and_retry_without_a_verdict_file(self):
        self.repo.write("relai/relai.toml", '[triage]\nprovider = "openrouter"\nmodel = "cheap"\n')
        self.repo.write("traces.jsonl", json.dumps({"id": "t1", "trace": "hello"}) + "\n")
        triage = load("triage")
        triage.judge = load("judge")
        args = SimpleNamespace(input=str(self.repo.root / "traces.jsonl"), ingest="first-errors", limit=0,
                               concurrency=1, max_chars=1000, context_file=None)
        output = io.StringIO()
        with patch.object(triage.judge, "call_model_full", side_effect=RuntimeError("synthetic provider failure")), \
                contextlib.redirect_stdout(output):
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 1)
        d = self.repo.relai / "work/discover/first-errors"
        self.assertFalse((d / "verdicts.jsonl").exists())
        self.assertEqual(json.loads((d / "errors.jsonl").read_text())["error"],
                         "RuntimeError: synthetic provider failure")
        self.assertIn("done: 0 verdicts, 1 errors", output.getvalue())
        self.assertIn("rerun to retry", output.getvalue())
        self.assertIsNone(json.loads((d / "errors.jsonl").read_text())["cost_usd"])
        self.assertIn("cost not reported", output.getvalue())
        with patch.object(triage.judge, "call_model_full", return_value=({"outcome": "success"}, "cheap", {})), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 0)
        self.assertEqual(json.loads((d / "verdicts.jsonl").read_text())["id"], "t1")
        self.assertEqual(len((d / "errors.jsonl").read_text().splitlines()), 1)

    def test_billed_invalid_responses_and_successful_retry_both_count_once(self):
        triage = load("triage")
        triage.judge = load("judge")
        self.repo.write("relai/relai.toml", '[triage]\nprovider = "openrouter"\nmodel = "cheap"\n')
        self.repo.write("relai/.env", "OPENROUTER_API_KEY=synthetic-only-key\n")
        self.repo.write("traces.jsonl", json.dumps({"id": "t1", "trace": "hello"}) + "\n")
        responses = iter([
            {"model": "served", "usage": {"cost": 0.123, "prompt_tokens": 10},
             "choices": [{"message": {"content": "not-json"}}]},
            {"model": "served", "usage": {"cost": 0.02},
             "choices": [{"message": {"content": '{"outcome": "success"}'}}]},
        ])
        triage.judge.post = lambda *args: next(responses)
        args = SimpleNamespace(input=str(self.repo.root / "traces.jsonl"), ingest="billed", limit=0,
                               concurrency=1, max_chars=1000, context_file=None)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 1)
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 0)
            self.assertEqual(triage.cmd_run(args, self.repo.relai), 0)
        d = self.repo.relai / "work/discover/billed"
        error = json.loads((d / "errors.jsonl").read_text())
        self.assertEqual(error["cost_usd"], 0.123)
        self.assertEqual(error["usage"]["prompt_tokens"], 10)
        self.assertEqual(error["model"], "served")
        self.assertIn("$0.1230", output.getvalue())
        self.assertEqual(output.getvalue().count("$0.1430"), 2)
        self.assertEqual(len((d / "verdicts.jsonl").read_text().splitlines()), 1)

    def test_triage_run_resume_and_lanes(self):
        import subprocess, sys
        self.repo.write("relai/relai.toml", '[triage]\nprovider = "openrouter"\nmodel = "cheap"\n')
        self.repo.write("relai/wiki/risks/early-transfer.md", "# Transfers too early\nObservable failure: transfer.\n")
        self.repo.task("orders")
        lines = [json.dumps({"id": f"t{i}", "trace": [{"role": "user", "content": f"hello {i}"}]}) for i in range(4)]
        self.repo.write("traces.jsonl", "\n".join(lines) + "\n")
        triage = load("triage")
        verdicts = {
            "t0": {"outcome": "failure", "failure": "transferred", "risks": ["early-transfer"], "closest_test": "",
                   "weak_signals": [{"kind": "premature-escalation", "note": "n", "quote": "q"},
                                    {"kind": "skipped-check", "note": "n", "quote": "q"}], "intent": "Refund"},
            "t1": {"outcome": "success", "failure": "", "risks": [], "closest_test": "",
                   "weak_signals": [{"kind": "premature-escalation", "note": "n", "quote": "q"},
                                    {"kind": "skipped-check", "note": "n", "quote": "q"}], "intent": "refund"},
            "t2": {"outcome": "success", "failure": "", "risks": [], "closest_test": "orders", "weak_signals": [],
                   "intent": "order status"},
        }

        def fake(config, relai_dir, prompt, system, schema, name, response_metadata=None):
            tid = prompt.rsplit("Run ", 1)[1].split(":", 1)[0]
            if tid == "t3":
                raise RuntimeError("provider down")
            base = {"evidence": [], "requirements": [], "needs_human": False, "human_question": ""}
            self.assertIn("early-transfer", prompt)
            self.assertIn("orders:", prompt)
            return {**base, **verdicts[tid]}, "cheap", {"cost": 0.002}
        triage.judge.call_model_full = fake
        args = type("A", (), {"input": str(self.repo.root / "traces.jsonl"), "ingest": "t1", "limit": 0,
                              "concurrency": 2, "max_chars": 1000, "context_file": None})()
        self.assertEqual(triage.cmd_run(args, self.repo.relai), 1, "an error makes the run exit 1")
        d = self.repo.relai / "work" / "discover" / "t1"
        self.assertEqual(len((d / "verdicts.jsonl").read_text().splitlines()), 3)
        self.assertIn("provider down", (d / "errors.jsonl").read_text())
        verdicts_before = (d / "verdicts.jsonl").read_text()
        triage.judge.call_model_full = fake
        triage.cmd_run(args, self.repo.relai)  # resume: only t3 is retried (and fails again)
        self.assertEqual((d / "verdicts.jsonl").read_text(), verdicts_before)
        triage.cmd_report(type("A", (), {"ingest": "t1"})(), self.repo.relai)
        lanes = json.loads((d / "lanes.json").read_text())
        self.assertEqual([a["id"] for a in lanes["A"]], ["t0"])
        self.assertEqual([b["intent"] for b in lanes["B"]], ["refund"])
        pair = lanes["C"]["co_occurring"][0]
        self.assertEqual(pair["traces"], 2)
        self.assertIn("signal:premature-escalation", pair["pair"])
        self.assertTrue((d / "triage.md").is_file())
        self.assertEqual(json.loads((d / "verdicts.jsonl").read_text().splitlines()[0])["cost_usd"], 0.002)


class AnyProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()
        self.judge = load("judge")
        self.task = self.repo.task()
        self.ev = {"id": "explains", "type": "judge", "rubric": "tests/judge.md", "criterion": "c",
                   "min_score": 0.0, "max_score": 1.0}
        self.repo.write("relai/.env", "OPENROUTER_API_KEY=or-test-0123456789abcdef\nLLM_KEY=llm-test-0123456789\n")

    def tearDown(self) -> None:
        self.repo.close()

    def fake(self):
        calls = []

        def post(url, headers, body):
            calls.append((url, headers, body))
            return {"model": "served", "choices": [{"message": {"content": '{"score": 1, "feedback": "fine"}'}}]}
        self.judge.post = post
        return calls

    def test_openrouter_asks_for_cost_and_judge_records_it(self):
        calls = []
        self.judge.post = lambda url, headers, body: (calls.append(body) or {
            "model": "m", "usage": {"prompt_tokens": 10, "cost": 0.0123},
            "choices": [{"message": {"content": '{"score": 1, "feedback": "fine"}'}}]})
        traj = trajectory([{"source": "user", "message": "hi"}, {"source": "agent", "message": "ok"}])
        r = self.judge.judge_one({"provider": "openrouter", "model": "m"}, self.repo.relai, self.task, self.ev, traj, {})
        self.assertEqual(calls[0]["usage"], {"include": True})
        self.assertEqual(r["cost_usd"], 0.0123)

    def test_openrouter_and_compatible_urls_and_keys(self):
        calls = self.fake()
        traj = trajectory([{"source": "user", "message": "hi"}, {"source": "agent", "message": "ok"}])
        r = self.judge.judge_one({"provider": "openrouter", "model": "anthropic/claude-opus-5.5"},
                                 self.repo.relai, self.task, self.ev, traj, {})
        self.assertEqual(r["score"], 1)
        self.assertEqual(calls[0][0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(calls[0][1]["authorization"], "Bearer or-test-0123456789abcdef")
        self.judge.judge_one({"provider": "openai-compatible", "model": "m", "base_url": "http://llm:4000/v1/",
                              "api_key_env": "LLM_KEY"}, self.repo.relai, self.task, self.ev, traj, {})
        self.assertEqual(calls[1][0], "http://llm:4000/v1/chat/completions")
        self.assertEqual(calls[1][1]["authorization"], "Bearer llm-test-0123456789")

    def test_simulated_user_compatible_needs_base_url(self):
        launcher = load("launcher")
        seen = []
        launcher.post_json = lambda url, headers, body, timeout=300: (
            seen.append(url) or {"choices": [{"message": {"content": "hello"}}]})
        text, _ = launcher.simulated_user_turn({"instructions": "be a user", "model": "openrouter:openai/gpt-5.5"}, [], "k")
        self.assertEqual(text, "hello")
        self.assertEqual(seen[0], "https://openrouter.ai/api/v1/chat/completions")
        with self.assertRaises(RuntimeError):
            launcher.simulated_user_turn({"instructions": "u", "model": "compatible:m"}, [], "k")


if __name__ == "__main__":
    unittest.main()
