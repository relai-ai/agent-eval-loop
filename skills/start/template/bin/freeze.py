#!/usr/bin/env python3
"""Freeze tests before their first real run, so they cannot be tuned to the agent's results.

Usage:
  python3 relai/bin/freeze.py relai/tests/<id> [...]                  freeze new tests
  python3 relai/bin/freeze.py relai/tests/<id> --reason "why"          re-freeze a changed test
  python3 relai/bin/freeze.py --check [relai/tests/<id> ...]            report state, write nothing
  python3 relai/bin/freeze.py relai/tests/<id> --begin-repair --reason "why"   open an agreed repair

Records each test's digest (every file except README.md) in relai/frozen.json, keyed by its
path relative to relai/ (tests/<id>, benchmarks/<id>/cases/<case>), with a
history of re-freezes and their reasons. Re-freezing a changed test requires --reason;
record the same reason in relai/decisions.md and get a fresh review of the change.
--begin-repair records an agreed repair as open, so editing hooks stop asking before each edit of
that test; re-freezing it (or freezing it unchanged) closes the repair.
This script writes only relai/frozen.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import dir_digest, relai_root, frozen_state, test_key  # noqa: E402


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
            print(f"error: {task} has no task.toml")
            status = 1
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
                status = 1
            continue
        if args.begin_repair:
            if not entry:
                print(f"error: {key} is not frozen; there is nothing to repair", file=sys.stderr)
                status = 1
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
                  "(and a note in decisions.md plus a fresh review)")
            status = 1
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
