#!/usr/bin/env python3
"""Run every (task, agent) pair of a coding-agent run through Harbor, resuming after a restart.

Usage:
  python3 relai/bin/run_queue.py relai/work/runs/<run-id> init --tasks relai/tests/<id> [...] --agents <id>[,<id>...]
          [--attempts 1] [--env docker] [--parallel 1] [--max-retries 1] [--harbor-arg ARG ...]
  python3 relai/bin/run_queue.py relai/work/runs/<run-id> run [--dry-run] [--harbor CMD]
  python3 relai/bin/run_queue.py relai/work/runs/<run-id> status

`init` writes <run dir>/queue.json: the tasks, the agents (ids of [[coding_evals.agents]] in relai.toml), the
attempts per pair and the Harbor settings. `run` starts one Harbor job per pair that still lacks finished
trials, --parallel pairs at a time, as `harbor run -e <env> -p <task> -a <agent> -m <model> --ak version=<v>
-o <run dir> --job-name <task>__<agent>[__retry<N>] -k <missing attempts> -n <same> --yes --quiet <harbor args>`
through `uv tool run --from harbor==<[harbor].version>` (or --harbor CMD). The credentials an agent's `env`
names reach Harbor through its environment, from the environment or relai/.env, never on its command line.

The job folders are the record: a trial counts as finished once its result.json exists, unless it crashed
before verification (an exception and no verifier result), which counts as missing until the pair has used
--max-retries retry jobs. An attempt with no result.json at all (its job was killed) is missing until it
runs. So a queue that was killed, or whose machine restarted, resumes with `run`: pairs with all trials
finished are skipped, a job interrupted mid-trial is left as it is, and only the missing attempts run again
in a new job beside it. One `run` starts each pair at most 1 + --max-retries times. queue.json records each job's process; `run` waits for one that
is still alive instead of starting it twice, and a lock keeps two queues off one run directory. `status`
prints each pair's finished, missing and running trials. It calls models only through the agents Harbor runs.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import evals_config, harbor_version, load_json, relai_root, secret_values, test_key

POLL_SECONDS = 15


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def alive(pid) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def trial_results(run_dir: Path, jobs: list[str]) -> list[dict]:
    """Every trial result.json under the pair's job folders."""
    results = []
    for job in jobs:
        for path in sorted((run_dir / job).glob("*/result.json")):
            try:
                data = load_json(path)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and "trial_name" in data:
                results.append(data)
    return results


def crashed(result: dict) -> bool:
    return bool(result.get("exception_info")) and result.get("verifier_result") is None


def pair_state(run_dir: Path, item: dict, attempts: int, max_retries: int) -> dict:
    """A pair's attempts from its job folders on disk: finished, missing (absent results, plus crashed trials
    while a retry is left), crashed, absent (no result.json at all, as when a job was killed) and whether a
    crash may still be retried."""
    jobs = item.get("jobs") or []
    results = trial_results(run_dir, jobs)
    kept = [r for r in results if not crashed(r)]
    crashes = len(results) - len(kept)
    retry_left = len(jobs) <= max_retries
    finished = len(kept) + (0 if retry_left else crashes)
    return {"finished": min(finished, attempts), "missing": max(attempts - finished, 0), "crashed": crashes,
            "absent": max(attempts - len(results), 0), "retry_left": retry_left}


class Queue:
    def __init__(self, run_dir: Path, relai_dir: Path):
        self.run_dir, self.relai_dir = run_dir, relai_dir
        self.path = run_dir / "queue.json"

    def load(self) -> dict:
        if not self.path.is_file():
            raise SystemExit(f"error: {self.path} does not exist; start with `run_queue.py {self.run_dir} init`")
        return load_json(self.path)

    def save(self, state: dict) -> None:
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.path)


def agents_by_id(relai_dir: Path) -> dict:
    rows = (evals_config(relai_dir).get("coding_evals") or {}).get("agents") or []
    return {row.get("id"): row for row in rows if isinstance(row, dict) and row.get("id")}


