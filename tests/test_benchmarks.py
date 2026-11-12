"""Tests for benchmarks: splits, sampling, coverage record, wrapped results, fidelity, the board.
Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import json
import unittest

from helpers import Repo


def cases_file(repo: Repo, rows: list[dict]) -> str:
    repo.write("bench/cases.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
    return str(repo.root / "bench" / "cases.jsonl")


def wrapped_run(repo: Repo, run: str, rows: list[tuple], commit: str = "abc1234", bench: str = "bx") -> str:
    lines = [{"benchmark": bench, "case": c, "split": s, "attempt": 1, "status": st, "score": sc,
              "cost_usd": 0.02, "benchmark_commit": commit, "at": "2026-11-10T00:00:00Z"} for c, s, st, sc in rows]
    repo.write(f"relai/work/runs/{run}/relai-results.jsonl", "".join(json.dumps(x) + "\n" for x in lines))
    return str(repo.relai / "work" / "runs" / run)


def ledger(repo: Repo, bench: str = "bx") -> dict:
    return json.loads((repo.relai / "work" / "benchmarks" / bench / "ledger.json").read_text())


class SplitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()

    def tearDown(self) -> None:
        self.repo.close()

    def init(self, rows, *extra):
        return self.repo.run("benchmark.py", "init", "bx", "--cases", cases_file(self.repo, rows),
                             "--source", "../bench", "--commit", "abc1234", *extra)

    def test_train_test_gets_a_held_out_fifth_of_train(self):
        rows = [{"id": f"t{i}", "split": "train", "category": "ab"[i % 2]} for i in range(20)]
        rows += [{"id": f"x{i}", "split": "test"} for i in range(5)]
        out = self.init(rows, "--derive-splits", "--held-out-n", "3")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        roles = [c["role"] for c in ledger(self.repo)["cases"].values()]
        self.assertEqual((roles.count("development"), roles.count("held-out"), roles.count("final")), (16, 4, 5))
        self.assertEqual(len(ledger(self.repo)["held_out_sample"]), 3)
        self.assertIn("set aside a category-balanced fifth", out.stdout)

    def test_validation_split_is_held_out_and_test_is_final(self):
        rows = [{"id": "a", "split": "train"}, {"id": "b", "split": "validation"}, {"id": "c", "split": "test"}]
        self.assertEqual(self.init(rows).returncode, 0)
        roles = {k: v["role"] for k, v in ledger(self.repo)["cases"].items()}
        self.assertEqual(roles, {"a": "development", "b": "held-out", "c": "final"})

    def test_no_splits_makes_60_20_20(self):
        self.assertEqual(self.init([{"id": f"c{i}"} for i in range(10)], "--derive-splits").returncode, 0)
        roles = [c["role"] for c in ledger(self.repo)["cases"].values()]
        self.assertEqual((roles.count("development"), roles.count("held-out"), roles.count("final")), (6, 2, 2))

    def test_unsplit_cases_remain_development_without_a_sample(self):
        self.assertEqual(self.init([{"id": f"c{i}"} for i in range(10)]).returncode, 0)
        saved = ledger(self.repo)
        self.assertTrue(all(c["role"] == "development" for c in saved["cases"].values()))
        self.assertEqual(saved["held_out_sample"], [])
        self.assertEqual(self.repo.run("benchmark.py", "sample", "bx").stdout.strip(), "")
        self.assertEqual(self.repo.run("benchmark.py", "batch", "bx", "--n", "3").returncode, 0)
        run = wrapped_run(self.repo, "dev", [("c0", "", "scored", 1.0)])
        self.assertEqual(self.repo.run("benchmark.py", "record", "bx", run, "--agent", "start").returncode, 0)
        self.assertEqual(ledger(self.repo)["held_out_sample"], [])

    def test_train_and_final_preserved_without_derived_validation(self):
        self.assertEqual(self.init([{"id": "a", "split": "train"}, {"id": "b", "split": "test"}]).returncode, 0)
        saved = ledger(self.repo)
        self.assertEqual({k: v["role"] for k, v in saved["cases"].items()}, {"a": "development", "b": "final"})
        out = self.init([{"id": "new"}], "--derive-splits")
        self.assertEqual(out.returncode, 2)
        self.assertEqual(ledger(self.repo), saved, "existing ledgers must not be silently migrated")

    def test_unknown_split_needs_a_mapping(self):
        rows = [{"id": "a", "split": "train"}, {"id": "b", "split": "holdout"}]
        out = self.init(rows)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("--map holdout=<role>", out.stdout + out.stderr)
        self.assertEqual(self.init(rows, "--map", "holdout=held-out").returncode, 0)

    def test_unsafe_ids_are_sanitized_and_a_second_init_is_refused(self):
        self.assertEqual(self.init([{"id": "repo/issue#1", "split": "train"}, {"id": "b", "split": "test"}]).returncode, 0)
        self.assertEqual(ledger(self.repo)["cases"]["repo_issue_1"]["source_id"], "repo/issue#1")
        self.assertIn("new benchmark version gets a new id", self.init([{"id": "z"}]).stderr)

    def test_original_wrapped_case_ids_round_trip_record_and_fidelity(self):
        self.assertEqual(self.init([{"id": "repo/issue#1", "split": "train"},
                                    {"id": "other/issue#1", "split": "train"}]).returncode, 0)
        run = wrapped_run(self.repo, "r1", [("repo/issue#1", "train", "scored", 1.0),
                                            ("other/issue#1", "train", "scored", 0.0)])
        recorded = self.repo.run("benchmark.py", "record", "bx", run, "--agent", "revision-a")
        self.assertEqual(recorded.returncode, 0, recorded.stdout + recorded.stderr)
        self.assertIn("recorded 2 case(s)", recorded.stdout)
        saved = ledger(self.repo)
        self.assertEqual(saved["cases"]["repo_issue_1"]["plays"][-1]["score"], 1.0)
        self.assertEqual(saved["cases"]["other_issue_1"]["plays"][-1]["score"], 0.0)
        ref = self.repo.write("reference.jsonl", '{"case":"repo/issue#1","score":1.0}\n'
                              '{"case":"other/issue#1","score":0.0}\n')
        fidelity = self.repo.run("benchmark.py", "fidelity", "bx", run, "--reference", str(ref))
        self.assertEqual(fidelity.returncode, 0, fidelity.stdout + fidelity.stderr)
        self.assertIn("2 case(s) compared", fidelity.stdout)


class SamplingAndRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repo()
        rows = [{"id": f"d{i}", "split": "train", "category": "abc"[i % 3]} for i in range(12)]
        rows += [{"id": f"v{i}", "split": "validation"} for i in range(4)]
        rows += [{"id": f"f{i}", "split": "test"} for i in range(3)]
        out = self.repo.run("benchmark.py", "init", "bx", "--cases", cases_file(self.repo, rows), "--source", "../bench",
                            "--commit", "abc1234", "--held-out-n", "4")
        assert out.returncode == 0, out.stdout + out.stderr

    def tearDown(self) -> None:
        self.repo.close()

    def batch(self, n: int) -> list[str]:
        out = self.repo.run("benchmark.py", "batch", "bx", "--n", str(n))
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.split()

    def test_batches_cover_unplayed_cases_category_balanced(self):
        first = self.batch(3)
        cats = {ledger(self.repo)["cases"][c]["category"] for c in first}
        self.assertEqual(cats, {"a", "b", "c"})
        self.assertTrue(all(c.startswith("d") for c in first))
        self.assertEqual(len(ledger(self.repo)["batches"]), 1)

    def test_explicit_selection_preserves_order_and_records_only_a_plan(self):
        result = self.repo.run("benchmark.py", "batch", "bx", "--case-ids", "d4", "d1", "d7")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["d4", "d1", "d7"])
        saved = ledger(self.repo)
        self.assertEqual(saved["batches"][-1]["cases"], ["d4", "d1", "d7"])
        self.assertTrue(all(not c["plays"] for c in saved["cases"].values()))

    def test_invalid_explicit_requests_are_atomic(self):
        path = self.repo.relai / "work/benchmarks/bx/ledger.json"
        before = path.read_bytes()
        for extra in (("--case-ids", "d1", "v0"), ("--case-ids", "d1", "f0"),
                      ("--case-ids", "d1", "unknown"), ("--case-ids", "d1", "d1"),
                      ("--case-ids", "d1", "--n", "2"), ("--n", "0"), ("--n", "-1")):
            with self.subTest(extra=extra):
                result = self.repo.run("benchmark.py", "batch", "bx", *extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(path.read_bytes(), before)

    def test_record_then_next_batch_prefers_unplayed_then_failed(self):
        first = self.batch(4)
        run = wrapped_run(self.repo, "r1", [(c, "train", "scored", 0.0 if i < 2 else 1.0) for i, c in enumerate(first)])
        out = self.repo.run("benchmark.py", "record", "bx", run, "--agent", "main@1")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        nxt = self.batch(10)
        unplayed = [c for c in nxt if c not in first]
        self.assertEqual(len(unplayed), 6)  # most of the batch is new cases
        self.assertEqual(set(nxt) - set(unplayed), set(first))  # ~30% earlier failures to fix, ~20% passes to recheck
        self.assertEqual(len(self.batch(4)), 4)
        self.assertEqual(len(self.batch(40)), 12)  # never more than the development split

    def test_record_refuses_another_benchmark_commit(self):
        run = wrapped_run(self.repo, "r1", [("d0", "train", "scored", 1.0)], commit="zzz9999")
        out = self.repo.run("benchmark.py", "record", "bx", run, "--agent", "main@1")
        self.assertEqual(out.returncode, 2)
        self.assertIn("different version is a different benchmark", out.stderr)

    def test_errors_are_not_scores_and_final_runs_are_counted(self):
        run = wrapped_run(self.repo, "r1", [("d0", "train", "runtime failure", None), ("f0", "test", "scored", 0.5)])
        out = self.repo.run("benchmark.py", "record", "bx", run, "--agent", "main@1")
        self.assertIn("1 without a score", out.stdout)
        self.assertIn("final run #1", out.stdout)
        led = ledger(self.repo)
        self.assertIsNone(led["cases"]["d0"]["plays"][-1]["score"])
        self.assertEqual(led["final_runs"][0]["mean"], 0.5)

    def test_fidelity_compares_with_the_benchmarks_own_scorer(self):
        run = wrapped_run(self.repo, "r1", [("d0", "train", "scored", 1.0), ("d1", "train", "scored", 0.0)])
        self.repo.write("ref.jsonl", '{"case": "d0", "score": 1.0}\n{"case": "d1", "score": 0.0}\n')
        ok = self.repo.run("benchmark.py", "fidelity", "bx", run, "--reference", str(self.repo.root / "ref.jsonl"))
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.repo.write("ref.jsonl", '{"case": "d0", "score": 1.0}\n{"case": "d1", "score": 1.0}\n')
        bad = self.repo.run("benchmark.py", "fidelity", "bx", run, "--reference", str(self.repo.root / "ref.jsonl"))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("d1: RELAI 0.0000 vs benchmark 1.0000", bad.stdout)
        self.assertFalse(ledger(self.repo)["fidelity"]["ok"])

    def test_summarize_reads_wrapped_runs_by_split(self):
        run = wrapped_run(self.repo, "r1", [("d0", "train", "scored", 1.0), ("v0", "validation", "scored", 0.0),
                                            ("v1", "validation", "evaluator error", None)])
        out = self.repo.run("summarize.py", run, "--details")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("| benchmarks/bx | validation | 2 | 1 | 0.00 |", out.stdout)
        self.assertIn("evaluator error", out.stdout)
        self.assertNotIn("is not frozen", out.stdout)

    def test_comparison_across_benchmark_commits_warns(self):
        base = wrapped_run(self.repo, "r1", [("d0", "train", "scored", 1.0)], commit="abc1234")
        cand = wrapped_run(self.repo, "r2", [("d0", "train", "scored", 0.0)], commit="def5678")
        out = self.repo.run("summarize.py", cand, "--baseline", base)
        self.assertEqual(out.returncode, 0)
        self.assertIn("Comparison warnings:", out.stdout)
        self.assertIn("lower 1", out.stdout)

    def test_coverage_counts_played_development_cases(self):
        sample = ledger(self.repo)["held_out_sample"]
        run = wrapped_run(self.repo, "r1", [(c, "validation", "scored", 1.0 if i % 2 else 0.0) for i, c in enumerate(sample)]
                          + [("d0", "train", "scored", 1.0)])
        self.repo.run("benchmark.py", "record", "bx", run, "--agent", "main@1")
        cov = self.repo.run("benchmark.py", "coverage", "bx")
        self.assertIn("development 1/12 played", cov.stdout)

    def test_coverage_exposes_mixed_revisions_without_combining_their_scores(self):
        first = wrapped_run(self.repo, "old", [("v0", "validation", "scored", 1.0),
                                               ("d0", "train", "scored", 1.0)])
        second = wrapped_run(self.repo, "new", [("v1", "validation", "scored", 0.0),
                                                ("d1", "train", "scored", 0.0)])
        self.assertEqual(self.repo.run("benchmark.py", "record", "bx", first, "--agent", "old").returncode, 0)
        self.assertEqual(self.repo.run("benchmark.py", "record", "bx", second, "--agent", "new").returncode, 0)
        result = self.repo.run("benchmark.py", "coverage", "bx", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        cov = json.loads(result.stdout)
        for stats in (cov["roles"]["development"], cov["roles"]["held-out"], cov["held_out_sample"]):
            self.assertEqual(stats["scored"], 2)
            self.assertEqual(stats["agents"], ["new", "old"])
            self.assertIsNone(stats["mean"])
            self.assertIsNone(stats["se"])
            self.assertEqual(stats["warning"], "mixed agent revisions")
        self.assertEqual(cov["roles"]["development"]["played"], 2)
        line = self.repo.run("benchmark.py", "coverage", "bx").stdout
        self.assertIn("mean unavailable: mixed agent revisions (new, old)", line)
        self.assertNotIn("held-out sample not run", line)

    def test_coverage_requires_a_known_revision_and_retains_legacy_plays(self):
        run = wrapped_run(self.repo, "known", [("v0", "validation", "scored", 1.0),
                                               ("v1", "validation", "scored", 0.0)])
        self.repo.run("benchmark.py", "record", "bx", run, "--agent", "revision-a")
        cov = json.loads(self.repo.run("benchmark.py", "coverage", "bx", "--json").stdout)
        self.assertEqual(cov["held_out_sample"]["mean"], 0.5)
        self.assertEqual(cov["held_out_sample"]["agents"], ["revision-a"])
        self.assertIsNotNone(cov["held_out_sample"]["se"])
        path = self.repo.relai / "work/benchmarks/bx/ledger.json"
        saved = json.loads(path.read_text())
        for case in ("v0", "v1"):
            saved["cases"][case]["plays"][-1].pop("agent")
        path.write_text(json.dumps(saved))
        cov = json.loads(self.repo.run("benchmark.py", "coverage", "bx", "--json").stdout)
        self.assertEqual(cov["held_out_sample"]["scored"], 2)
        self.assertIsNone(cov["held_out_sample"]["mean"])
        self.assertEqual(cov["held_out_sample"]["agents"], [None])
        self.assertEqual(cov["held_out_sample"]["warning"], "unknown agent revision")
        self.assertEqual(json.loads(path.read_text()), saved, "coverage must not migrate legacy records")


if __name__ == "__main__":
    unittest.main()
