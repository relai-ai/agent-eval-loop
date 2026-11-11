#!/usr/bin/env python3
"""Reference native runner: runs a per-trial command for each test x attempt and writes the trial
layout the checkers read (see relai/docs/native.md). Standard library only.

  python3 relai/bin/native_runner.py --out relai/work/runs/<run-id> --attempts 2 \
      --concurrency 8 --pass-env OPENAI_API_KEY --tests relai/tests/a relai/tests/b \
      -- python3 relai/harness/run_trial.py {task_dir} {trial_dir} {attempt}

The command after `--` runs once per trial, with these placeholders replaced (other text, braces
included, is passed through unchanged):
  {task_dir}   absolute path of the test directory
  {trial_dir}  absolute path of this trial's directory (created empty beforehand)
  {test_id}    [metadata.relai].id of the test
  {attempt}    attempt number, starting at --first-attempt
It runs the agent through its real entrypoint, writes the ATIF trajectory to
{trial_dir}/agent/trajectory.json, scores it, and writes {trial_dir}/verifier/reward.json,
feedback.json and errors.json (the examples' evaluate.py's format). It may also write
{trial_dir}/agent/usage.json: {"n_input_tokens", "n_output_tokens", "cost_usd"}.

This launcher does not sandbox the command. The integration must provide reviewed containment
and explicit authorization for host execution before using it.
On POSIX, timeout/interruption kills the command's process group. Other platforms stop only the
direct process; their integration must manage descendants. Container-launching integrations must
also own container cleanup: stopping a CLI process is not stopping its container.

The runner never trusts the command's exit status: the files decide. A trial without reward.json
has verifier_result null and counts as a runtime failure; a non-zero exit or a timeout is recorded
as exception_info either way. A trial that already has result.json is kept, so rerunning resumes
an interrupted run; a trial directory without result.json is cleared and rerun. Use a new --out for each agent revision. --retry-failed
also reruns trials that recorded a runtime failure. Resuming with a different command, runner identity or a
changed test is refused before any trial starts: use a new --out.

--runner-id names the runner implementation (default "native"). summarize.py reports differences
across runner ids with an advisory notice. Keep it the same for a before/after pair when the command's
paths or configuration differ (a worktree, a candidate model), and change it when the way trials
are run or graded changes.

The command gets a minimal environment (PATH, HOME, LANG, TMPDIR and the names given with
--pass-env, taken from this process's environment), never the whole environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # copied beside relai/bin/_common.py
from _common import declared_evaluators, dir_digest, load_toml  # noqa: E402

BASE_ENV = ("PATH", "HOME", "LANG", "TMPDIR")
PLACEHOLDERS = ("task_dir", "trial_dir", "test_id", "attempt")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def git(cwd: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def trial_name(task_dir: Path, cwd: Path, attempt: int) -> str:
    """Unique per test directory: its path relative to the working directory, plus a short hash of
    the absolute path, so tests/x and benchmarks/b/rows/x never share a trial directory."""
    rel = task_dir.relative_to(cwd).as_posix() if task_dir.is_relative_to(cwd) else task_dir.as_posix()
    key = re.sub(r"[^A-Za-z0-9._-]+", "_", rel.strip("/").replace("/", "-"))[-80:]
    digest = hashlib.sha256(str(task_dir).encode()).hexdigest()[:6]
    return f"{key}-{digest}__a{attempt}"


def fill(part: str, values: dict) -> str:
    for name in PLACEHOLDERS:
        part = part.replace("{" + name + "}", values[name])
    return part


def failed(result: dict) -> bool:
    return result.get("verifier_result") is None


def stop_command(process: subprocess.Popen) -> None:
    """Stop the trial group on POSIX, even when its leader has already exited."""
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.wait()


def run_trial(task_dir: Path, attempt: int, out: Path, command: list[str], cwd: Path, timeout: float,
              env: dict, retry_failed: bool, meta: dict, cancelled: threading.Event | None = None) -> dict:
    trial = out / trial_name(task_dir, cwd, attempt)
    if trial.is_symlink():
        raise ValueError("trial directory must not be a symlink")
    result_path = trial / "result.json"
    existing = read_json(result_path)
    checksum = dir_digest(task_dir)
    template = shlex.join(command)
    if isinstance(existing, dict) and not (retry_failed and failed(existing)):
        return existing
    if trial.exists():
        shutil.rmtree(trial)  # stale files from an interrupted or retried trial must not be scored
    for sub in ("agent", "verifier", "logs"):
        (trial / sub).mkdir(parents=True)
    started = time.monotonic()
    exception, argv, evaluator_definitions = None, command, None
    try:
        if cancelled is not None and cancelled.is_set():
            raise InterruptedError("trial cancelled")
        config = load_toml(task_dir / "task.toml")
        meta_relai = ((config.get("metadata") or {}).get("relai") or {})
        evaluator_definitions = [{"id": ev.get("id"), "type": ev.get("type"),
                                  "min_score": ev.get("min_score", 0.0), "max_score": ev.get("max_score", 1.0)}
                                 for ev in declared_evaluators(config)]
        values = {"task_dir": str(task_dir), "trial_dir": str(trial), "attempt": str(attempt),
                  "test_id": str(meta_relai.get("id", task_dir.name))}
        argv = [fill(part, values) for part in command]
        with (trial / "logs" / "stdout.txt").open("w") as stdout, (trial / "logs" / "stderr.txt").open("w") as stderr:
            process = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr, env=env,
                                       start_new_session=os.name == "posix")
            deadline = time.monotonic() + timeout
            try:
                while True:
                    if cancelled is not None and cancelled.is_set():
                        raise InterruptedError("trial cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(argv, timeout)
                    try:
                        code = process.wait(timeout=min(remaining, 0.2))
                        break
                    except subprocess.TimeoutExpired:
                        continue
            except BaseException:
                stop_command(process)
                raise
        if code != 0:
            exception = f"NonZeroExit({code})"
    except subprocess.TimeoutExpired:
        exception = "TrialTimeout"
    except InterruptedError:
        exception = "TrialInterrupted"
    except Exception as exc:  # a broken task.toml or launch failure is this trial's runtime failure
        exception = f"LaunchError: {type(exc).__name__}: {exc}"[:500]
    rewards = read_json(trial / "verifier" / "reward.json")
    usage = read_json(trial / "agent" / "usage.json")
    result = {
        "trial_name": trial.name,
        "runner": "native",
        "runner_id": meta["runner_id"],
        "runner_command": template,
        "task_name": task_dir.name,
        "task_id": {"path": str(task_dir)},
        "task_checksum": checksum,
        "evaluator_definitions": evaluator_definitions,
        "attempt": attempt,
        "verifier_result": {"rewards": rewards} if isinstance(rewards, dict) else None,
        "exception_info": {"exception_type": exception} if exception else None,
        "agent_result": usage if isinstance(usage, dict) else None,
        "duration_sec": round(time.monotonic() - started, 1),
        "command": shlex.join(argv),
        "git_head": meta["git_head"],
        "git_dirty": meta["git_dirty"],
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def conflicts(jobs: list, out: Path, cwd: Path, template: str, runner_id: str) -> list[str]:
    """Trials already in the run directory that were made by another command or test version."""
    found = []
    for task_dir, attempt in jobs:
        existing = read_json(out / trial_name(task_dir, cwd, attempt) / "result.json")
        if isinstance(existing, dict) and (existing.get("runner_command") != template
                                           or existing.get("task_checksum") != dir_digest(task_dir)
                                           or existing.get("runner_id", "native") != runner_id):
            found.append(trial_name(task_dir, cwd, attempt))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tests", nargs="+", required=True, help="test directories (each with task.toml)")
    parser.add_argument("--out", required=True, help="run directory, for example relai/work/runs/<run-id>")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--first-attempt", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=3600.0, help="seconds per trial")
    parser.add_argument("--cwd", default=".", help="working directory for the command")
    parser.add_argument("--pass-env", nargs="*", default=[], help="variable names the agent needs")
    parser.add_argument("--retry-failed", action="store_true", help="rerun trials that recorded a runtime failure")
    parser.add_argument("--runner-id", default="native", help="name of this runner; comparisons need the same id")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- then the per-trial command")
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("give the per-trial command after --")
    if args.attempts < 1 or args.first_attempt < 1 or args.concurrency < 1 or args.timeout <= 0:
        parser.error("attempts, first-attempt, concurrency and timeout must be positive")
    tasks = list(dict.fromkeys(Path(raw).resolve() for raw in args.tests))  # duplicates would share a trial
    missing = [str(t) for t in tasks if not (t / "task.toml").is_file()]
    if missing:
        parser.error("no task.toml in: " + ", ".join(missing))
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cwd = Path(args.cwd).resolve()
    env = {k: os.environ[k] for k in (*BASE_ENV, *args.pass_env) if k in os.environ}
    status = git(cwd, "status", "--porcelain")
    meta = {"runner": "native", "runner_id": args.runner_id, "runner_command": shlex.join(command), "cwd": str(cwd),
            "git_head": git(cwd, "rev-parse", "HEAD"), "git_dirty": None if status is None else bool(status),
            "started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pass_env": args.pass_env,
            "attempts": args.attempts, "first_attempt": args.first_attempt, "timeout_sec": args.timeout}
    jobs = [(t, a) for t in tasks for a in range(args.first_attempt, args.first_attempt + args.attempts)]
    if any((out / trial_name(t, cwd, a)).is_symlink() for t, a in jobs):
        parser.error("trial directories must not be symlinks")
    clash = conflicts(jobs, out, cwd, meta["runner_command"], args.runner_id)
    if clash:
        print(f"error: {', '.join(clash)} was run with a different command or test version, or runner identity; use a new --out",
              file=sys.stderr)
        return 2
    cancelled = threading.Event()
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        try:
            results = list(pool.map(lambda job: run_trial(job[0], job[1], out, command, cwd, args.timeout, env,
                                                          args.retry_failed, meta, cancelled), jobs))
        except KeyboardInterrupt:
            cancelled.set()
            raise
    trials = [read_json(p) for p in sorted(out.glob("*/result.json"))]
    trials = [t for t in trials if isinstance(t, dict) and "trial_name" in t]
    errored = sum(1 for t in trials if failed(t))
    previous = read_json(out / "result.json") or {}
    summary = {"runner": "native", "runner_id": args.runner_id, "runner_command": meta["runner_command"],
               "n_total_trials": len(trials),
               "stats": {"n_errored_trials": errored, "n_completed_trials": len(trials) - errored},
               "batches": (previous.get("batches") or []) + [meta]}
    (out / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} trial(s) this batch; {len(trials)} in {out}: {len(trials) - errored} completed, "
          f"{errored} errored. Summarize with: python3 relai/bin/summarize.py {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
