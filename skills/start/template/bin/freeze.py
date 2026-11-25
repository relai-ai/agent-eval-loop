#!/usr/bin/env python3
"""Freeze tests before their first real run, so they cannot be tuned to the agent's results.

Usage:
  python3 relai/bin/freeze.py relai/tests/<id> [...]                  freeze new tests
  python3 relai/bin/freeze.py relai/tests/<id> --reason "why"          re-freeze a changed test
  python3 relai/bin/freeze.py --check [relai/tests/<id> ...]            report state, write nothing
  python3 relai/bin/freeze.py relai/tests/<id> --begin-repair --reason "why"   open an agreed repair
  python3 relai/bin/freeze.py relai/tests/<id> --require-controls [--controls PATH ...] [--reason "why"]

Records each test's digest (every file except README.md) in relai/frozen.json, keyed by its
path relative to relai/ (tests/<id>, benchmarks/<id>/cases/<case>), with a
history of re-freezes and their reasons. Re-freezing a changed test requires --reason;
record the same reason in relai/decisions.md and get a fresh review of the change.
--begin-repair records a repair as open, so editing hooks stop asking before each edit of that
test; re-freezing it (or freezing it unchanged) closes the repair. Run it only after the repair
is agreed and recorded in relai/decisions.md, never to avoid asking.
--require-controls refuses to freeze a test whose controls have not passed on its current files. By default
it reads controls.py's record (relai/work/controls/<key>.json): it must name the current digest, be complete
and pass. --controls PATH (repeatable) names that record elsewhere, or Harbor job folders holding oracle and
nop trials of the test (on Modal, say): an oracle trial without an exception and with every code check at
its max_score, and a nop trial with the primary check at its min_score, both started after the test's files
last changed.
This script writes only relai/frozen.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    controls_record, declared_evaluators, dir_digest, load_json, load_toml, relai_root, frozen_state, setup_run,
    test_key,
)


def newest_change(task: Path) -> datetime:
    times = [p.stat().st_mtime for p in task.rglob("*") if p.is_file() and p != task / "README.md"]
    return datetime.fromtimestamp(max(times or [0.0]), timezone.utc)


def harbor_controls(task: Path, folders: list[Path]) -> str | None:
    """Why the oracle and nop trials of this task under these Harbor job folders do not clear it, or None."""
    toml = load_toml(task / "task.toml")
    code = [ev for ev in declared_evaluators(toml) if ev.get("type") == "code"]
    primary = ((toml.get("metadata", {}).get("relai", {}) or {}).get("coding") or {}).get("primary")
    changed = newest_change(task)
    found: dict = {}
    for folder in folders:
        for path in [folder / "result.json", *folder.glob("*/result.json"), *folder.glob("*/*/result.json")]:
            try:
                result = load_json(path)
            except (OSError, ValueError):
                continue
            if not isinstance(result, dict) or "trial_name" not in result or result.get("task_name") != task.name:
                continue
            agent = (result.get("agent_info") or {}).get("name")
            if agent in ("oracle", "nop"):
                found.setdefault(agent, []).append(result)
    problems = []
    for agent in ("oracle", "nop"):
        trials = found.get(agent) or []
        if not trials:
            problems.append(f"no {agent} trial of {task.name}")
            continue
        latest = max(trials, key=lambda r: str(r.get("started_at") or ""))
        try:
            started = datetime.fromisoformat(str(latest.get("started_at")).replace("Z", "+00:00"))
        except ValueError:
            started = None
        rewards = ((latest.get("verifier_result") or {}).get("rewards") or {})
        if started is None or started < changed:
            problems.append(f"the latest {agent} trial started before the test's files last changed "
                            f"({changed:%Y-%m-%d %H:%M} UTC)")
        elif latest.get("exception_info"):
            problems.append(f"the {agent} trial raised {(latest['exception_info'] or {}).get('exception_type')}")
        elif agent == "oracle":
            short = [ev["id"] for ev in code if rewards.get(ev["id"]) != ev.get("max_score", 1.0)]
            if short:
                problems.append(f"the oracle scored below full marks on {', '.join(short)}")
        elif rewards.get(primary) != next((ev.get("min_score", 0.0) for ev in code if ev["id"] == primary), 0.0):
            problems.append(f"the nop scored {rewards.get(primary)} on the primary check {primary}")
    return "; ".join(problems) or None


def controls_problem(task: Path, relai_dir: Path, key: str, digest: str, sources: list[str]) -> str | None:
    """Why the test's controls do not clear it for freezing, or None when they do."""
    paths = [Path(s).resolve() for s in sources] or [controls_record(relai_dir, key)]
    folders = [p for p in paths if p.is_dir()]
    if folders:
        problem = harbor_controls(task, folders)
        if problem:
            return f"Harbor controls: {problem}"
    for path in [p for p in paths if not p.is_dir()]:
        try:
            record = load_json(path)
        except (OSError, ValueError):
            return f"no controls record at {path}: run controls.py on the test first"
        if record.get("task") != key or record.get("digest") != digest:
            return f"{path} was recorded for {record.get('task')} at digest {str(record.get('digest'))[:12]}, " \
                   f"not the current files ({digest[:12]}): rerun controls.py"
        if record.get("partial"):
            return f"{path} records a partial run (--only); run every control"
        failed = [c.get("id") for c in record.get("controls") or [] if not c.get("ok")]
        if failed or not record.get("ok"):
            return f"controls failed: {', '.join(map(str, failed)) or 'see ' + str(path)}"
    return None


