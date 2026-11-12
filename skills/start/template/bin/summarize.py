#!/usr/bin/env python3
"""Summarize Harbor, native, and wrapped benchmark runs per test and evaluator, or compare a run with a baseline.

Usage:
  python3 relai/bin/summarize.py <job or run dir> [...] [--details] [--json out.json]
  python3 relai/bin/summarize.py <candidate dirs> --baseline <baseline dir> [...]

Reads every Harbor or native trial under the given directories: result.json (exceptions, rewards,
task checksum, usage), verifier/feedback.json and verifier/errors.json (code evaluators),
and judges/<evaluator-id>.json (judges, written after the trial). Each trial is classified
as scored, evaluator error, judges pending, runtime failure, or unscored; these are never
merged, and Harbor's own exit status is not trusted (it exits 0 when trials fail). A trial with an
exception and recorded token counts that are all zero is a runtime failure even when the verifier
scored it: the agent never reached its model, so the score is the untouched workspace's.

An agent-neutral coding task ([metadata.relai].agent_neutral = true) needs no trajectory to be scored: its
checks read the workspace. Without a trajectory, the evaluators that need one (code evaluators with
trajectory = true, judges whose inputs include "trajectory") are "not recorded" and left out of the pass rule.

A benchmark run through its own runner (wrapped) leaves relai-results.jsonl in its run directory,
one attempt per line: {"benchmark", "case", "split", "attempt", "status" (scored | runtime failure
| evaluator error), "score" (0-1), "error", "cost_usd", "trajectory", "benchmark_commit"}. Each
line becomes a trial of test benchmarks/<benchmark>/<case>; the benchmark commit stands in for
the task checksum, so differences in benchmark versions can be reported.

With --baseline, both sides are summarized and matched by test identity. Different runners,
changed or mixed test versions, missing identities and malformed trajectories produce advisory
warnings, not refusals. Available scores are retained; the caller judges comparability and claims.
Trajectory JSON notices inspect Harbor/native trial directories only; wrapped benchmark logs
keep their native format and must be assessed through that benchmark's integration.
Native results name runner and runner_id; wrapped rows may name runner_id when scoring changes.
Output describes observations, not acceptance or confidence. --details prints full tables;
--json always writes the complete evidence. observed_change is higher, lower, equal or
not-comparable; numeric noise/se fields are reference estimates only.
Writes nothing except --json.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    declared_evaluators, dir_digest, relai_root, frozen_state, load_json, load_toml, normalized,
    resolve_task_dir, test_key,
)

STATUSES = ("scored", "evaluator error", "judges pending", "runtime failure", "unscored", "task not found")


def find_results(paths: list[Path]):
    trials, jobs = [], []
    for root in paths:
        candidates = [root / "result.json"] + sorted(root.glob("*/result.json")) + sorted(root.glob("*/*/result.json")) \
            + sorted(root.glob("*/*/*/result.json"))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                data = load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and "trial_name" in data:
                trials.append((path.parent, data))
            elif isinstance(data, dict) and "n_total_trials" in data:
                jobs.append((path.parent, data))
    unique = {str(d.resolve()): (d, r) for d, r in trials}
    return list(unique.values()), jobs


def wrapped_records(paths: list[Path]) -> list[dict]:
    """Trials from relai-results.jsonl files written by a wrapped benchmark's adapter."""
    files = []
    for root in paths:
        files += [root / "relai-results.jsonl"] + sorted(root.glob("*/relai-results.jsonl")) \
            + sorted(root.glob("*/*/relai-results.jsonl"))
    records, seen = [], set()
    for path in files:
        if not path.is_file() or str(path.resolve()) in seen:
            continue
        seen.add(str(path.resolve()))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            bench, case = str(row.get("benchmark") or "?"), str(row.get("case") or f"line-{n}")
            state = str(row.get("status") or "scored")
            score = row.get("score")
            outcome = {"type": "code", "min": 0.0, "max": 1.0}
            if state == "scored" and valid_number(score) and 0.0 <= score <= 1.0:
                outcome.update(state="scored", score=score, feedback=str(row.get("feedback") or ""))
                status = "scored"
            elif state == "runtime failure":
                outcome.update(state="error", message=str(row.get("error") or "runtime failure"))
                status = "runtime failure"
            else:
                outcome.update(state="error", message=str(row.get("error") or f"invalid score {score!r}"))
                status = "evaluator error"
            records.append({
                "trial": f"{case}#{row.get('attempt', 1)}", "dir": str(path.parent), "checksum": row.get("benchmark_commit"),
                "runner": f"wrapped:{bench}:" + str(row.get("runner_id") or "benchmark-scorer"),
                "exception": row.get("error") if status == "runtime failure" else None,
                "score": outcome.get("score") if status == "scored" else None,
                "evaluators": {"benchmark-scorer": outcome},
                "usage": {"n_input_tokens": None, "n_cache_tokens": None, "n_output_tokens": None,
                          "cost_usd": row.get("cost_usd")},
                "test": f"benchmarks/{bench}/{case}", "task_path": f"wrapped:{bench}", "status": status,
                "split": row.get("split"), "started": str(row.get("at") or "")})
    return records