def init(args, queue: Queue) -> int:
    if queue.path.exists():
        raise SystemExit(f"error: {queue.path} exists; `run` resumes it, or choose a new run directory")
    agents = agents_by_id(queue.relai_dir)
    wanted = [a for a in args.agents.split(",") if a]
    unknown = [a for a in wanted if a not in agents]
    if unknown or not wanted:
        raise SystemExit(f"error: agents {unknown or wanted} are not ids of [[coding_evals.agents]] in relai.toml")
    for agent in wanted:
        if not agents[agent].get("agent"):
            raise SystemExit(f"error: [[coding_evals.agents]] {agent} has no Harbor agent name (agent = ...)")
    tasks = []
    for raw in args.tasks:
        task = Path(raw).resolve()
        if not (task / "task.toml").is_file():
            raise SystemExit(f"error: {raw} is not a task directory")
        tasks.append(task)
    if not harbor_version(queue.relai_dir):
        raise SystemExit("error: relai.toml [harbor].version is not set; record the Harbor release first")
    items = [{"task": str(task), "key": test_key(task, queue.relai_dir), "agent": agent, "jobs": []}
             for task in tasks for agent in wanted]
    queue.run_dir.mkdir(parents=True, exist_ok=True)
    queue.save({"created": now(), "attempts": args.attempts, "env": args.env, "parallel": args.parallel,
                "max_retries": args.max_retries, "harbor_args": args.harbor_arg or [], "items": items})
    print(f"queued {len(items)} pair(s): {len(tasks)} task(s) x {len(wanted)} agent(s) in {queue.path}")
    return 0


def job_name(item: dict) -> str:
    base = f"{Path(item['task']).name}__{item['agent']}"
    count = len(item.get("jobs") or [])
    return base if count == 0 else f"{base}__retry{count}"


def harbor_command(state: dict, item: dict, agent: dict, job: str, missing: int, run_dir: Path, base: list) -> list:
    command = [*base, "run", "-e", state["env"], "-p", item["task"], "-a", agent["agent"]]
    if agent.get("model"):
        command += ["-m", agent["model"]]
    if agent.get("version"):
        command += ["--ak", f"version={agent['version']}"]
    return command + ["-o", str(run_dir), "--job-name", job, "-k", str(missing), "-n", str(missing),
                      "--yes", "--quiet", *state.get("harbor_args", [])]


def harbor_env(relai_dir: Path, agent: dict) -> dict:
    env = {**os.environ, "HARBOR_TELEMETRY": "0"}
    stored = secret_values(relai_dir)
    for name in agent.get("env") or []:
        if name not in env and name in stored:
            env[name] = stored[name]
    return env