def all_tests(relai_dir: Path) -> list[Path]:
    return sorted(p.parent for kind in ("tests", "benchmarks")
                  for p in (relai_dir / kind).rglob("task.toml"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tasks", nargs="*", help="test directories")
    parser.add_argument("--reason", help="why a frozen test changed (required to re-freeze)")
    parser.add_argument("--check", action="store_true", help="report frozen, changed and unfrozen tests; write nothing")
    parser.add_argument("--begin-repair", action="store_true",
                        help="open an agreed repair of frozen tests (needs --reason); re-freezing closes it")
    parser.add_argument("--require-controls", action="store_true",
                        help="refuse to freeze unless the test's controls passed on its current files")
    parser.add_argument("--controls", action="append", default=[], metavar="PATH",
                        help="a controls.py record or Harbor job folders with oracle and nop trials (implies "
                             "--require-controls)")
    parser.add_argument("--relai-dir")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir)
    state = frozen_state(relai_dir)
    tests = state.setdefault("tests", {})
    tasks = [Path(t).resolve() for t in args.tasks] or (all_tests(relai_dir) if args.check else [])
    if not tasks:
        parser.error("name the test directories to freeze")
    if args.begin_repair and (args.check or not args.reason or not args.tasks):
        parser.error("--begin-repair needs the test directories and --reason, and cannot be combined with --check")

    status = 0
    changed_state = False
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for task in tasks:
        if not (task / "task.toml").is_file():
            print(f"error: {task} has no task.toml", file=sys.stderr)
            status = 2
            continue
        if setup_run(task):
            print(f"error: {task} is a run copy built by apply_setup.py; freeze the test it was built from",
                  file=sys.stderr)
            status = 2
            continue
        key = test_key(task, relai_dir)
        digest = dir_digest(task)
        entry = tests.get(key)
        if args.check:
            label = "unfrozen" if not entry else ("frozen" if entry["digest"] == digest else "CHANGED since frozen")
            if entry and entry.get("repair"):
                label += f" (repair open: {entry['repair'].get('reason', '')})"
            print(f"{key}: {label}")
            if entry and entry["digest"] != digest:
                status = max(status, 1)
            continue
        if args.begin_repair:
            if not entry:
                print(f"error: {key} is not frozen; there is nothing to repair", file=sys.stderr)
                status = 2
                continue
            entry["repair"] = {"reason": args.reason, "since": now}
            changed_state = True
            print(f"{key}: repair open; re-freeze with --reason when done")
            continue
        if entry and entry["digest"] == digest:
            if entry.pop("repair", None):
                changed_state = True
                print(f"{key}: unchanged; repair closed")
            else:
                print(f"{key}: already frozen, unchanged")
            continue
        if entry and not args.reason:
            print(f"error: {key} changed since it was frozen on {entry['frozen_at']}; re-freezing needs --reason "
                  "(and a note in decisions.md plus a fresh review)", file=sys.stderr)
            status = max(status, 1)
            continue
        if args.require_controls or args.controls:
            problem = controls_problem(task, relai_dir, key, digest, args.controls)
            if problem:
                print(f"error: {key} not frozen: {problem}", file=sys.stderr)
                status = max(status, 1)
                continue
        history = (entry or {}).get("history", [])
        history.append({"digest": digest, "at": now, "reason": args.reason or "first freeze"})
        tests[key] = {"digest": digest, "frozen_at": now, "history": history}
        changed_state = True
        print(f"{key}: frozen ({digest[:12]})")

    if changed_state:
        path = relai_dir / "frozen.json"
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
