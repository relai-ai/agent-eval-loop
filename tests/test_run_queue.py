"""Tests for run_queue.py: a resumable queue of (task, agent) Harbor jobs, driven here by a fake harbor command.
Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import Repo

FAKE_HARBOR = r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
def value(flag):
    return args[args.index(flag) + 1]
out, job, attempts, task = Path(value("-o")), value("--job-name"), int(value("-k")), value("-p")
log = Path(os.environ["FAKE_LOG"])
with log.open("a") as handle:
    handle.write(json.dumps({"argv": args, "has_key": os.environ.get("FIXTURE_AGENT_KEY") == "sk-fixture-0123456789"}) + "\n")
modes = json.loads(Path(os.environ["FAKE_MODES"]).read_text()) if Path(os.environ["FAKE_MODES"]).is_file() else {}
mode = modes.get(job, "ok")
(out / job).mkdir(parents=True, exist_ok=True)
for n in range(attempts):
    if mode == "killed" and n == 1:
        (out / job / f"t{n}").mkdir()
        sys.exit(137)
    trial = out / job / f"t{n}"
    trial.mkdir()
    crashed = mode == "crash"
    (trial / "result.json").write_text(json.dumps({
        "trial_name": f"{job}-t{n}", "task_name": Path(task).name,
        "exception_info": {"exception_type": "AgentSetupError"} if crashed else None,
        "verifier_result": None if crashed else {"rewards": {"fixes-the-bug": 1.0}}}))
'''

RELAI_TOML = """
[harbor]
version = "0.26.0"

[[coding_evals.agents]]
id = "opus"
agent = "claude-code"
model = "anthropic/claude-opus-5-5"
version = "3.1.0"
env = ["FIXTURE_AGENT_KEY"]

