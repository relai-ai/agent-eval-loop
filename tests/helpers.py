"""Fixtures for the RELAI checker tests: a throwaway repository with relai/ copied from the plugin."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parent.parent
TEMPLATE = PLUGIN / "skills" / "start" / "template"
EXAMPLES = PLUGIN / "examples"  # copied into relai/bin/ or relai/harness/ when chosen

GOOD_TASK_TOML = """\
artifacts = ["/logs/agent/trajectory.json"]

[task]
name = "acme/{id}"
version = "0.1.0"
description = "A test."

[verifier]
environment_mode = "separate"
timeout_sec = 300

[metadata.relai]
id = "{id}"
behavior = "Looks up the order before answering."

[[metadata.relai.evaluators]]
id = "looks-up-order"
type = "code"
method = "exact"
criterion = "Calls get_order with the order id."
min_score = 0.0
max_score = 1.0

[[metadata.relai.evaluators]]
id = "explains"
type = "judge"
method = "semantic"
criterion = "Explains the order status."
rubric = "tests/judge.md"
min_score = 0.0
max_score = 1.0
"""

VERIFIER = """\
import json, pathlib
traj = json.loads(pathlib.Path("/logs/agent/trajectory.json").read_text())
replies = " ".join(s.get("message", "") for s in traj["steps"] if s["source"] == "agent")
ok = bool(replies.strip())
out = pathlib.Path("/logs/verifier")
out.joinpath("reward.json").write_text(json.dumps({"looks-up-order": 1.0 if ok else 0.0}))
out.joinpath("feedback.json").write_text(json.dumps({"looks-up-order": "replied" if ok else "no reply; full marks need a reply"}))
"""


# A Harbor release for tests that run Harbor; projects record their own in relai.toml [harbor].version.
HARBOR_TEST_VERSION = "0.25.0"


def container_engine() -> bool:
    """Whether a docker- or podman-compatible engine is running, as check_task.py --verifier needs."""
    for cli in ("docker", "podman"):
        if shutil.which(cli) and subprocess.run([cli, "info"], capture_output=True).returncode == 0:
            return True
    return False


class Repo:
    """A temporary repository with relai/ installed the way the start skill installs it."""

    def __init__(self) -> None:
        # Provider tests must use fixture keys, never credentials inherited from the developer.
        self._provider_env = patch.dict(os.environ, {name: "" for name in
            ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")})
        self._provider_env.start()
        self._tmp = tempfile.TemporaryDirectory(prefix="relai-test-")
        self.root = Path(self._tmp.name)
        self.relai = self.root / "relai"
        shutil.copytree(TEMPLATE, self.relai)
        (self.relai / "gitignore").rename(self.relai / ".gitignore")

    def close(self) -> None:
        try:
            self._tmp.cleanup()
        finally:
            self._provider_env.stop()

    def write(self, rel: str, content: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))
        return path

    def task(self, test_id: str = "orders", toml: str | None = None) -> Path:
        base = f"relai/tests/{test_id}"
        self.write(f"{base}/task.toml", (toml or GOOD_TASK_TOML).format(id=test_id))
        self.write(f"{base}/instruction.md", "")
        self.write(f"{base}/environment/Dockerfile", "FROM python:3.12-slim\n")
        self.write(f"{base}/tests/test.sh", "#!/bin/sh\npython3 /tests/evaluate.py\n")
        self.write(f"{base}/tests/Dockerfile", "FROM python:3.12-slim\nCOPY . /tests/\n")
        self.write(f"{base}/tests/evaluate.py", VERIFIER)
        self.write(f"{base}/tests/judge.md", "Full marks when the reply states the order status.\n")
        return self.root / base

    def run(self, script: str, *args: str) -> subprocess.CompletedProcess:
        path = self.relai / "bin" / script
        return subprocess.run([sys.executable, str(path), *args], capture_output=True, text=True, cwd=self.root)


def trajectory(steps: list[dict], **extra) -> dict:
    doc = {"schema_version": "ATIF-v1.7", "agent": {"name": "test", "version": "1", "model_name": "m"},
           "steps": [{"step_id": i + 1, **s} for i, s in enumerate(steps)]}
    doc.update(extra)
    return doc


def harbor_trial(job: Path, name: str, task_dir: Path, rewards: dict | None, checksum: str = "c1",
                 exception: str | None = None, feedback: dict | None = None, judges: dict | None = None,
                 with_trajectory: bool = True) -> Path:
    trial = job / name
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir()
    result = {"trial_name": name, "task_name": task_dir.name, "task_id": {"path": str(task_dir)},
              "task_checksum": checksum, "verifier_result": {"rewards": rewards} if rewards is not None else None,
              "exception_info": {"exception_type": exception} if exception else None,
              "agent_result": {"n_input_tokens": 100, "n_output_tokens": 10, "cost_usd": 0.01}}
    (trial / "result.json").write_text(json.dumps(result))
    if with_trajectory:
        (trial / "agent" / "trajectory.json").write_text(json.dumps(trajectory([
            {"source": "user", "message": "hi"}, {"source": "agent", "message": "hello"}])))
    if feedback is not None:
        (trial / "verifier" / "feedback.json").write_text(json.dumps(feedback))
    for ev_id, data in (judges or {}).items():
        (trial / "judges").mkdir(exist_ok=True)
        (trial / "judges" / f"{ev_id}.json").write_text(json.dumps(data))
    return trial


def harbor_job(root: Path, name: str, n_trials: int, errored: int = 0) -> Path:
    job = root / name
    job.mkdir(parents=True)
    (job / "result.json").write_text(json.dumps({"n_total_trials": n_trials,
                                                 "stats": {"n_errored_trials": errored, "n_completed_trials": n_trials}}))
    return job