def run(args, queue: Queue) -> int:
    state = queue.load()
    agents = agents_by_id(queue.relai_dir)
    version = harbor_version(queue.relai_dir)
    base = shlex.split(args.harbor) if args.harbor else \
        ["uv", "tool", "run", "--python", "3.12", "--from", f"harbor=={version}", "harbor"]
    logs = queue.run_dir / "queue-logs"
    logs.mkdir(exist_ok=True)
    running: dict = {}
    starts: dict = {}
    failures = 0
    while True:
        for index, item in enumerate(state["items"]):
            pid = (item.get("running") or {}).get("pid")
            if index in running or not pid:
                continue
            if alive(pid):
                running[index] = None
            else:
                item.pop("running", None)
        for index, proc in list(running.items()):
            item = state["items"][index]
            pid = (item.get("running") or {}).get("pid")
            done = proc.poll() is not None if proc is not None else not alive(pid)
            if done:
                code = proc.returncode if proc is not None else None
                item.pop("running", None)
                item.setdefault("history", []).append({"job": item["jobs"][-1], "ended": now(), "exit": code})
                del running[index]
                counts = pair_state(queue.run_dir, item, state["attempts"], state["max_retries"])
                print(f"{item['key']} {item['agent']}: job {item['jobs'][-1]} ended (exit {code}); "
                      f"{counts['finished']}/{state['attempts']} finished", flush=True)
        queue.save(state)
        pending = []
        for index, item in enumerate(state["items"]):
            if index in running:
                continue
            counts = pair_state(queue.run_dir, item, state["attempts"], state["max_retries"])
            if counts["missing"] and starts.get(index, 0) <= state["max_retries"] \
                    and (counts["absent"] or counts["retry_left"]):
                pending.append((index, counts))
        if not pending and not running:
            break
        if args.dry_run:
            for index, counts in pending:
                item = state["items"][index]
                print(f"would run {item['key']} {item['agent']} as {job_name(item)}: {counts['missing']} missing")
            return 0
        while pending and len(running) < max(state.get("parallel", 1), 1):
            index, counts = pending.pop(0)
            item = state["items"][index]
            agent = agents.get(item["agent"])
            if agent is None:
                print(f"error: agent {item['agent']} is no longer in relai.toml; skipping {item['key']}")
                failures += 1
                item["skipped"] = "agent removed from relai.toml"
                continue
            job = job_name(item)
            command = harbor_command(state, item, agent, job, counts["missing"], queue.run_dir, base)
            log = (logs / f"{job}.log").open("a", encoding="utf-8")
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                    env=harbor_env(queue.relai_dir, agent), start_new_session=True)
            item["jobs"].append(job)
            starts[index] = starts.get(index, 0) + 1
            item["running"] = {"pid": proc.pid, "job": job, "started": now()}
            running[index] = proc
            queue.save(state)
            print(f"{item['key']} {item['agent']}: started {job} ({counts['missing']} attempt(s))", flush=True)
        if running:
            time.sleep(args.poll)
    rows = [pair_state(queue.run_dir, item, state["attempts"], state["max_retries"]) for item in state["items"]]
    incomplete = sum(1 for r in rows if r["missing"])
    print(f"{len(rows) - incomplete} of {len(rows)} pair(s) finished; {incomplete} still missing trials")
    return 1 if incomplete or failures else 0


def status(args, queue: Queue) -> int:
    state = queue.load()
    incomplete = 0
    for item in state["items"]:
        counts = pair_state(queue.run_dir, item, state["attempts"], state["max_retries"])
        pid = (item.get("running") or {}).get("pid")
        label = "running" if alive(pid) else ("done" if not counts["missing"] else "missing")
        incomplete += label != "done"
        print(f"{label:8} {item['key']} {item['agent']}: {counts['finished']}/{state['attempts']} finished, "
              f"{counts['crashed']} crashed, {len(item.get('jobs') or [])} job(s)")
    return 1 if incomplete else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", help="the run directory, such as relai/work/runs/<run-id>")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("init", help="queue tasks x agents")
    start.add_argument("--tasks", nargs="+", required=True)
    start.add_argument("--agents", required=True, help="comma-separated [[coding_evals.agents]] ids")
    start.add_argument("--attempts", type=int, default=1)
    start.add_argument("--env", default="docker", help="Harbor's -e environment (docker, podman, modal, ...)")
    start.add_argument("--parallel", type=int, default=1, help="pairs run at once")
    start.add_argument("--max-retries", type=int, default=1,
                       help="retry jobs per pair for trials that crashed before verification")
    start.add_argument("--harbor-arg", action="append", help="one more argument for every harbor run (repeatable)")
    go = sub.add_parser("run", help="run or resume")
    go.add_argument("--dry-run", action="store_true", help="print the jobs it would start")
    go.add_argument("--harbor", help="the command that runs Harbor (default: uv tool run harbor==[harbor].version)")
    go.add_argument("--poll", type=float, default=POLL_SECONDS, help=argparse.SUPPRESS)
    sub.add_parser("status", help="show each pair's trials")
    parser.add_argument("--relai-dir")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir)
    queue = Queue(Path(args.run_dir).resolve(), relai_dir)
    if args.command == "init":
        if args.attempts < 1 or args.parallel < 1 or args.max_retries < 0:
            parser.error("--attempts and --parallel must be at least 1, --max-retries at least 0")
        return init(args, queue)
    if args.command == "status":
        return status(args, queue)
    queue.run_dir.mkdir(parents=True, exist_ok=True)
    with (queue.run_dir / "queue.lock").open("w") as lock:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass
        except OSError:
            raise SystemExit(f"error: another run_queue.py is running on {queue.run_dir}")
        return run(args, queue)


if __name__ == "__main__":
    sys.exit(main())