def task_split(task_path: str) -> str | None:
    try:
        return (load_toml(Path(task_path) / "task.toml").get("metadata", {}).get("relai", {}) or {}).get("split")
    except Exception:
        return None


def read_json_dict(path: Path) -> dict:
    try:
        data = load_json(path)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def valid_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def runner_label(result: dict) -> str:
    """Stable measurement identity; candidate paths/settings may vary without changing it."""
    kind = result.get("runner") or "harbor"
    return kind + ":" + str(result.get("runner_id") or "native") if kind == "native" else str(kind)


def recorded_evaluators(value) -> bool:
    """Only the fields needed to interpret original scores, without reading rubric content."""
    if not isinstance(value, list):
        return False
    ids = set()
    for ev in value:
        if not isinstance(ev, dict) or not isinstance(ev.get("id"), str) or not ev["id"] or ev["id"] in ids:
            return False
        low, high = ev.get("min_score"), ev.get("max_score")
        if ev.get("type") not in ("code", "judge") or not valid_number(low) or not valid_number(high) or low >= high:
            return False
        ids.add(ev["id"])
    return True


def trial_record(trial_dir: Path, result: dict, relai_dir: Path) -> dict:
    raw_path = str(((result.get("task_id") or {}).get("path")) or "")
    task_path = resolve_task_dir(raw_path, relai_dir, trial_dir.parent)
    exception = (result.get("exception_info") or {}).get("exception_type")
    usage = {k: (result.get("agent_result") or {}).get(k)
             for k in ("n_input_tokens", "n_cache_tokens", "n_output_tokens", "cost_usd")}
    warnings = []
    if result.get("runner") == "native" and not result.get("runner_id"):
        warnings.append("native runner_id is missing; runner identity was inferred")
    trajectory = trial_dir / "agent" / "trajectory.json"
    if trajectory.is_file():
        try:
            document = load_json(trajectory)
            if not isinstance(document, dict):
                warnings.append("trajectory JSON is not an object")
        except (OSError, ValueError) as exc:
            warnings.append(f"trajectory JSON could not be read ({type(exc).__name__})")
    base = {"trial": trial_dir.name, "dir": str(trial_dir), "checksum": result.get("task_checksum"),
            "exception": exception, "score": None, "evaluators": {}, "usage": usage,
            "runner": runner_label(result), "warnings": warnings}
    if task_path is None:
        return {**base, "test": Path(raw_path).name or result.get("task_name", "?"), "task_path": raw_path,
                "status": "task not found",
                "missing": f"task {raw_path!r} not found; Harbor records -p as typed, so run Harbor with absolute "
                           "paths or summarize from the directory Harbor ran in"}
    try:
        toml = load_toml(task_path / "task.toml")
    except Exception:
        toml = None
    # an agent-neutral coding task is scored from the workspace, so an agent Harbor records without an ATIF
    # trajectory (or the oracle) can still be scored; evaluators that need the trajectory are "not recorded"
    neutral = bool(((toml or {}).get("metadata", {}).get("relai", {}) or {}).get("agent_neutral"))
    if recorded_evaluators(result.get("evaluator_definitions")):
        evaluators = result["evaluator_definitions"]
        base["evaluator_source"] = "recorded"
    else:
        base["evaluator_source"] = "current-task"
        if "evaluator_definitions" in result:
            warnings.append("recorded evaluator definitions are invalid; falling back to current task.toml")
        warnings.append("original evaluator definitions are unavailable; scores use current task.toml evaluator types and bounds")
        evaluators = declared_evaluators(toml) if toml is not None else []
    rewards = ((result.get("verifier_result") or {}).get("rewards")) or {}
    feedback = read_json_dict(trial_dir / "verifier" / "feedback.json")
    errors = read_json_dict(trial_dir / "verifier" / "errors.json")
    crashed = bool(exception) and result.get("verifier_result") is None
    # Harbor grades the untouched workspace even when the agent never reached its model, which would read
    # as a real 0: an exception with recorded token counts that are all zero is a runtime failure
    tokens = [usage[k] for k in ("n_input_tokens", "n_output_tokens") if valid_number(usage[k])]
    if exception and tokens and not any(tokens):
        crashed = True
        base["missing"] = "the agent recorded an exception and made no model calls, so its verifier scores are not counted"
    has_trajectory = (trial_dir / "agent" / "trajectory.json").is_file()
    outcomes = {}
    for ev in evaluators:
        ev_id, low, high = ev.get("id"), ev.get("min_score", 0.0), ev.get("max_score", 1.0)
        outcome = {"type": ev.get("type"), "min": low, "max": high}
        needs_trajectory = bool(ev.get("trajectory")) if ev.get("type") == "code" else \
            "trajectory" in (ev.get("inputs") or ["trajectory"])
        if neutral and not has_trajectory and needs_trajectory:
            outcome.update(state="not recorded", message="needs a trajectory; this run has none")
            outcomes[ev_id] = outcome
            continue
        if ev.get("type") == "judge":
            path = trial_dir / "judges" / f"{ev_id}.json"
            data = read_json_dict(path) if path.is_file() else None
            if data is None:
                outcome["state"] = "pending"
            elif "error" in data:
                outcome.update(state="error", message=str(data["error"]))
            elif valid_number(data.get("score")) and low <= data["score"] <= high:
                outcome.update(state="scored", score=data["score"], feedback=data.get("feedback", ""))
            else:
                outcome.update(state="error", message=data.get("error") or f"invalid judge score {data.get('score')!r}")
        else:
            value = rewards.get(ev_id)
            if ev_id in errors:
                outcome.update(state="error", message=str(errors[ev_id]))
            elif valid_number(value) and low <= value <= high:
                outcome.update(state="scored", score=value, feedback=feedback.get(ev_id, ""))
                if not str(feedback.get(ev_id, "")).strip():
                    outcome["warning"] = "no feedback"
            elif value is not None:
                outcome.update(state="error", message=f"score {value!r} outside [{low}, {high}]")
            else:
                outcome.update(state="error", message="no score in reward.json")
        outcomes[ev_id] = outcome

    recorded = {k: o for k, o in outcomes.items() if o["state"] != "not recorded"}
    states = {o["state"] for o in recorded.values()}
    if crashed or (not has_trajectory and not neutral):
        status = "runtime failure"  # judge files written for a crashed run never make it scored
    elif not recorded:
        status = "unscored"
    elif "error" in states:
        status = "evaluator error"
    elif "pending" in states:
        status = "judges pending"
    else:
        status = "scored"
    score = None
    if status == "scored":
        score = statistics.fmean(normalized(o["score"], o["min"], o["max"]) for o in recorded.values())
    return {**base, "test": test_key(task_path, relai_dir), "task_path": str(task_path), "status": status,
            "score": score, "evaluators": outcomes}


