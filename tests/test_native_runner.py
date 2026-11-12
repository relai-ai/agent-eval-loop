"""Offline integration tests for the optional native launcher and shared result consumers."""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from helpers import EXAMPLES, Repo, TEMPLATE
REFERENCE = EXAMPLES

TRIAL_COMMAND = """\
import json, os, sys
from pathlib import Path
task_dir, trial_dir, attempt = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
mode = os.environ.get("MODE", "")
(trial_dir / "agent" / "seen.txt").write_text(task_dir.as_posix() + " " + " ".join(sys.argv[4:]))
if os.environ.get("FAIL_ATTEMPT") == str(attempt) or mode == "fail":
    sys.exit(3)
if os.environ.get("LEAK_CHECK") is not None and "OTHER_SECRET" in os.environ:
    sys.exit(4)
steps = [{"step_id": 1, "source": "user", "message": "status?"},
         {"step_id": 2, "source": "agent", "message": "shipped", "model_name": "m"}]
(trial_dir / "agent" / "trajectory.json").write_text(json.dumps(
    {"schema_version": "ATIF-v1.7", "agent": {"name": "a", "version": "1"}, "steps": steps}))
(trial_dir / "agent" / "usage.json").write_text(json.dumps({"n_input_tokens": 5, "n_output_tokens": 2}))
(trial_dir / "verifier" / "reward.json").write_text(json.dumps({"looks-up-order": 1.0}))
(trial_dir / "verifier" / "feedback.json").write_text(json.dumps({"looks-up-order": "looked it up"}))
(trial_dir / "judges").mkdir(exist_ok=True)
(trial_dir / "judges" / "explains.json").write_text(json.dumps({"score": 1.0, "feedback": "ok"}))
if mode == "exit-after-score":
    sys.exit(5)
"""


class NativeRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()
        self.task = self.repo.task().resolve()
        self.repo.write("relai/harness/run_trial.py", TRIAL_COMMAND)
        shutil.copy(REFERENCE / "native_runner.py", self.repo.relai / "bin")  # how a user installs the example
        self.out = self.repo.root / "evals" / "work" / "runs" / "native"

    def tearDown(self) -> None:
        self.repo.close()

    def runner(self, *extra: str, tests=None, env=None, attempts="1", tail=()):
        command = [sys.executable, str(self.repo.relai / "bin" / "native_runner.py"), "--tests",
                   *[str(t) for t in (tests or [self.task])], "--attempts", attempts, "--out", str(self.out),
                   "--concurrency", "2", *extra, *self.passed(env, extra), "--",
                   sys.executable, "relai/harness/run_trial.py", "{task_dir}", "{trial_dir}", "{attempt}", *tail]
        return subprocess.run(command, capture_output=True, text=True, cwd=self.repo.root,
                              env={"PATH": "/usr/bin:/bin", **(env or {})}, timeout=120)

    @staticmethod
    def passed(env, extra) -> list[str]:
        names = [k for k in (env or {}) if k not in ("OTHER_SECRET", "LEAK_CHECK")]
        return [] if "--pass-env" in extra or not names else ["--pass-env", *names]

    def trials(self) -> dict:
        found = {}
        for path in sorted(self.out.glob("*/result.json")):
            data = json.loads(path.read_text())
            found[(data["task_id"]["path"], data["attempt"])] = (path.parent, data)
        return found

    def test_writes_the_layout_summarize_reads_and_failures_stay_apart(self):
        first = self.runner("--pass-env", "FAIL_ATTEMPT", env={"FAIL_ATTEMPT": "2"}, attempts="2")
        self.assertEqual(first.returncode, 0, first.stderr)
        trials = self.trials()
        _, ok = trials[(str(self.task), 1)]
        self.assertEqual(ok["runner"], "native")
        self.assertEqual(ok["verifier_result"], {"rewards": {"looks-up-order": 1.0}})
        _, bad = trials[(str(self.task), 2)]
        self.assertIsNone(bad["verifier_result"])
        self.assertEqual(bad["exception_info"]["exception_type"], "NonZeroExit(3)")
        summary = self.repo.run("summarize.py", str(self.out), "--details")
        self.assertIn("scored 1", summary.stdout)
        self.assertIn("runtime failure 1", summary.stdout)
        self.assertIn("Runner: native", summary.stdout)
        self.assertIn("1 errored trial", summary.stdout)
        kept = self.runner(attempts="2")
        self.assertIn("1 runtime failure", kept.stdout)  # finished trials are kept, not rerun
        retried = self.runner("--retry-failed", attempts="2")
        self.assertIn("0 runtime failure", retried.stdout)

    def test_same_directory_names_in_different_places_get_their_own_trials(self):
        other = (self.repo.root / "evals" / "benchmarks" / "b" / "rows" / "orders").resolve()
        shutil.copytree(self.task, other)
        result = self.runner(tests=[self.task, other])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.trials()), 2)

    def test_evaluator_definitions_are_captured_before_the_command_runs(self):
        # Omitted bounds are materialized before a command can change the current task file.
        config = self.task / "task.toml"
        config.write_text(config.read_text().replace("min_score = 0.0\n", "").replace("max_score = 1.0\n", ""))
        script = self.repo.relai / "harness/run_trial.py"
        script.write_text(script.read_text() + '\np = task_dir / "task.toml"\n'
                          'p.write_text(p.read_text().replace("type = \\\"code\\\"", "type = \\\"code\\\"\\nmax_score = 2.0")'
                          '.replace("type = \\\"judge\\\"", "type = \\\"judge\\\"\\nmax_score = 2.0"))\n')
        result = self.runner()
        self.assertEqual(result.returncode, 0, result.stderr)
        _, trial = self.trials()[(str(self.task), 1)]
        self.assertEqual(trial["evaluator_definitions"], [
            {"id": "looks-up-order", "type": "code", "min_score": 0.0, "max_score": 1.0},
            {"id": "explains", "type": "judge", "min_score": 0.0, "max_score": 1.0}])
        path = self.repo.root / "summary.json"
        summary = self.repo.run("summarize.py", str(self.out), "--json", str(path))
        self.assertEqual(summary.returncode, 0, summary.stderr)
        scored = json.loads(path.read_text())["run"]["tests"]["tests/orders"]
        self.assertEqual(scored["mean"], 1.0)

    def test_stale_files_from_an_interrupted_trial_are_not_scored(self):
        self.runner()
        trial_dir, _ = self.trials()[(str(self.task), 1)]
        (trial_dir / "result.json").unlink()  # as if killed before the result was written
        rerun = self.runner(env={"MODE": "fail"}, tail=())
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        _, data = self.trials()[(str(self.task), 1)]
        self.assertIsNone(data["verifier_result"])
        self.assertFalse((trial_dir / "verifier" / "reward.json").exists())

    def test_braces_pass_through_and_a_score_before_a_crash_is_kept_with_the_exception(self):
        result = self.runner(env={"MODE": "exit-after-score"}, tail=("{}", "{not_a_placeholder}"))
        self.assertEqual(result.returncode, 0, result.stderr)
        trial_dir, data = self.trials()[(str(self.task), 1)]
        self.assertTrue((trial_dir / "agent" / "seen.txt").read_text().endswith("{} {not_a_placeholder}"))
        self.assertEqual(data["exception_info"]["exception_type"], "NonZeroExit(5)")
        summary = self.repo.run("summarize.py", str(self.out), "--details")
        self.assertIn("scored 1", summary.stdout)
        self.assertIn("scored, but the runner recorded NonZeroExit(5)", summary.stdout)

    def test_only_named_variables_reach_the_command(self):
        result = self.runner("--pass-env", "LEAK_CHECK", env={"LEAK_CHECK": "1", "OTHER_SECRET": "x"})
        _, data = self.trials()[(str(self.task), 1)]
        self.assertIsNone(data["exception_info"], result.stderr)

    def test_resuming_with_a_different_command_is_refused(self):
        self.runner()
        changed = self.runner(tail=("--extra",))
        self.assertEqual(changed.returncode, 2)
        self.assertIn("different command or test version", changed.stderr)

    def test_runner_id_not_command_decides_comparability(self):
        self.runner()
        first = self.out
        self.out = self.repo.root / "evals" / "work" / "runs" / "candidate"
        self.runner(tail=("--candidate-config",))  # same runner, different command (e.g. a worktree)
        same = self.repo.run("summarize.py", str(self.out), "--baseline", str(first))
        self.assertEqual(same.returncode, 0, same.stdout)
        self.out = self.repo.root / "evals" / "work" / "runs" / "other"
        self.runner("--runner-id", "other-grader")
        other = self.repo.run("summarize.py", str(self.out), "--baseline", str(first))
        self.assertEqual(other.returncode, 0, other.stdout)
        self.assertIn("Comparison warnings:", other.stdout)

    def test_refused_resume_starts_no_trial_and_duplicates_run_once(self):
        self.runner(tests=[self.task, self.task])
        self.assertEqual(len(self.trials()), 1)
        refused = self.runner(tail=("--extra",), attempts="2")
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(len(self.trials()), 1)  # attempt 2 was not started


    def test_runner_identity_change_refuses_resume_before_new_trials(self):
        self.runner()
        changed = self.runner("--runner-id", "new-grader", attempts="2")
        self.assertEqual(changed.returncode, 2)
        self.assertEqual(len(self.trials()), 1)

    def test_symlink_trial_directory_is_rejected_before_launch(self):
        self.runner()
        trial_dir, _ = self.trials()[(str(self.task), 1)]
        shutil.rmtree(trial_dir)
        outside = self.repo.root / "outside"
        outside.mkdir()
        marker = outside / "preserve.txt"
        marker.write_text("keep")
        trial_dir.symlink_to(outside, target_is_directory=True)
        result = self.runner(attempts="2")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not be symlinks", result.stderr)
        self.assertEqual(marker.read_text(), "keep")
        self.assertEqual(list(outside.iterdir()), [marker])

    def test_changed_task_refuses_resume_before_new_trials(self):
        self.runner()
        (self.task / "instruction.md").write_text("changed scenario")
        changed = self.runner(attempts="2")
        self.assertEqual(changed.returncode, 2)
        self.assertEqual(len(self.trials()), 1)

    def delayed_child(self):
        marker = self.repo.root / "late-side-effect"
        ready = self.repo.root / "child-started"
        child = f"import time; from pathlib import Path; time.sleep(1.5); Path({str(marker)!r}).write_text('late')"
        self.repo.write("relai/harness/run_trial.py",
                        f"import subprocess, sys, time\nfrom pathlib import Path\n"
                        f"subprocess.Popen([sys.executable, '-c', {child!r}])\n"
                        f"Path({str(ready)!r}).write_text('ready')\ntime.sleep(5)\n")
        return marker, ready

    @unittest.skipUnless(os.name == "posix", "POSIX process-group lifecycle")
    def test_timeout_stops_descendants_before_they_write(self):
        marker, ready = self.delayed_child()
        result = self.runner("--timeout", "0.5")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(ready.exists(), "the child must actually have been launched")
        _, data = self.trials()[(str(self.task), 1)]
        self.assertEqual(data["exception_info"]["exception_type"], "TrialTimeout")
        time.sleep(1.6)
        self.assertFalse(marker.exists(), "timed-out descendants must not mutate the trial later")

    @unittest.skipUnless(os.name == "posix", "POSIX CLI interruption")
    def test_cli_interrupt_cancels_workers_and_stops_descendants(self):
        marker, ready = self.delayed_child()
        command = [sys.executable, str(self.repo.relai / "bin/native_runner.py"), "--tests", str(self.task),
                   "--out", str(self.out), "--timeout", "30", "--", sys.executable,
                   "relai/harness/run_trial.py", "{task_dir}", "{trial_dir}", "{attempt}"]
        process = subprocess.Popen(command, cwd=self.repo.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), "wait until the worker has actually launched its child")
            process.send_signal(signal.SIGINT)
            _, stderr = process.communicate(timeout=3)
            self.assertNotEqual(process.returncode, 0, stderr)
            _, data = self.trials()[(str(self.task), 1)]
            self.assertEqual(data["exception_info"]["exception_type"], "TrialInterrupted")
            time.sleep(1.6)
            self.assertFalse(marker.exists(), "interrupting the CLI must stop its worker's descendants")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
