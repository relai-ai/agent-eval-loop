#!/usr/bin/env python3
"""Write relai/STATUS.json from the records and print the plain-text status every board opens with.

Usage:
  python3 relai/bin/status.py [--stage <skill> <n>] [--plan-step TEXT] [--json] [--relai-dir DIR]

Everything is read from records: wiki pages, frozen.json, changes.md, feedback.md, run folders
under work/ and records/spend.jsonl. The only value it keeps between runs is the active stage,
which --stage records (stage numbers and names match docs/board.md, Stages) and --plan-step
labels with the user's own plan step. It writes only STATUS.json, which is per person and not
committed. Missing costs are reported as unknown, never zero, and partly reported costs say how
many attempts reported one. Exit status: 0 written, 2 a usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import frozen_state, relai_root

SCHEMA_VERSION = 1
JOURNEY = ("start", "discover", "eval", "improve", "loop")
STAGES = {
    "discover": ["Scope", "Read sources", "Investigate", "Write wiki", "Review risks and questions", "Report"],
    "eval": ["Scope", "Scenarios", "Harness (first use)", "Build tests", "Grader check", "Independent review", "Freeze", "Run",
             "Judge checks and pass mark", "Report"],
    "eval-run": ["Select", "Cost", "Run", "Judge", "Report"],
    "improve": ["Agreement", "Diagnose", "Build candidate", "Measure", "Compare", "Keep or reject",
                "Independent review", "Deliver"],
    "loop": ["Gather evidence", "Discover", "Eval", "Improve", "Digest"],
    "coding-evals": ["Pick tasks", "Build", "Validate", "Independent review", "User sign-off", "Freeze", "Pilot run",
                     "Full run", "Report"],
    "review-app": ["Build or extend views", "The user reviews", "Write answers back"],
}
RISK_GLYPHS = {"proposed": ("○", "suspected"), "admitted": ("◐", "selected"), "confirmed": ("●", "confirmed"),
               "refined": ("◐", "narrowed"), "resolved": ("✓", "resolved"), "rejected": ("✗", "rejected"),
               "retired": ("✗", "retired")}
STATE_GLYPHS = {"done": "✓", "active": "◐", "started": "◐", "not started": "○"}
VERDICT = re.compile(r"\b(kept|accepted|rejected|not kept|left for review)\b", re.I)


def risks(relai: Path) -> list[dict]:
    items = []
    for page in sorted((relai / "wiki" / "risks").glob("*.md")):
        text = page.read_text(encoding="utf-8", errors="replace")
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), page.stem)
        match = re.search(r"^Status:\s*(\w+)", text, re.M)
        state = match.group(1).lower() if match else "proposed"
        glyph, plain = RISK_GLYPHS.get(state, ("○", state))
        items.append({"kind": "risk", "id": page.stem, "title": title, "state": state, "plain": plain,
                      "glyph": glyph})
    return items


def candidates(relai: Path) -> list[dict]:
    path = relai / "changes.md"
    if not path.is_file():
        return []
    found = []
    for entry in re.split(r"^## ", path.read_text(encoding="utf-8", errors="replace"), flags=re.M)[1:]:
        heading, _, body = entry.partition("\n")
        line = next((l for l in body.splitlines() if l.lower().startswith("verdict")), "")
        match = VERDICT.search(line) or VERDICT.search(heading)
        verdict = match.group(1).lower() if match else None
        glyph = {"kept": "✓", "accepted": "✓", "left for review": "◐"}.get(verdict, "✗" if verdict else "◐")
        date, _, title = heading.strip().partition(" · ")
        name = title.split(":", 1)[0].strip() if title else heading.strip()
        found.append({"name": name, "title": title.strip() or heading.strip(), "date": date,
                      "verdict": verdict, "glyph": glyph})
    return found


def pending_feedback(relai: Path) -> int:
    path = relai / "feedback.md"
    if not path.is_file():
        return 0
    return len(re.findall(r"^Status:\s*pending", path.read_text(encoding="utf-8", errors="replace"), re.M))


def open_questions(relai: Path) -> int:
    return len(list((relai / "wiki" / "open-questions").glob("*.md")))


def run_dirs(relai: Path) -> list[Path]:
    work = relai / "work"
    found = [p for p in (work / "runs").glob("*") if p.is_dir()]
    found += [p for p in work.glob("candidates/*/runs/*") if p.is_dir()]
    return sorted(found, key=lambda p: p.stat().st_mtime)


def run_summary(path: Path, relai: Path) -> dict:
    try:
        import summarize
        summary = summarize.summarize([path], relai)
    except Exception as exc:
        return {"run": str(path.relative_to(relai)), "error": f"{type(exc).__name__}: {exc}"}
    judges = summary.get("judge_usage") or {}
    trials = [t for test in summary.get("tests", {}).values() for t in test.get("trials", [])]
    costs = [(t.get("usage") or {}).get("cost_usd") for t in trials]
    costs = [c for c in costs if isinstance(c, (int, float))]
    return {"run": str(path.relative_to(relai)), "attempts": summary.get("trials", 0),
            "scored": (summary.get("status_counts") or {}).get("scored", 0),
            "agent_cost_usd": sum(costs) if costs else None, "agent_costs_reported": len(costs),
            "judge_cost_usd": judges.get("cost_usd"),
            "judge_calls": judges.get("calls", 0), "judge_costs_reported": judges.get("cost_reported", 0)}


def ledger(relai: Path) -> dict:
    path = relai / "records" / "spend.jsonl"
    total, entries, unknown = 0.0, 0, 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            entries += 1
            cost = entry.get("cost_usd")
            if isinstance(cost, (int, float)):
                total += cost
            else:
                unknown += 1
    return {"entries": entries, "cost_usd": round(total, 4) if entries > unknown else None, "unknown": unknown}


def journey(relai: Path, active: dict | None) -> list[dict]:
    frozen = frozen_state(relai).get("tests") or {}
    has = {
        "start": (relai / "README.md").is_file(),
        "discover": any(any((relai / "wiki" / kind).glob("*.md")) for kind in ("requirements", "risks", "open-questions")),
        "eval": bool(frozen) or any((relai / "tests").glob("*/task.toml")),
        "improve": (relai / "changes.md").is_file() or (relai / "records" / "improve" / "plan.json").is_file(),
        "loop": (relai / "records" / "loop" / "state.json").is_file(),
    }
    current = (active or {}).get("skill")
    current = "eval" if current == "eval-run" else current
    states = []
    for skill in JOURNEY:
        state = "active" if skill == current else "done" if has[skill] else "not started"
        states.append({"skill": skill, "state": state, "glyph": STATE_GLYPHS[state]})
    return states


def build(relai: Path, previous: dict, stage: tuple[str, int] | None, plan_step: str | None) -> dict:
    active = previous.get("active")
    if stage:
        skill, number = stage
        names = STAGES[skill]
        active = {"skill": skill, "stage": number, "of": len(names), "name": names[number - 1],
                  "user_plan_step": plan_step if plan_step is not None else (active or {}).get("user_plan_step"),
                  "since": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    elif plan_step is not None and active:
        active = {**active, "user_plan_step": plan_step}
    items = risks(relai)
    runs = [run_summary(path, relai) for path in run_dirs(relai)[-3:]]
    frozen = sorted((frozen_state(relai).get("tests") or {}).keys())
    waiting = []
    if open_questions(relai):
        waiting.append({"kind": "open question(s)", "count": open_questions(relai), "ref": "wiki/open-questions/"})
    if pending_feedback(relai):
        waiting.append({"kind": "feedback item(s)", "count": pending_feedback(relai), "ref": "feedback.md"})
    return {"schema_version": SCHEMA_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "generated_from": "relai records (wiki, frozen.json, changes.md, feedback.md, work/ runs, records/spend.jsonl)",
            "journey": journey(relai, active), "active": active, "items": items, "frozen_tests": frozen,
            "candidates": candidates(relai), "runs": runs, "waiting_on_user": waiting,
            "spend": {"ledger": ledger(relai), "runs": runs}}


def money(value) -> str:
    return "unknown" if value is None else f"${value:.2f}"


def render(status: dict) -> str:
    active = status.get("active")
    head = "RELAI"
    if active:
        head += f" · {active['skill']} {active['stage']}/{active['of']} · {active['name']}"
        if active.get("user_plan_step"):
            head += f" · {active['user_plan_step']}"
    lines = [head, " › ".join(f"{j['skill']} {j['glyph']}" for j in status["journey"])]
    if status["items"]:
        counts: dict[tuple[str, str], int] = {}
        for item in status["items"]:
            counts[(item["glyph"], item["plain"])] = counts.get((item["glyph"], item["plain"]), 0) + 1
        lines.append("Risks:  " + " · ".join(f"{g} {n} {p}" for (g, p), n in counts.items()))
    if status["frozen_tests"]:
        lines.append(f"Tests:  {len(status['frozen_tests'])} frozen")
    if status["candidates"]:
        lines.append("Candidates: " + " · ".join(f"{c['name']} {c['glyph']}" for c in status["candidates"]))
    for run in status["runs"][-1:]:
        if "error" in run:
            lines.append(f"Latest run: {run['run']} (could not summarize: {run['error']})")
        else:
            partial = run["agent_costs_reported"] < run["attempts"] and run["agent_cost_usd"] is not None
            lines.append(f"Latest run: {run['run']} · {run['scored']}/{run['attempts']} attempts scored · agent "
                         f"{money(run['agent_cost_usd'])}"
                         + (f" ({run['agent_costs_reported']}/{run['attempts']} reported)" if partial else "")
                         + f" · judges {money(run['judge_cost_usd'])}")
    waiting = status["waiting_on_user"]
    lines.append("You:    " + (" · ".join(f"{w['count']} {w['kind']}" for w in waiting) if waiting else "nothing pending"))
    spent = status["spend"]["ledger"]
    if spent["entries"]:
        lines.append(f"Spend:  helpers outside runs {money(spent['cost_usd'])} recorded"
                     + (f" · {spent['unknown']} call(s) with unknown cost" if spent["unknown"] else ""))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", nargs=2, metavar=("SKILL", "N"), help="record the active skill and stage number")
    parser.add_argument("--plan-step", help="the user's own plan step for the active work, such as 'Step 5'")
    parser.add_argument("--json", action="store_true", help="print STATUS.json instead of the text status")
    parser.add_argument("--relai-dir")
    args = parser.parse_args()
    relai = relai_root(args.relai_dir)
    if not relai.is_dir():
        print(f"error: {relai} does not exist; set up relai/ with the start skill or pass --relai-dir",
              file=sys.stderr)
        return 2
    stage = None
    if args.stage:
        skill, number = args.stage
        if skill not in STAGES or not number.isdigit() or not 1 <= int(number) <= len(STAGES[skill]):
            print(f"error: --stage takes one of {', '.join(STAGES)} and a stage number within that skill's list "
                  "(docs/board.md, Stages)", file=sys.stderr)
            return 2
        stage = (skill, int(number))
    path = relai / "STATUS.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except ValueError:
        previous = {}
    status = build(relai, previous if isinstance(previous, dict) else {}, stage, args.plan_step)
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, ensure_ascii=False) if args.json else render(status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