def summarize(paths: list[Path], relai_dir: Path) -> dict:
    trials, jobs = find_results(paths)
    records = [trial_record(d, r, relai_dir) for d, r in trials] + wrapped_records(paths)
    tests: dict[str, dict] = {}
    for rec in records:
        entry = tests.setdefault(rec["test"], {"trials": [], "checksums": set(), "task_path": rec["task_path"]})
        entry["trials"].append(rec)
        if rec["checksum"]:
            entry["checksums"].add(rec["checksum"])
    summary = {"tests": {}, "trials": len(records), "status_counts": {s: 0 for s in STATUSES}, "jobs": [],
               "runners": sorted({rec["runner"] for rec in records})}
    for rec in records:
        summary["status_counts"][rec["status"]] += 1
    for job_dir, job in jobs:
        stats = job.get("stats") or {}
        summary["jobs"].append({"dir": str(job_dir), "n_total_trials": job.get("n_total_trials"),
                                "n_errored_trials": stats.get("n_errored_trials"),
                                "n_completed_trials": stats.get("n_completed_trials"),
                                "cost_usd": stats.get("cost_usd")})
    usage = {"n_input_tokens": None, "n_cache_tokens": None, "n_output_tokens": None, "cost_usd": None}
    usage_counts = {key: 0 for key in usage}
    for rec in records:
        for key, value in rec["usage"].items():
            if valid_number(value):
                usage[key] = (usage[key] or 0) + value
                usage_counts[key] += 1
    summary["usage"] = usage if any(usage_counts.values()) else None
    summary["usage_counts"] = usage_counts

    for name, entry in sorted(tests.items()):
        recs = entry["trials"]
        scored = [r["score"] for r in recs if r["score"] is not None]
        costs = [r["usage"].get("cost_usd") for r in recs if valid_number(r["usage"].get("cost_usd"))]
        wrapped = str(entry["task_path"]).startswith("wrapped:")
        per_eval: dict[str, dict] = {}
        for rec in recs:
            for ev_id, outcome in rec["evaluators"].items():
                agg = per_eval.setdefault(ev_id, {"type": outcome["type"], "scores": [], "errors": 0, "pending": 0})
                if outcome["state"] == "scored":
                    agg["scores"].append(normalized(outcome["score"], outcome["min"], outcome["max"]))
                elif outcome["state"] == "error":
                    agg["errors"] += 1
                else:
                    agg["pending"] += 1
        summary["tests"][name] = {
            "attempts": len(recs),
            "trials": recs,
            "status_counts": {s: sum(r["status"] == s for r in recs) for s in STATUSES},
            "mean": statistics.fmean(scored) if scored else None,
            "stdev": statistics.stdev(scored) if len(scored) > 1 else None,
            "scored": len(scored),
            "full_marks": sum(1 for s in scored if s >= 1.0),
            "checksums": sorted(entry["checksums"]),
            "runners": sorted({r["runner"] for r in recs}),
            "task_path": entry["task_path"],
            "split": recs[0].get("split") if wrapped else task_split(entry["task_path"]),
            "cost_usd": sum(costs) if costs else None,
            "evaluators": {
                ev_id: {"type": agg["type"], "n": len(agg["scores"]), "errors": agg["errors"], "pending": agg["pending"],
                        "mean": statistics.fmean(agg["scores"]) if agg["scores"] else None,
                        "min": min(agg["scores"]) if agg["scores"] else None,
                        "max": max(agg["scores"]) if agg["scores"] else None}
                for ev_id, agg in sorted(per_eval.items())},
            "problems": [problem(r) for r in recs if r["status"] != "scored"],
            "notes": [f"{r['trial']}: scored, but the runner recorded {r['exception']} (for example the agent timed out "
                      "and the verifier scored what it had done)" for r in recs if r["status"] == "scored" and r["exception"]],
        }
    groups: dict[tuple, list] = {}
    for name, test in summary["tests"].items():
        parts = name.split("/")
        group = "/".join(parts[:2]) if parts[0] == "benchmarks" and len(parts) > 2 else parts[0]
        groups.setdefault((group, test["split"] or "development"), []).append(test["mean"])
    summary["splits"] = [{"group": g, "split": s, "tests": len(m), "scored": sum(v is not None for v in m),
                          "mean": statistics.fmean([v for v in m if v is not None]) if any(v is not None for v in m) else None}
                         for (g, s), m in sorted(groups.items())]
    return summary