[[coding_evals.agents]]
id = "codex"
agent = "codex"
model = "openai/gpt-6.2"
"""


class RunQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()
        self.repo.write("relai/relai.toml", RELAI_TOML)
        self.repo.write("relai/.env", "FIXTURE_AGENT_KEY=sk-fixture-0123456789\n")
        self.tasks = [self.repo.task("alpha"), self.repo.task("beta")]
        self.run_dir = self.repo.relai / "work" / "runs" / "round-1"
        self.fake = self.repo.root / "fake_harbor.py"
        self.fake.write_text(FAKE_HARBOR)
        self.log = self.repo.root / "harbor.log"
        self.modes = self.repo.root / "modes.json"

    def tearDown(self) -> None:
        self.repo.close()

    def queue(self, *args: str, modes: dict | None = None) -> subprocess.CompletedProcess:
        if modes is not None:
            self.modes.write_text(json.dumps(modes))
        extra = ["--harbor", f"{sys.executable} {self.fake}", "--poll", "0.05"] if args[0] == "run" else []
        path = self.repo.relai / "bin" / "run_queue.py"
        return subprocess.run([sys.executable, str(path), str(self.run_dir), *args, *extra], capture_output=True,
                              text=True, cwd=self.repo.root,
                              env={"PATH": "/usr/bin:/bin", "FAKE_LOG": str(self.log), "FAKE_MODES": str(self.modes),
                                   "HOME": str(self.repo.root)})

    def calls(self) -> list:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.is_file() else []

    def init(self, *extra: str) -> None:
        ran = self.queue("init", "--tasks", *map(str, self.tasks), "--agents", "opus,codex", *extra)
        self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_every_pair_runs_once_with_its_agent_and_credentials_stay_off_the_command_line(self):
        self.init("--parallel", "2")
        ran = self.queue("run")
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        calls = self.calls()
        self.assertEqual(sorted(c["argv"][c["argv"].index("--job-name") + 1] for c in calls),
                         ["alpha__codex", "alpha__opus", "beta__codex", "beta__opus"])
        opus = next(c for c in calls if "alpha__opus" in c["argv"])
        self.assertEqual(opus["argv"][:8], ["run", "-e", "docker", "-p", str(self.tasks[0].resolve()), "-a",
                                            "claude-code", "-m"])
        self.assertIn("version=3.1.0", opus["argv"])
        self.assertTrue(opus["has_key"], "the agent's credential reaches Harbor through its environment")
        self.assertFalse(any("sk-fixture" in arg for c in calls for arg in c["argv"]))
        self.assertIn("4 of 4 pair(s) finished", ran.stdout)
        status = self.queue("status")
        self.assertEqual(status.returncode, 0, status.stdout)
        self.assertEqual(status.stdout.count("done"), 4)
        self.assertEqual(self.queue("run").returncode, 0)
        self.assertEqual(len(self.calls()), 4, "a finished queue starts nothing on resume")

    def test_a_killed_job_is_resumed_with_only_its_missing_attempts(self):
        self.init("--attempts", "2", "--max-retries", "0")
        ran = self.queue("run", modes={"alpha__opus": "killed"})
        self.assertEqual(ran.returncode, 1, ran.stdout)
        self.assertIn("3 of 4 pair(s) finished", ran.stdout)
        status = self.queue("status")
        self.assertIn("missing  tests/alpha opus: 1/2 finished", status.stdout)
        ran = self.queue("run", modes={})
        self.assertEqual(ran.returncode, 0, ran.stdout)
        retries = [c["argv"] for c in self.calls()[4:]]
        self.assertEqual(len(retries), 1, "only the interrupted pair runs again")
        self.assertEqual(retries[0][retries[0].index("--job-name") + 1], "alpha__opus__retry1")
        self.assertEqual(retries[0][retries[0].index("-k") + 1], "1")
        self.assertTrue((self.run_dir / "alpha__opus" / "t1").is_dir(), "the interrupted job is left as it was")

    def test_a_trial_that_crashed_before_verification_is_retried_up_to_max_retries(self):
        self.init("--max-retries", "1")
        modes = {f"{t}__{a}{s}": "crash" for t in ("alpha", "beta") for a in ("opus", "codex") for s in ("", "__retry1")}
        ran = self.queue("run", modes=modes)
        self.assertEqual(ran.returncode, 0, ran.stdout)
        self.assertEqual(len(self.calls()), 8, "each pair ran once and was retried once")
        status = self.queue("status")
        self.assertIn("tests/alpha opus: 1/1 finished, 2 crashed, 2 job(s)", status.stdout)

    def test_a_job_still_running_from_an_earlier_queue_is_waited_for_not_restarted(self):
        self.init()
        launched = subprocess.run(["sh", "-c", "sleep 1 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True)
        pid = int(launched.stdout.strip())
        state = json.loads((self.run_dir / "queue.json").read_text())
        item = state["items"][0]
        item["jobs"] = ["alpha__opus"]
        item["running"] = {"pid": pid, "job": "alpha__opus"}
        trial = self.run_dir / "alpha__opus" / "t0"
        trial.mkdir(parents=True)
        (trial / "result.json").write_text(json.dumps({"trial_name": "x", "exception_info": None,
                                                       "verifier_result": {"rewards": {}}}))
        (self.run_dir / "queue.json").write_text(json.dumps(state))
        ran = self.queue("run")
        self.assertEqual(ran.returncode, 0, ran.stdout)
        self.assertNotIn("alpha__opus", [c["argv"][c["argv"].index("--job-name") + 1] for c in self.calls()])
        self.assertIn("tests/alpha opus: job alpha__opus ended", ran.stdout)

    def test_dry_run_lock_and_bad_agents(self):
        self.init()
        ran = self.queue("run", "--dry-run")
        self.assertEqual(ran.returncode, 0)
        self.assertIn("would run tests/beta codex as beta__codex: 1 missing", ran.stdout)
        self.assertEqual(self.calls(), [])
        with (self.run_dir / "queue.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ran = self.queue("run")
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("another run_queue.py is running", ran.stderr)
        again = self.queue("init", "--tasks", str(self.tasks[0]), "--agents", "opus")
        self.assertIn("exists; `run` resumes it", again.stderr)
        (self.run_dir / "queue.json").unlink()
        bad = self.queue("init", "--tasks", str(self.tasks[0]), "--agents", "gemini")
        self.assertIn("are not ids of [[coding_evals.agents]]", bad.stderr)


if __name__ == "__main__":
    unittest.main()
