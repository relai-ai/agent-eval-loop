#!/usr/bin/env python3
"""Splits, sampling and the coverage record for a benchmark, so a small budget covers a large one.

Usage:
  python3 relai/bin/benchmark.py init <id> --cases cases.jsonl --source SRC --commit SHA [--mode import|wrap]
                                      [--map train=development,validation=held-out,test=final]
                                      [--derive-splits] [--held-out-n 80] [--seed 0]
  python3 relai/bin/benchmark.py sample <id>              # the fixed held-out sample, one case id per line
  python3 relai/bin/benchmark.py batch <id> --case-ids a b  # exact development selection
  python3 relai/bin/benchmark.py batch <id> --n 20        # the next working batch (recorded), one id per line
  python3 relai/bin/benchmark.py record <id> <run dir>... --agent <revision>
  python3 relai/bin/benchmark.py fidelity <id> <run dir>... --reference scores.jsonl
  python3 relai/bin/benchmark.py coverage <id> [--json]

The coverage record is relai/work/benchmarks/<id>/ledger.json. `init` reads one JSON object per
line, {"id", "split"?, "category"?}, and maps the benchmark's own split names to RELAI's roles:
development (investigation may read it), held-out (scored only; decides keep or reject) and final
(report only). Supplied splits are preserved; unsplit cases remain development by default. Only with
--derive-splits does it derive a category-balanced fifth of development for validation, or
60/20/20 when all cases are unsplit. Existing ledgers are never changed by init. `batch --case-ids` records the agent's exact selection.
The optional `batch --n` strategy mixes development cases: about 30%
that failed before (to fix), about 20% that passed before (to catch regressions), and the rest
never played (category-balanced); when one kind runs out, the others fill in. `record` adds a run's
scores (Harbor trials, or relai-results.jsonl from a wrapped benchmark) and refuses results from a
different benchmark commit. `fidelity` checks RELAI's per-case scores against the benchmark's own
scorer on the same runs. Standard library only; never calls a model or runs the agent.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import fail, relai_root  # noqa: E402

ROLES = ("development", "held-out", "final")
DEFAULT_MAP = {"train": "development", "training": "development", "dev": "held-out", "val": "held-out",
               "valid": "held-out", "validation": "held-out", "test": "final", "eval": "final"}
SAFE = re.compile(r"[^A-Za-z0-9._-]")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ledger_path(relai_dir: Path, bench: str) -> Path:
    return relai_dir / "work" / "benchmarks" / bench / "ledger.json"


def load(relai_dir: Path, bench: str) -> dict:
    path = ledger_path(relai_dir, bench)
    if not path.is_file():
        fail(f"no coverage record for {bench!r}; run `benchmark.py init {bench} ...` first")
    return json.loads(path.read_text(encoding="utf-8"))


def save(relai_dir: Path, ledger: dict) -> None:
    path = ledger_path(relai_dir, ledger["benchmark"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8")


def balanced(ids: list[str], cases: dict, rng: random.Random) -> list[str]:
    """Shuffle within each category, then take one per category in turn."""
    buckets: dict[str, list[str]] = {}
    for cid in ids:
        buckets.setdefault(str(cases[cid].get("category") or ""), []).append(cid)
    order = sorted(buckets)
    rng.shuffle(order)
    for key in order:
        rng.shuffle(buckets[key])
    out = []
    while any(buckets.values()):
        for key in order:
            if buckets[key]:
                out.append(buckets[key].pop())
    return out


def parse_map(text: str | None) -> dict:
    mapping = dict(DEFAULT_MAP)
    for part in filter(None, (text or "").split(",")):
        name, _, role = part.partition("=")
        if role.strip() not in ROLES:
            fail(f"--map role must be one of {', '.join(ROLES)}, got {role!r}")
        mapping[name.strip().lower()] = role.strip()
    return mapping


def init(args, relai_dir: Path) -> int:
    if ledger_path(relai_dir, args.id).is_file():
        print(f"error: {args.id} already has a coverage record; a new benchmark version gets a new id "
              "(for example <name>-<commit>) so runs on different versions are never compared", file=sys.stderr)
        return 2
    mapping, rng = parse_map(args.map), random.Random(args.seed)
    cases: dict[str, dict] = {}
    for n, line in enumerate(Path(args.cases).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        source_id = str(row.get("id") or "")
        if not source_id:
            fail(f"line {n} has no id")
        cid = SAFE.sub("_", source_id)
        if cid in cases:
            fail(f"duplicate case id {cid!r} (line {n})")
        split = str(row.get("split") or "").strip()
        role = mapping.get(split.lower()) if split else None
        if split and role is None:
            fail(f"unknown split {split!r} on line {n}; map it with --map {split}=<role>")
        cases[cid] = {"split": split or None, "role": role, "category": row.get("category"), "plays": []}
        if cid != source_id:
            cases[cid]["source_id"] = source_id
    if not cases:
        fail("no cases")
    notes = []
    unsplit = [c for c, v in cases.items() if v["role"] is None]
    if unsplit and len(unsplit) == len(cases) and args.derive_splits:
        order = balanced(unsplit, cases, rng)
        a, b = round(0.6 * len(order)), round(0.8 * len(order))
        for i, cid in enumerate(order):
            cases[cid]["role"] = "development" if i < a else "held-out" if i < b else "final"
        notes.append("no splits given: made 60/20/20 development/held-out/final")
    elif unsplit and len(unsplit) == len(cases):
        for cid in unsplit:
            cases[cid]["role"] = "development"
        notes.append("no splits given: all cases remain development; no independent assessment")
    elif unsplit:
        fail(f"{len(unsplit)} case(s) have no split while others do; give every case a split")
    if args.derive_splits and not any(v["role"] == "held-out" for v in cases.values()):
        dev = balanced([c for c, v in cases.items() if v["role"] == "development"], cases, rng)
        for cid in dev[: max(1, round(0.2 * len(dev)))] if dev else []:
            cases[cid]["role"] = "held-out"
        notes.append("no held-out split: set aside a category-balanced fifth of development")
    held = balanced([c for c, v in cases.items() if v["role"] == "held-out"], cases, rng)
    ledger = {"benchmark": args.id, "source": args.source, "commit": args.commit, "mode": args.mode,
              "seed": args.seed, "created": now(), "map": {k: v for k, v in mapping.items()
                                                         if any(c["split"] and c["split"].lower() == k for c in cases.values())},
              "held_out_sample": sorted(held[: args.held_out_n]), "batches": [], "final_runs": [],
              "fidelity": None, "notes": notes, "cases": cases}
    save(relai_dir, ledger)
    counts = {r: sum(v["role"] == r for v in cases.values()) for r in ROLES}
    print(f"{args.id}: {len(cases)} cases - " + ", ".join(f"{r} {n}" for r, n in counts.items())
          + f"; held-out sample {len(ledger['held_out_sample'])}")
    for note in notes:
        print(f"note: {note}")
    return 0


def latest(case: dict) -> dict | None:
    return case["plays"][-1] if case["plays"] else None


def batch(args, relai_dir: Path) -> int:
    ledger = load(relai_dir, args.id)
    cases = ledger["cases"]
    dev = [c for c, v in cases.items() if v["role"] == "development"]
    unplayed_ids = {c for c in dev if not cases[c]["plays"]}
    if args.case_ids is not None:
        chosen = args.case_ids
        if len(chosen) != len(set(chosen)):
            fail("duplicate case ids")
        invalid = [cid for cid in chosen if cid not in cases or cases[cid]["role"] != "development"]
        if invalid:
            fail("case ids must name development cases: " + ", ".join(invalid))
    else:
        n = args.n
        if n < 1:
            fail("--n must be positive")
        rng = random.Random(f"{ledger['seed']}-{len(ledger['batches'])}")
        unplayed = balanced([c for c in dev if not cases[c]["plays"]], cases, rng)
        failed = [c for c in dev if latest(cases[c]) and latest(cases[c])["score"] is not None and latest(cases[c])["score"] < 1.0]
        passed = [c for c in dev if latest(cases[c]) and latest(cases[c])["score"] is not None and latest(cases[c])["score"] >= 1.0]
        failed.sort(key=lambda c: latest(cases[c])["score"])
        rng.shuffle(passed)
        want_passed = min(len(passed), max(1, round(0.2 * n))) if passed else 0
        want_failed = min(len(failed), round(0.3 * n))
        chosen = unplayed[: max(0, n - want_passed - want_failed)]
        chosen += failed[: want_failed + max(0, n - want_passed - want_failed - len(chosen))]
        chosen += [c for c in passed if c not in chosen][: n - len(chosen)]
        chosen += [c for c in failed if c not in chosen][: n - len(chosen)]
    ledger["batches"].append({"at": now(), "cases": chosen})
    save(relai_dir, ledger)
    left = len(unplayed_ids) - sum(1 for c in chosen if c in unplayed_ids)
    for cid in chosen:
        print(cid)
    print(f"# {len(chosen)} case(s); {left} unplayed development case(s) outside this scheduled batch (no trials launched)", file=sys.stderr)
    return 0


def case_ids(ledger: dict) -> dict[str, str]:
    """Original benchmark identifiers and generated task directory names address the same case."""
    return {name: cid for cid, case in ledger["cases"].items() for name in (cid, case.get("source_id", cid))}


def results(relai_dir: Path, bench: str, runs: list[str], ledger: dict) -> tuple[dict, list[str]]:
    from summarize import summarize  # imported here so `init` and `batch` need nothing else
    summary = summarize([Path(r) for r in runs], relai_dir)
    prefix, out, problems = f"benchmarks/{bench}/", {}, []
    aliases = case_ids(ledger)
    for key, test in summary["tests"].items():
        if key.startswith(prefix):
            suffix = key[len(prefix):]
            raw = suffix if str(test["task_path"]).startswith("wrapped:") else suffix.rsplit("/", 1)[-1]
            cid = aliases.get(raw, raw)
            if cid in out:
                problems.append(f"multiple result identities map to case {cid!r}; use one original or generated id per case")
            else:
                out[cid] = test
    if not out:
        problems.append(f"no results for benchmark {bench!r} under {', '.join(runs)}")
    return out, problems


def record(args, relai_dir: Path) -> int:
    ledger = load(relai_dir, args.id)
    found, problems = results(relai_dir, args.id, args.runs, ledger)
    for p in problems:
        print(f"error: {p}", file=sys.stderr)
    if problems:
        return 2
    wrong = sorted({c for t in found.values() if str(t["task_path"]).startswith("wrapped:") for c in t["checksums"]}
                   - {ledger["commit"]})
    if wrong:
        print(f"error: results come from benchmark commit(s) {', '.join(wrong)}, not {ledger['commit']}; "
              "a different version is a different benchmark", file=sys.stderr)
        return 2
    run_name, final_scores, unknown, unscored = Path(args.runs[0]).name, [], [], 0
    for cid, test in sorted(found.items()):
        case = ledger["cases"].get(cid)
        if case is None:
            unknown.append(cid)
            continue
        if test["mean"] is None:
            unscored += 1
        cost = test.get("cost_usd")
        case["plays"].append({"run": run_name, "agent": args.agent, "score": test["mean"],
                              "attempts": test["attempts"], "scored": test["scored"], "at": now(),
                              "cost_usd": cost / test["attempts"] if cost is not None and test["attempts"] else None})
        if case["role"] == "final" and test["mean"] is not None:
            final_scores.append(test["mean"])
    if final_scores:
        ledger["final_runs"].append({"at": now(), "agent": args.agent, "run": run_name, "n": len(final_scores),
                                     "mean": statistics.fmean(final_scores)})
    save(relai_dir, ledger)
    print(f"recorded {len(found) - len(unknown)} case(s) from {run_name} ({unscored} without a score: "
          "rerun those, they are not failures)")
    if unknown:
        print(f"warning: {len(unknown)} case(s) not in the record: {', '.join(unknown[:5])}")
    if final_scores:
        print(f"note: final split played ({len(final_scores)} case(s)); this is final run "
              f"#{len(ledger['final_runs'])}. Report it; never choose a change from it.")
    return 0


def fidelity(args, relai_dir: Path) -> int:
    ledger = load(relai_dir, args.id)
    found, problems = results(relai_dir, args.id, args.runs, ledger)
    aliases = case_ids(ledger)
    reference = {}
    for line in Path(args.reference).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            raw = str(row["case"])
            reference[aliases.get(raw, raw)] = float(row["score"])
    compared, mismatched = 0, []
    for cid, ref in sorted(reference.items()):
        mine = (found.get(cid) or {}).get("mean")
        if mine is None:
            problems.append(f"{cid}: no RELAI score to compare")
            continue
        compared += 1
        if abs(mine - ref) > 1e-6:
            mismatched.append(f"{cid}: RELAI {mine:.4f} vs benchmark {ref:.4f}")
    ok = compared > 0 and not mismatched and not problems
    ledger["fidelity"] = {"at": now(), "run": Path(args.runs[0]).name, "cases": compared, "ok": ok,
                          "mismatched": mismatched[:20]}
    save(relai_dir, ledger)
    for line in problems + mismatched:
        print(f"- {line}")
    print(f"fidelity {'OK' if ok else 'FAILED'}: {compared} case(s) compared, {len(mismatched)} mismatched"
          + ("" if ok else "; no score counts until RELAI's scores match the benchmark's own"))
    return 0 if ok else 1


def revision_scores(plays: list[dict]) -> dict:
    """Latest observations can describe one revision, never a synthetic mix of revisions."""
    scored = [p for p in plays if p is not None and p.get("score") is not None]
    agents = sorted({p.get("agent") or None for p in scored}, key=lambda name: name or "")
    scores = [p["score"] for p in scored]
    warning = None
    if scores and (len(agents) != 1 or agents[0] is None):
        warning = "mixed agent revisions" if len(agents) > 1 else "unknown agent revision"
    return {"scored": len(scores), "agents": agents,
            "mean": statistics.fmean(scores) if scores and not warning else None,
            "se": statistics.stdev(scores) / len(scores) ** 0.5 if len(scores) > 1 and not warning else None,
            "warning": warning}


def coverage(ledger: dict) -> dict:
    cases = ledger["cases"]
    out = {"benchmark": ledger["benchmark"], "commit": ledger.get("commit"), "mode": ledger.get("mode"), "roles": {},
           "fidelity": ledger.get("fidelity"), "final_runs": ledger.get("final_runs", [])}
    for role in ROLES:
        ids = [c for c, v in cases.items() if v["role"] == role]
        scores = revision_scores([latest(cases[c]) for c in ids])
        out["roles"][role] = {"total": len(ids), "played": sum(1 for c in ids if cases[c]["plays"]),
                              **scores}
    sample = revision_scores([latest(cases[c]) for c in ledger.get("held_out_sample", []) if c in cases])
    out["held_out_sample"] = {"n": len(ledger.get("held_out_sample", [])), **sample}
    costs = [p.get("cost_usd") for v in cases.values() for p in v["plays"] if isinstance(p.get("cost_usd"), (int, float))]
    out["cost_per_case"] = statistics.fmean(costs) if costs else None
    return out


def coverage_line(cov: dict) -> str:
    dev, sample = cov["roles"]["development"], cov["held_out_sample"]
    fmt = lambda v: "-" if v is None else f"{v:.2f}"  # noqa: E731
    def assessment(stats):
        agents = ", ".join(agent or "unknown" for agent in stats["agents"])
        if stats["warning"]:
            return f"mean unavailable: {stats['warning']} ({agents})"
        return f"{fmt(stats['mean'])} @ {agents}" if agents else "not run"
    held = (f"{assessment(sample)} ± {fmt(sample['se'])} (n={sample['scored']}/{sample['n']})" if sample["mean"] is not None
            else f"{assessment(sample)} (n={sample['scored']}/{sample['n']})")
    finals = cov["final_runs"]
    final = f"run {len(finals)}× (last {finals[-1]['mean']:.2f}, {finals[-1]['at'][:10]})" if finals else "not run"
    fid = cov["fidelity"]
    fid_text = "fidelity not checked" if not fid else ("fidelity OK" if fid["ok"] else "FIDELITY FAILED")
    return (f"{cov['benchmark']} @ {str(cov['commit'] or '?')[:7]}: development {dev['played']}/{dev['total']} played "
            f"({assessment(dev)}); held-out sample {held}; final {final}; {fid_text}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--relai-dir")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("id")
    p.add_argument("--cases", required=True)
    p.add_argument("--source", required=True, help="benchmark repository path or URL")
    p.add_argument("--commit", required=True, help="the benchmark commit the cases come from")
    p.add_argument("--mode", choices=("import", "wrap"), default="import")
    p.add_argument("--map", help="extra split mappings, e.g. holdout=held-out,public=final")
    p.add_argument("--derive-splits", action="store_true", help="explicitly derive missing splits after agreeing their relevance")
    p.add_argument("--held-out-n", type=int, default=80)
    p.add_argument("--seed", type=int, default=0)
    p = sub.add_parser("sample")
    p.add_argument("id")
    p = sub.add_parser("batch")
    p.add_argument("id")
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument("--n", type=int, help="optional automatic selection strategy")
    selection.add_argument("--case-ids", nargs="+", help="exact development case ids, preserved in this order")
    p = sub.add_parser("record")
    p.add_argument("id")
    p.add_argument("runs", nargs="+")
    p.add_argument("--agent", required=True, help="the agent revision that played (git commit or candidate name)")
    p = sub.add_parser("fidelity")
    p.add_argument("id")
    p.add_argument("runs", nargs="+")
    p.add_argument("--reference", required=True, help="JSONL of {case, score} from the benchmark's own scorer")
    p = sub.add_parser("coverage")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir)
    if args.command == "init":
        return init(args, relai_dir)
    if args.command == "sample":
        print("\n".join(load(relai_dir, args.id)["held_out_sample"]))
        return 0
    if args.command == "batch":
        return batch(args, relai_dir)
    if args.command == "record":
        return record(args, relai_dir)
    if args.command == "fidelity":
        return fidelity(args, relai_dir)
    cov = coverage(load(relai_dir, args.id))
    print(json.dumps(cov, indent=1) if args.json else coverage_line(cov))
    return 0


if __name__ == "__main__":
    sys.exit(main())
