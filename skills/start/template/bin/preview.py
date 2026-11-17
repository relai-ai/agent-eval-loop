#!/usr/bin/env python3
"""Grader check before freezing: score one test's graders on prepared cases and record the round.

Usage:
  python3 relai/bin/preview.py relai/tests/<id> <case dir> [<case dir> ...] [--evaluators a,b] [--judge] [--dry-run]

Each case dir holds what a trial would export to /logs/agent: at least trajectory.json (a synthetic
passing, failing or empty reply, or a real recorded run), plus any state the verifier reads. Its
name is the case label. The task's verifier runs once per case in a container (as check_task.py
--verifier does), and with --judge each judge evaluator is scored with relai/bin/judge.py, which
calls the model in relai.toml [judge] and appends each call to records/spend.jsonl. --dry-run prints each judge's input size and
estimated cost instead of calling a model. --evaluators limits the round to the listed evaluator
ids, for a fix-and-recheck of one grader. Every round is appended to
records/eval/<date>-grader-preview.md with the digest of the test's tests/ directory and of each
judge rubric, so the round that was approved can be matched to the grader that was frozen.
Exit status: 0 recorded, 1 a case could not be scored, 2 a usage error.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    Report, declared_evaluators, dir_digest, evals_config, file_sha256, load_json, load_toml, relai_root,
    secret_values, test_key,
)
from check_task import verifier_image, verify_case


def first_line(text) -> str:
    lines = str(text or "").strip().splitlines()
    return (lines[0][:160] if lines else "").replace("|", "\\|")


def digests(task: Path, evaluators: list[dict]) -> list[str]:
    found = [f"tests/ {dir_digest(task / 'tests')[:12]}"] if (task / "tests").is_dir() else []
    for ev in evaluators:
        rubric = task / str(ev.get("rubric", ""))
        if ev.get("type") == "judge" and rubric.is_file():
            found.append(f"{ev['id']} rubric {file_sha256(rubric)[:12]}")
    return found


def load_judge(relai: Path):
    if not (relai / "bin" / "judge.py").is_file():
        return None
    sys.path.insert(0, str(relai / "bin"))
    import judge
    return judge


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task")
    parser.add_argument("cases", nargs="+")
    parser.add_argument("--evaluators", help="comma-separated evaluator ids to include (default: all)")
    parser.add_argument("--judge", action="store_true", help="also score judge evaluators with relai/bin/judge.py")
    parser.add_argument("--dry-run", action="store_true", help="estimate judge input size and cost; call no model")
    parser.add_argument("--relai-dir")
    args = parser.parse_args()
    relai = relai_root(args.relai_dir)
    task = Path(args.task).resolve()
    if not (task / "task.toml").is_file():
        print(f"error: {task} has no task.toml", file=sys.stderr)
        return 2
    cases = [Path(c).resolve() for c in args.cases]
    missing = [str(c) for c in cases if not (c / "trajectory.json").is_file()]
    if missing:
        print(f"error: each case dir needs a trajectory.json: {', '.join(missing)}", file=sys.stderr)
        return 2
    config = load_toml(task / "task.toml")
    evaluators = declared_evaluators(config)
    if args.evaluators:
        wanted = {e.strip() for e in args.evaluators.split(",") if e.strip()}
        unknown = wanted - {ev.get("id") for ev in evaluators}
        if unknown:
            print(f"error: not declared in task.toml: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        evaluators = [ev for ev in evaluators if ev.get("id") in wanted]
    codes = [ev for ev in evaluators if ev.get("type") == "code"]
    judges = [ev for ev in evaluators if ev.get("type") == "judge"]
    judge = None
    if judges and (args.judge or args.dry_run):
        judge = load_judge(relai)
        if judge is None:
            print("error: --judge and --dry-run need relai/bin/judge.py (eval: harness)", file=sys.stderr)
            return 2
        judge_config = evals_config(relai).get("judge", {}) or {}
        if judge_config.get("mode") == "subagent":
            print("error: relai.toml [judge].mode is 'subagent': score judges with a fresh subagent instead",
                  file=sys.stderr)
            return 2
        secrets = secret_values(relai)
    report = Report()
    reads_verifier = any(str(i).startswith("verifier/") for ev in judges for i in (ev.get("inputs") or []))
    found = verifier_image(task, config, report) if codes or (reads_verifier and judge is not None) else None
    rows, failed = [], False
    work = relai / "work" / "preview" / task.name
    for case in cases:
        keep = work / case.name / "verifier"
        shutil.rmtree(keep, ignore_errors=True)
        outputs = verify_case(task, config, *found, case.name, report, case, keep=keep) if found else None
        rewards, feedback, errors = outputs or ({}, {}, {})
        for ev in codes:
            ev_id = ev["id"]
            if ev_id in rewards:
                rows.append((ev_id, case.name, rewards[ev_id], first_line(feedback.get(ev_id))))
            else:
                failed = True
                rows.append((ev_id, case.name, "error", first_line(errors.get(ev_id) or "no score")))
        trajectory = load_json(case / "trajectory.json")
        for ev in judges:
            if judge is None:
                rows.append((ev["id"], case.name, "not run", "pass --judge to score judges"))
            elif args.dry_run:
                try:
                    prompt, _ = judge.build_prompt(judge_config, relai, task, ev, trajectory, secrets, work / case.name)
                    est = judge.estimate(judge_config, relai, prompt)
                    cost = est["input_cost_usd_estimate"]
                    rows.append((ev["id"], case.name, "dry run", f"{est['input_chars']} chars, about "
                                 f"{est['input_tokens_estimate']} tokens, input cost "
                                 f"{'unknown' if cost is None else f'${cost:.4f}'}"))
                except (OSError, ValueError) as exc:
                    failed = True
                    rows.append((ev["id"], case.name, "error", first_line(judge.redact(str(exc), secrets))))
            else:
                result = judge.judge_one(judge_config, relai, task, ev, trajectory, secrets, work / case.name,
                                         ledger=True)
                if "error" in result:
                    failed = True
                    rows.append((ev["id"], case.name, "error", first_line(result["error"])))
                else:
                    rows.append((ev["id"], case.name, result["score"], first_line(result["feedback"])))
    for message in report.errors + report.warnings:
        print(f"note: {message}", file=sys.stderr)
    out = relai / "records" / "eval" / f"{date.today().isoformat()}-grader-preview.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"\n## {test_key(task, relai)} · round recorded {date.today().isoformat()}"
             + (" (dry run)" if args.dry_run else ""),
             "Graders: " + " · ".join(digests(task, evaluators)), "",
             "| Evaluator | Case | Score | Feedback (first line) |", "| --- | --- | --- | --- |"]
    lines += [f"| {e} | {c} | {s} | {f} |" for e, c, s, f in rows]
    with out.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\n".join(lines[1:]))
    print(f"\nAppended to {out.relative_to(relai.parent) if out.is_relative_to(relai.parent) else out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
