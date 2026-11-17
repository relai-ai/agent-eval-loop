"""Status, grader preview and candidate helpers, spend records and invalid attempts."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import EXAMPLES, PLUGIN, TEMPLATE, Repo, harbor_job, harbor_trial, trajectory
from test_examples import ADAPTER, load


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_status_reads_records_and_keeps_only_the_stage(self):
        self.repo.write("relai/wiki/risks/a.md", "# Risk A\nStatus: confirmed\n")
        self.repo.write("relai/wiki/risks/b.md", "# Risk B\nStatus: proposed\n")
        self.repo.write("relai/wiki/risks/c.md", "# Risk C\nStatus: resolved\n")
        self.repo.write("relai/wiki/open-questions/q.md", "# Q\n")
        self.repo.write("relai/changes.md", "# Changes\n\n## 2026-11-16 · c1: tighter sourcing\n\nVerdict: rejected, "
                                            "a target dropped.\n\n## 2026-11-17 · c2: report contract\n\nVerdict: kept.\n")
        result = self.repo.run("status.py", "--stage", "improve", "6", "--plan-step", "Step 6")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("improve 6/8 · Keep or reject · Step 6", result.stdout)
        self.assertIn("● 1 confirmed", result.stdout)
        self.assertIn("✓ 1 resolved", result.stdout)
        self.assertIn("c1 ✗ · c2 ✓", result.stdout)
        self.assertIn("1 open question(s)", result.stdout)
        status = json.loads((self.repo.relai / "STATUS.json").read_text())
        self.assertEqual(status["active"]["skill"], "improve")
        self.assertEqual([c["verdict"] for c in status["candidates"]], ["rejected", "kept"])
        again = self.repo.run("status.py")
        self.assertIn("improve 6/8", again.stdout)

    def test_unknown_costs_stay_unknown_and_bad_stage_is_a_usage_error(self):
        self.repo.write("relai/records/spend.jsonl", json.dumps({"tool": "judge", "cost_usd": None}) + "\n")
        result = self.repo.run("status.py")
        self.assertIn("helpers outside runs unknown recorded · 1 call(s) with unknown cost", result.stdout)
        self.assertIn("discover ○", result.stdout)
        self.assertEqual(self.repo.run("status.py", "--stage", "improve", "99").returncode, 2)
        self.assertEqual(self.repo.run("status.py", "--stage", "nope", "1").returncode, 2)
        missing = self.repo.run("status.py", "--relai-dir", str(self.repo.root / "absent"))
        self.assertEqual(missing.returncode, 2)
        self.assertNotIn("Traceback", missing.stderr)

    def test_stage_names_match_the_board_and_the_coding_evals_skill(self):
        sys.path.insert(0, str(TEMPLATE / "bin"))
        import status
        board = (TEMPLATE / "docs/board.md").read_text()
        keys = {"`eval` (build)": "eval", "`eval` (run)": "eval-run", "`loop` (each iteration)": "loop"}
        found = {}
        section = board.split("## Stages", 1)[1].split("\n## ", 1)[0]
        for line in [l for l in section.splitlines() if l.startswith("| `")]:
            label, stages = [c.strip() for c in line.strip("|").split("|")]
            names = [re.sub(r"^\d+ ", "", s.replace("★", "").strip()) for s in stages.split(" · ")]
            found[keys.get(label, label.strip("`"))] = names
        self.assertEqual(found, status.STAGES)
        skill = (PLUGIN / "skills/coding-evals/SKILL.md").read_text()
        for name in status.STAGES["coding-evals"]:
            self.assertIn(name, skill)


class CandidateTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.target = self.repo.task("target")
        self.guard = self.repo.task("guard")

    def tearDown(self):
        self.repo.close()

    def run_data(self, name, target, guard):
        job = harbor_job(self.repo.relai / "work/runs", name, len(target) + len(guard))
        for task, scores, prefix in ((self.target, target, "t"), (self.guard, guard, "g")):
            for index, score in enumerate(scores):
                harbor_trial(job, f"{prefix}{index}", task, {"looks-up-order": score},
                             feedback={"looks-up-order": "f"}, judges={"explains": {"score": score, "feedback": "f"}})
        return job

    def test_card_labels_targets_and_gives_notices_not_verdicts(self):
        self.repo.write("relai/records/improve/plan.json", json.dumps({"targets": ["tests/target"]}))
        base = self.run_data("base", [0.0], [1.0, 1.0])
        cand = self.run_data("cand", [1.0], [0.0, 1.0])
        result = self.repo.run("candidate.py", "compare", "c1", "--baseline", str(base), "--candidate", str(cand))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("target    tests/target: 0.00 -> 1.00", result.stdout)
        self.assertIn("rests on a single scored attempt", result.stdout)
        self.assertIn("tests/guard: guardrail dropped", result.stdout)
        self.assertNotIn("accept", result.stdout.lower())
        partial = self.run_data("partial", [1.0], [])
        missing = self.repo.run("candidate.py", "compare", "c2", "--baseline", str(base), "--candidate", str(partial))
        self.assertIn("baseline only (not compared): tests/guard", missing.stdout)

    def test_new_creates_a_worktree_outside_the_users_checkout(self):
        git = ["git", "-C", str(self.repo.root)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"],
                       check=True)
        result = self.repo.run("candidate.py", "new", "c1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.repo.relai / "work/candidates/c1/.git").exists())
        self.assertEqual(self.repo.run("candidate.py", "new", "c1").returncode, 2)
        self.assertEqual(self.repo.run("candidate.py", "new", "../x").returncode, 2)


class PreviewTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.task = self.repo.task()

    def tearDown(self):
        self.repo.close()

    def test_usage_errors_are_reported_before_any_scoring(self):
        case = self.repo.root / "cases/pass"
        case.mkdir(parents=True)
        missing = self.repo.run("preview.py", str(self.task), str(case))
        self.assertEqual(missing.returncode, 2)
        self.assertIn("trajectory.json", missing.stderr)
        (case / "trajectory.json").write_text(json.dumps(trajectory([{"source": "agent", "message": "ok"}])))
        unknown = self.repo.run("preview.py", str(self.task), str(case), "--evaluators", "nope")
        self.assertEqual(unknown.returncode, 2)
        no_judge = self.repo.run("preview.py", str(self.task), str(case), "--evaluators", "explains", "--dry-run")
        self.assertEqual(no_judge.returncode, 2)
        self.assertIn("relai/bin/judge.py", no_judge.stderr)

    def test_dry_run_records_a_round_with_grader_digests(self):
        (self.repo.relai / "bin/judge.py").write_text((EXAMPLES / "judge.py").read_text())
        self.repo.write("relai/relai.toml", '[judge]\nmodel = "m"\n\n[pricing."m"]\ninput = 5.0\n')
        case = self.repo.root / "cases/pass"
        case.mkdir(parents=True)
        (case / "trajectory.json").write_text(json.dumps(trajectory([{"source": "agent", "message": "ok"}])))
        result = self.repo.run("preview.py", str(self.task), str(case), "--evaluators", "explains", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = next((self.repo.relai / "records/eval").glob("*-grader-preview.md")).read_text()
        self.assertIn("## tests/orders · round recorded", record)
        self.assertIn("explains rubric ", record)
        self.assertIn("| explains | pass | dry run |", record)
        self.assertNotIn("spend.jsonl", [p.name for p in (self.repo.relai / "records").glob("*")])


class SpendAndInvalidTest(unittest.TestCase):
    def test_judge_prices_tokens_and_appends_to_the_ledger(self):
        repo = Repo()
        try:
            judge = load("judge")
            repo.write("relai/.env", "ANTHROPIC_API_KEY=sk-ant-test-0123456789abcdefghij\n")
            repo.write("relai/relai.toml", '[judge]\nmodel = "m"\n\n[pricing."m"]\ninput = 5.0\noutput = 25.0\n'
                                           'cache_read = 0.5\n')
            self.assertEqual(judge.priced_cost(repo.relai, "m", {"input_tokens": 1000, "output_tokens": 100,
                                                                 "cache_read_input_tokens": 2000}), 0.0085)
            self.assertIsNone(judge.priced_cost(repo.relai, "other", {"input_tokens": 1}))
            judge.post = lambda url, headers, body: {"stop_reason": "end_turn", "model": "m",
                                                     "usage": {"input_tokens": 1000, "output_tokens": 100},
                                                     "content": [{"type": "text",
                                                                  "text": '{"score": 1, "feedback": "ok"}'}]}
            ev = {"id": "explains", "type": "judge", "rubric": "tests/judge.md", "criterion": "c"}
            task = repo.task()
            run_trial = repo.relai / "work/runs/r/t0"
            judge.judge_one({"model": "m"}, repo.relai, task, ev, trajectory([{"source": "agent", "message": "ok"}]),
                            {}, run_trial)
            self.assertFalse((repo.relai / "records/spend.jsonl").exists())
            result = judge.judge_one({"model": "m"}, repo.relai, task, ev,
                                     trajectory([{"source": "agent", "message": "ok"}]), {},
                                     repo.relai / "work/preview/orders/pass", ledger=True)
            self.assertEqual((result["cost_usd"], result["cost_source"]), (0.0075, "pricing"))
            entry = json.loads((repo.relai / "records/spend.jsonl").read_text().splitlines()[-1])
            self.assertEqual((entry["tool"], entry["cost_usd"], entry["ref"]),
                             ("judge", 0.0075, "work/preview/orders/pass"))
        finally:
            repo.close()

    def test_invalid_attempt_is_an_error_for_every_evaluator(self):
        evaluate = load("evaluate")
        traj = trajectory([{"source": "agent", "message": ""}], final_metrics={"extra": {"run_status": "timeout"}})
        self.assertEqual(evaluate.run_status(traj), "timeout")
        results = evaluate.Results(["a", "b"])
        results.invalid("the agent's run ended with status 'timeout'")
        with tempfile.TemporaryDirectory() as directory:
            results.write(Path(directory))
            self.assertEqual(json.loads((Path(directory) / "reward.json").read_text()), {})
            self.assertEqual(set(json.loads((Path(directory) / "errors.json").read_text())), {"a", "b"})

    def test_launcher_exits_6_when_the_run_did_not_finish(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            adapter = ADAPTER.replace('"steps": steps}', '"steps": steps, "final_metrics": {"extra": '
                                                         '{"run_status": "timeout"}}}')
            (tmp / "adapter.py").write_text(adapter)
            (tmp / "scenario.json").write_text(json.dumps({"turns": ["first"]}))
            result = subprocess.run(
                [sys.executable, str(EXAMPLES / "launcher.py"), "--scenario", str(tmp / "scenario.json"),
                 "--trajectory", str(tmp / "trajectory.json"), "--adapter", f"{sys.executable} {tmp / 'adapter.py'}"],
                capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=60)
            self.assertEqual(result.returncode, 6, result.stderr)
            self.assertIn("invalid", result.stderr)


class WithinNoiseTest(unittest.TestCase):
    def test_comparison_reports_within_noise(self):
        repo = Repo()
        try:
            task = repo.task()
            jobs = []
            for name, scores in (("base", [0.5, 0.7]), ("cand", [0.6, 0.8])):
                job = harbor_job(repo.relai / "work/runs", name, 2)
                for index, score in enumerate(scores):
                    harbor_trial(job, f"t{index}", task, {"looks-up-order": score}, feedback={"looks-up-order": "f"},
                                 judges={"explains": {"score": score, "feedback": "f"}})
                jobs.append(job)
            out = repo.root / "c.json"
            result = repo.run("summarize.py", str(jobs[1]), "--baseline", str(jobs[0]), "--json", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIs(json.loads(out.read_text())["comparison"]["rows"][0]["within_noise"], True)
            self.assertIn("Within noise", result.stdout)
        finally:
            repo.close()


if __name__ == "__main__":
    unittest.main()