def problem(rec: dict) -> str:
    details = [f"{k}: {o.get('message', o['state'])}" for k, o in rec["evaluators"].items() if o["state"] != "scored"]
    parts = [rec["status"]]
    if rec.get("missing"):
        parts.append(rec["missing"])
    if rec["exception"]:
        parts.append(f"exception {rec['exception']}")
    parts += details
    return f"{rec['trial']}: " + "; ".join(parts)


def fmt(value) -> str:
    return "-" if value is None else f"{value:.2f}"


def print_summary(summary: dict, label: str, details: bool = False) -> None:
    counts = summary["status_counts"]
    print(f"## {label}")
    print("Runner: " + ", ".join(summary["runners"]))
    print(f"Trials: {summary['trials']} (" + ", ".join(f"{k} {v}" for k, v in counts.items() if v) + ")")
    for job in summary["jobs"]:
        if job.get("n_errored_trials"):
            print(f"Run {Path(job['dir']).name}: {job['n_errored_trials']} errored trial(s)")
    if summary["usage"]:
        reported = []
        for key, value in summary["usage"].items():
            shown = "not measured" if value is None else f"${value:.4f}" if key == "cost_usd" else str(value)
            reported.append(f"{key} {shown} ({summary['usage_counts'][key]}/{summary['trials']} reported)")
        print("Agent usage: " + ", ".join(reported))
    else:
        print("Agent usage: not measured")
    notes_count = sum(len(t["notes"]) for t in summary["tests"].values())
    if notes_count:
        print(f"Scored attempts with runtime notes: {notes_count}; inspect --details or JSON.")
    print(f"Coverage: {len(summary['tests'])} test(s)")
    if not details:
        print("Full test/evaluator evidence: --details; complete machine-readable evidence: --json <path>.")
        return
    print()
    print("| Test | Attempts | Scored | Mean | Observed stdev | Full marks |")
    print("| --- | --- | --- | --- | --- | --- |")
    for name, t in summary["tests"].items():
        print(f"| {name} | {t['attempts']} | {t['scored']} | {fmt(t['mean'])} | {fmt(t['stdev'])} | {t['full_marks']} |")
    print()
    if any(r["group"].startswith("benchmarks/") or r["split"] != "development" for r in summary["splits"]):
        print("| Group | Split | Tests | Scored | Mean |")
        print("| --- | --- | --- | --- | --- |")
        for r in summary["splits"]:
            print(f"| {r['group']} | {r['split']} | {r['tests']} | {r['scored']} | {fmt(r['mean'])} |")
        print()
    print("| Test | Evaluator | Type | Scored | Mean | Min | Max | Errors | Pending |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, t in summary["tests"].items():
        for ev_id, e in t["evaluators"].items():
            print(f"| {name} | {ev_id} | {e['type']} | {e['n']} | {fmt(e['mean'])} | {fmt(e['min'])} | {fmt(e['max'])} "
                  f"| {e['errors']} | {e['pending']} |")
    problems = [(name, p) for name, t in summary["tests"].items() for p in t["problems"]]
    if problems:
        print("\nNot scored cleanly (never count these as agent failures or passes):")
        for name, p in problems:
            print(f"- {name} / {p}")
    notes = [(name, n) for name, t in summary["tests"].items() for n in t["notes"]]
    for name, n in notes:
        print(f"note: {name} / {n}")


def frozen_warnings(relai_dir: Path, summary: dict) -> list[str]:
    warnings = []
    frozen = frozen_state(relai_dir).get("tests", {})
    for name, test in summary["tests"].items():
        if test["status_counts"]["task not found"] == test["attempts"]:
            continue
        if name.startswith("harness/"):  # the smoke test checks the harness and is never frozen
            continue
        if str(test["task_path"]).startswith("wrapped:"):  # pinned by its benchmark commit instead
            continue
        entry = frozen.get(name)
        if not entry:
            warnings.append(f"{name} is not frozen; freeze tests before their first real run")
            continue
        path = relai_dir / name
        if path.is_dir() and dir_digest(path) != entry.get("digest"):
            warnings.append(f"{name} changed since it was frozen")
    return warnings


def evidence_warnings(summary: dict) -> list[str]:
    """Observations about evidence quality, not a decision about whether it may be used."""
    warnings = []
    for name, test in summary["tests"].items():
        if len(test["checksums"]) > 1:
            warnings.append(f"{name}: mixed test versions within this run")
        if len(test["runners"]) > 1:
            warnings.append(f"{name}: mixed runner identities within this run")
        missing = sum(not trial["checksum"] for trial in test["trials"])
        if missing:
            warnings.append(f"{name}: test version identity is missing for {missing} attempt(s)")
        for trial in test["trials"]:
            warnings.extend(f"{name} / {trial['trial']}: {warning}" for warning in trial.get("warnings", []))
    return warnings


def compare(base: dict, cand: dict) -> dict:
    rows = []
    for name in sorted(set(base["tests"]) & set(cand["tests"])):
        b, c = base["tests"][name], cand["tests"][name]
        delta = c["mean"] - b["mean"] if b["mean"] is not None and c["mean"] is not None else None
        noise = (math.sqrt(b["stdev"] ** 2 / b["scored"] + c["stdev"] ** 2 / c["scored"])
                 if b["scored"] > 1 and c["scored"] > 1 else None)
        change = observed_change(delta)
        rows.append({"test": name, "baseline": b["mean"], "candidate": c["mean"], "delta": delta,
                     "noise": noise, "observed_change": change,
                     "baseline_scored": b["scored"], "candidate_scored": c["scored"],
                     "attempts": f"{b['scored']}/{c['scored']}"})
    return {"rows": rows, "overall": overall(rows),
            "baseline only": sorted(set(base["tests"]) - set(cand["tests"])),
            "candidate only": sorted(set(cand["tests"]) - set(base["tests"]))}


def comparison_warnings(base: dict, cand: dict) -> list[str]:
    warnings = []
    if base["runners"] != cand["runners"]:
        warnings.append("runs use different runners or measurement identities")
    for name in sorted(set(base["tests"]) & set(cand["tests"])):
        b, c = base["tests"][name], cand["tests"][name]
        if b["runners"] != c["runners"]:
            warnings.append(f"{name}: different runners or measurement identities between runs")
        if b["checksums"] != c["checksums"]:
            warnings.append(f"{name}: different test versions between runs")
    return warnings


def print_warnings(warnings: list[str], label: str, details: bool) -> None:
    if not warnings:
        return
    print(f"{label}: {len(warnings)}; advisory, inspect --details or JSON.")
    if details:
        for warning in warnings:
            print(f"warning: {warning}")


def observed_change(delta) -> str:
    if delta is None:
        return "not-comparable"
    return "higher" if delta > 0 else "lower" if delta < 0 else "equal"


def overall(rows: list[dict]) -> dict | None:
    """Descriptive mean of matched per-test deltas; no inference or acceptance verdict."""
    deltas = [r["delta"] for r in rows if r["delta"] is not None]
    if not deltas:
        return None
    mean = statistics.fmean(deltas)
    se = statistics.stdev(deltas) / math.sqrt(len(deltas)) if len(deltas) > 1 else None
    change = observed_change(mean)
    higher, lower, equal = sum(d > 0 for d in deltas), sum(d < 0 for d in deltas), sum(d == 0 for d in deltas)
    return {"tests": len(deltas), "mean_delta": mean, "se": se, "observed_change": change,
            "higher": higher, "lower": lower, "equal": equal}


def print_comparison(comparison: dict, details: bool) -> None:
    print("\n## Observed comparison")
    if details:
        print("| Test | Baseline | Candidate | Delta | Spread reference (1 s.e.) | Scored attempts | Observed change |")
        print("| --- | --- | --- | --- | --- | --- | --- |")
        for row in comparison["rows"]:
            print(f"| {row['test']} | {fmt(row['baseline'])} | {fmt(row['candidate'])} | {fmt(row['delta'])} | "
                  f"{fmt(row.get('noise'))} | {row['attempts']} | {row['observed_change']} |")
    counts = {key: sum(row["observed_change"] == key for row in comparison["rows"])
              for key in ("higher", "lower", "equal", "not-comparable")}
    print("Matched tests: " + ", ".join(f"{key} {value}" for key, value in counts.items()))
    total = comparison["overall"]
    if total:
        print(f"Overall, paired over {total['tests']} tests: observed mean delta {total['mean_delta']:+.3f} "
              f"({total['observed_change']}); across-test s.e. reference {fmt(total['se'])}")
    for key in ("baseline only", "candidate only"):
        if comparison[key]:
            print(f"{key}: " + (", ".join(comparison[key]) if details else f"{len(comparison[key])} test(s)"))
    print("Observed spread, including zero spread, does not establish confidence, equivalence, or improvement. "
          "Differences are reported even when measurement conditions differ. "
          "Use the warnings, agreed objective, sampling and guardrails to judge the evidence.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", help="Harbor job directories, wrapped benchmark run directories, or folders containing them")
    parser.add_argument("--baseline", nargs="+", help="baseline job directories to compare against")
    parser.add_argument("--relai-dir")
    parser.add_argument("--details", action="store_true", help="show complete test, evaluator and comparison tables")
    parser.add_argument("--json", help="also write the summary as JSON to this path")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir)
    cand = summarize([Path(p) for p in args.runs], relai_dir)
    if not cand["trials"]:
        print("error: no Harbor/native trials or relai-results.jsonl found under the given directories")
        return 2
    print_summary(cand, "Run" if not args.baseline else "Candidate", args.details)
    output = {"run": cand}
    status = 1 if cand["status_counts"]["task not found"] else 0
    output["warnings"] = {"candidate": frozen_warnings(relai_dir, cand) + evidence_warnings(cand)}
    print_warnings(output["warnings"]["candidate"], "Integrity warnings", args.details)
    if args.baseline:
        base = summarize([Path(p) for p in args.baseline], relai_dir)
        print()
        print_summary(base, "Baseline", args.details)
        output["warnings"]["baseline"] = frozen_warnings(relai_dir, base) + evidence_warnings(base)
        print_warnings(output["warnings"]["baseline"], "Baseline integrity warnings", args.details)
        comparison = compare(base, cand)
        output["warnings"]["comparison"] = comparison_warnings(base, cand)
        print_warnings(output["warnings"]["comparison"], "Comparison warnings", args.details)
        output["baseline"], output["comparison"] = base, comparison
        print_comparison(comparison, args.details)
    print("Source runs: " + ", ".join(args.runs + (args.baseline or [])))
    if args.json:
        def default(value):
            return sorted(value) if isinstance(value, set) else str(value)
        Path(args.json).write_text(json.dumps(output, indent=2, default=default) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
