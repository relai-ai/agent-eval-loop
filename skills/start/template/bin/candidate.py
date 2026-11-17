#!/usr/bin/env python3
"""Candidates in improve: create a candidate worktree, or print its decision card against the current version.

Usage:
  python3 relai/bin/candidate.py new <name> [--repo DIR] [--from REF]
  python3 relai/bin/candidate.py compare <name> --baseline <run> [...] --candidate <run> [...] [--targets a,b] [--json]

new creates a git worktree of the agent's repository (default: the repository holding relai/) at
work/candidates/<name>/ on a branch named <name>, from REF (default HEAD), so candidates never touch
the user's working tree. compare summarizes both sides with summarize.py and prints one card:
targets (from --targets, else "targets" in records/improve/plan.json; other matched tests are
guardrails), each test's change and whether it is within noise, and agent cost on each side. It
adds a notice, not a verdict, when a target's improvement is within noise or rests on a single
scored attempt, or when any test dropped. summarize.py --baseline gives the full comparison.
Exit status: 0 done, 1 git failed or no comparable tests, 2 a usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_json, relai_root, repo_root
from summarize import compare, comparison_warnings, summarize


def new(relai: Path, name: str, repo: Path, ref: str) -> int:
    target = relai / "work" / "candidates" / name
    if target.exists():
        print(f"error: {target} already exists", file=sys.stderr)
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    made = subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", name, str(target), ref],
                          capture_output=True, text=True)
    if made.returncode:
        print(f"error: git worktree add failed: {made.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"Candidate {name}: worktree {target} on branch {name} from {ref}")
    return 0


def targets_from_plan(relai: Path) -> list[str]:
    path = relai / "records" / "improve" / "plan.json"
    try:
        plan = load_json(path) if path.is_file() else {}
    except (OSError, ValueError):
        return []
    found = plan.get("targets") if isinstance(plan, dict) else None
    return [str(t) for t in found] if isinstance(found, list) else []


def matches(test: str, targets: list[str]) -> bool:
    return any(test == t or test.endswith("/" + t) for t in targets)


def run_cost(summary: dict) -> dict:
    trials = [t for test in summary["tests"].values() for t in test.get("trials", [])]
    costs = [(t.get("usage") or {}).get("cost_usd") for t in trials]
    costs = [c for c in costs if isinstance(c, (int, float))]
    return {"usd": sum(costs) if costs else None, "reported": len(costs), "attempts": len(trials)}


def card(name: str, base: dict, cand: dict, targets: list[str]) -> dict:
    comparison = compare(base, cand)
    rows = comparison["rows"]
    for row in rows:
        row["role"] = "target" if matches(row["test"], targets) else "guardrail"
    notices = list(comparison_warnings(base, cand))
    for side in ("baseline only", "candidate only"):
        if comparison[side]:
            notices.append(f"{side} (not compared): {', '.join(comparison[side])}")
    for row in rows:
        if row["delta"] is None:
            notices.append(f"{row['test']}: not comparable (no scored attempt on a side)")
        elif row["role"] == "target" and row["delta"] > 0 and row["within_noise"]:
            notices.append(f"{row['test']}: the improvement is within noise")
        elif row["role"] == "target" and row["delta"] > 0 and row["within_noise"] is None:
            notices.append(f"{row['test']}: the improvement rests on a single scored attempt on a side")
        elif row["delta"] < 0:
            notices.append(f"{row['test']}: {row['role']} dropped" + (" (within noise)" if row["within_noise"] else ""))
    return {"candidate": name, "targets": targets, "rows": rows, "notices": notices,
            "agent_cost_usd": {"baseline": run_cost(base), "candidate": run_cost(cand)}}


def show(result: dict) -> None:
    def num(value):
        return "-" if value is None else f"{value:.2f}"
    print(f"Candidate {result['candidate']} vs current version")
    for row in sorted(result["rows"], key=lambda r: r["role"] != "target"):
        noise = {True: "within noise", False: "beyond noise", None: "noise unknown"}[row["within_noise"]]
        delta = "-" if row["delta"] is None else f"{row['delta']:+.2f}"
        print(f"  {row['role']:<9} {row['test']}: {num(row['baseline'])} -> {num(row['candidate'])} ({delta}, {noise}, "
              f"attempts {row['attempts']})")
    base, cand = result["agent_cost_usd"]["baseline"], result["agent_cost_usd"]["candidate"]
    line = f"  agent cost: {num(base['usd'])} -> {num(cand['usd'])}"
    complete = all(side["reported"] == side["attempts"] for side in (base, cand))
    if base["usd"] and cand["usd"] is not None and complete:
        line += f" ({(cand['usd'] / base['usd'] - 1) * 100:+.0f}%)"
    if not complete:
        line += (f" (reported for {base['reported']}/{base['attempts']} and {cand['reported']}/{cand['attempts']} "
                 "attempts, so not comparable)")
    print(line)
    for notice in result["notices"]:
        print(f"Notice: {notice}")
    if not result["targets"]:
        print("Notice: no targets named (--targets or plan.json \"targets\"); every test is shown as a guardrail")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("new")
    make.add_argument("name")
    make.add_argument("--repo", help="the agent's git repository (default: the one holding relai/)")
    make.add_argument("--from", dest="ref", default="HEAD")
    make.add_argument("--relai-dir")
    check = sub.add_parser("compare")
    check.add_argument("name")
    check.add_argument("--baseline", nargs="+", required=True)
    check.add_argument("--candidate", nargs="+", required=True)
    check.add_argument("--targets", help="comma-separated target test ids (default: plan.json \"targets\")")
    check.add_argument("--json", action="store_true")
    check.add_argument("--relai-dir")
    args = parser.parse_args()
    relai = relai_root(args.relai_dir)
    if args.command == "new":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.name):
            print("error: name a candidate with letters, digits, '.', '_' or '-'", file=sys.stderr)
            return 2
        return new(relai, args.name, Path(args.repo).resolve() if args.repo else repo_root(relai), args.ref)
    base = summarize([Path(p) for p in args.baseline], relai)
    cand = summarize([Path(p) for p in args.candidate], relai)
    targets = [t.strip() for t in args.targets.split(",") if t.strip()] if args.targets else targets_from_plan(relai)
    result = card(args.name, base, cand, targets)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        show(result)
    return 0 if result["rows"] else 1


if __name__ == "__main__":
    sys.exit(main())
