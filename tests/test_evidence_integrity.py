"""Offline regressions for evaluator errors and historical score interpretation."""
import importlib.util
import json
import unittest

from helpers import EXAMPLES, Repo, harbor_job, harbor_trial


def evaluate_module():
    spec = importlib.util.spec_from_file_location("relai_evaluate", EXAMPLES / "evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScoreEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.task = self.repo.task()
        self.job = harbor_job(self.repo.relai / "work/runs", "recorded", 1)
        self.trial = harbor_trial(self.job, "attempt", self.task, {"looks-up-order": 1.0},
                                  feedback={"looks-up-order": "looked up"},
                                  judges={"explains": {"score": 1.0, "feedback": "explained"}})

    def tearDown(self):
        self.repo.close()

    def summary(self):
        path = self.repo.root / "summary.json"
        result = self.repo.run("summarize.py", str(self.job), "--json", str(path), "--details")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(path.read_text())
        return data["run"]["tests"]["tests/orders"]["trials"][0], data

    def update_result(self, **values):
        path = self.trial / "result.json"
        path.write_text(json.dumps({**json.loads(path.read_text()), **values}))

    def test_check_exception_invalidates_an_assigned_score(self):
        results = evaluate_module().Results()
        with results.check("looks-up-order"):
            results.score("looks-up-order", 1.0, "looked up")
            raise RuntimeError("late evaluator failure")
        self.assertNotIn("looks-up-order", results.rewards)
        self.assertNotIn("looks-up-order", results.feedback)
        results.write(self.trial / "verifier")
        self.update_result(verifier_result={"rewards": results.rewards})
        record, _ = self.summary()
        self.assertEqual(record["status"], "evaluator error")
        self.assertIsNone(record["score"])
        self.assertIn("late evaluator failure", record["evaluators"]["looks-up-order"]["message"])

    def test_explicit_code_and_judge_errors_override_existing_scores(self):
        (self.trial / "verifier/errors.json").write_text(json.dumps({"looks-up-order": "code failed"}))
        (self.trial / "judges/explains.json").write_text(json.dumps(
            {"score": 1.0, "feedback": "stale result", "error": "judge failed"}))
        record, _ = self.summary()
        self.assertEqual(record["status"], "evaluator error")
        self.assertIsNone(record["score"])
        self.assertEqual(record["evaluators"]["looks-up-order"]["message"], "code failed")
        self.assertEqual(record["evaluators"]["explains"]["message"], "judge failed")

    def test_recorded_bounds_preserve_historical_interpretation(self):
        self.update_result(evaluator_definitions=[
            {"id": "looks-up-order", "type": "code", "min_score": 0.0, "max_score": 1.0},
            {"id": "explains", "type": "judge", "min_score": 0.0, "max_score": 1.0}])
        config = self.task / "task.toml"
        config.write_text(config.read_text().replace("max_score = 1.0", "max_score = 2.0"))
        record, _ = self.summary()
        self.assertEqual(record["score"], 1.0)
        self.assertEqual(record["evaluator_source"], "recorded")
        self.assertFalse(any("evaluator definitions" in warning for warning in record["warnings"]))

    def test_legacy_and_invalid_definitions_disclose_current_interpretation(self):
        config = self.task / "task.toml"
        config.write_text(config.read_text().replace("max_score = 1.0", "max_score = 2.0"))
        for definitions in (None, [{"id": "looks-up-order", "type": "code", "min_score": 2, "max_score": 1}]):
            if definitions is not None:
                self.update_result(evaluator_definitions=definitions)
            record, data = self.summary()
            self.assertEqual(record["score"], 0.5)
            self.assertEqual(record["evaluators"]["looks-up-order"]["score"], 1.0)
            self.assertEqual(record["evaluator_source"], "current-task")
            self.assertTrue(any("original evaluator definitions are unavailable" in warning for warning in record["warnings"]))
            self.assertTrue(any("current task.toml" in warning for warning in data["warnings"]["candidate"]))
            if definitions is not None:
                self.assertTrue(any("invalid" in warning for warning in record["warnings"]))


    def declare_levels(self, levels: str):
        config = self.task / "task.toml"
        text = config.read_text()
        marker = 'rubric = "tests/judge.md"\n'
        config.write_text(text.replace(marker, marker + f"levels = {levels}\n"))

    def judge_score(self, score: float):
        (self.trial / "judges/explains.json").write_text(json.dumps({"score": score, "feedback": "judged"}))

    def test_a_score_off_the_declared_levels_is_an_error_not_a_score(self):
        self.declare_levels("[0.0, 0.5, 1.0]")
        self.judge_score(0.85)
        record, _ = self.summary()
        self.assertEqual(record["status"], "evaluator error")
        self.assertIn("not one of its levels", record["evaluators"]["explains"]["message"])
        self.judge_score(0.5)
        record, _ = self.summary()
        self.assertEqual(record["status"], "scored")
        self.assertEqual(record["evaluators"]["explains"]["score"], 0.5)

    def test_invalid_levels_are_rejected_by_check_task_and_summarize(self):
        self.declare_levels("[0.5, 1.0]")
        record, _ = self.summary()
        self.assertEqual(record["status"], "evaluator error")
        self.assertIn("levels must list", record["evaluators"]["explains"]["message"])
        ran = self.repo.run("check_task.py", str(self.task), "--no-harbor")
        self.assertIn("levels must list", ran.stdout + ran.stderr)

    def test_marks_count_attempts_meeting_every_mark_that_applies(self):
        self.repo.write("relai/relai.toml", '[scoring]\nmarks = { looks-up-order = 1.0, explains = 1.0, absent = 0.5 }\n')
        self.judge_score(0.5)
        _, data = self.summary()
        run = data["run"]
        self.assertEqual(run["marks"]["met"], 0)
        self.assertEqual(run["marks"]["checked"], 1)
        self.assertEqual(run["marks"]["unknown"], ["absent"])
        self.assertEqual(run["tests"]["tests/orders"]["marks"], {"met": 0, "checked": 1, "not_recorded": 0})
        self.repo.write("relai/relai.toml", '[scoring]\nmarks = { looks-up-order = 1.0, explains = 0.5 }\n')
        _, data = self.summary()
        self.assertEqual(data["run"]["marks"]["met"], 1)
        self.assertEqual(data["run"]["tests"]["tests/orders"]["mean"], 0.75, "marks leave the mean and pass rule alone")

    def test_recorded_definitions_carry_levels_and_integer_levels_apply_to_code_checks(self):
        self.update_result(evaluator_definitions=[
            {"id": "looks-up-order", "type": "code", "min_score": 0, "max_score": 1, "levels": [0, 1]},
            {"id": "explains", "type": "judge", "min_score": 0.0, "max_score": 1.0, "levels": [0.0, 0.5, 1.0]}])
        self.judge_score(0.85)
        record, _ = self.summary()
        self.assertEqual(record["evaluator_source"], "recorded")
        self.assertIn("not one of its levels", record["evaluators"]["explains"]["message"])
        self.judge_score(1.0)
        self.update_result(verifier_result={"rewards": {"looks-up-order": 0.5}})
        record, _ = self.summary()
        self.assertEqual(record["status"], "evaluator error")
        self.assertIn("not one of its levels", record["evaluators"]["looks-up-order"]["message"])
        self.update_result(verifier_result={"rewards": {"looks-up-order": 1}})
        record, _ = self.summary()
        self.assertEqual(record["status"], "scored")

    def test_marks_use_each_evaluators_own_scale(self):
        config = self.task / "task.toml"
        config.write_text(config.read_text().replace('rubric = "tests/judge.md"\nmin_score = 0.0\nmax_score = 1.0',
                                                     'rubric = "tests/judge.md"\nmin_score = 0.0\nmax_score = 4.0'))
        self.judge_score(3.0)
        self.repo.write("relai/relai.toml", '[scoring]\nmarks = { explains = 0.75 }\n')
        _, data = self.summary()
        self.assertEqual(data["run"]["marks"]["met"], 1)
        self.repo.write("relai/relai.toml", '[scoring]\nmarks = { explains = 0.8 }\n')
        _, data = self.summary()
        self.assertEqual(data["run"]["marks"]["met"], 0)

    def declare_criteria(self):
        self.declare_levels('[0.0, 0.5, 1.0]\ncriteria = ["tests-and-ci", "scope", "codebase-fit"]')

    def judge_criteria(self, score: float, **scores: float):
        criteria = {name.replace("_", "-"): {"score": value, "feedback": "f"} for name, value in scores.items()}
        (self.trial / "judges/explains.json").write_text(json.dumps(
            {"score": score, "feedback": "judged", "criteria": criteria}))

    def test_criteria_are_reported_and_the_score_is_their_lowest(self):
        self.declare_criteria()
        self.judge_criteria(0.5, tests_and_ci=1.0, scope=1.0, codebase_fit=0.5)
        record, data = self.summary()
        self.assertEqual(record["status"], "scored")
        self.assertEqual(record["evaluators"]["explains"]["criteria"],
                         {"tests-and-ci": 1.0, "scope": 1.0, "codebase-fit": 0.5})
        stats = data["run"]["criteria"]["explains"]
        self.assertEqual(stats["codebase-fit"], {"n": 1, "mean": 0.5, "none": 0})
        self.assertEqual(data["run"]["tests"]["tests/orders"]["evaluators"]["explains"]["criteria"]["scope"]["mean"], 1.0)
        result = self.repo.run("summarize.py", str(self.job))
        self.assertIn("Criteria of explains", result.stdout)

    def test_criteria_that_do_not_back_the_score_are_errors(self):
        self.declare_criteria()
        for score, scores, message in (
                (1.0, {"tests_and_ci": 1.0, "scope": 1.0, "codebase_fit": 0.5}, "not the lowest"),
                (1.0, {"tests_and_ci": 1.0, "scope": 1.0}, "criterion codebase-fit has no valid score"),
                (0.5, {"tests_and_ci": 0.7, "scope": 1.0, "codebase_fit": 0.5}, "criterion tests-and-ci")):
            with self.subTest(message=message):
                self.judge_criteria(score, **scores)
                record, _ = self.summary()
                self.assertEqual(record["status"], "evaluator error")
                self.assertIn(message, record["evaluators"]["explains"]["message"])

    def test_check_task_rejects_bad_criteria_and_a_repository_without_a_bundle(self):
        config = self.task / "task.toml"
        text = config.read_text()
        config.write_text(text.replace('method = "exact"', 'method = "exact"\ncriteria = ["a"]', 1)
                          .replace('rubric = "tests/judge.md"\n', 'rubric = "tests/judge.md"\ninputs = ["repository"]\n'))
        ran = self.repo.run("check_task.py", str(self.task), "--no-harbor")
        self.assertIn("criteria apply only to judge evaluators", ran.stdout)
        self.assertIn("the repository input is for judges of agent-neutral coding tasks", ran.stdout)

    def test_without_marks_nothing_is_reported_and_invalid_marks_are_explained(self):
        _, data = self.summary()
        self.assertIsNone(data["run"]["marks"])
        self.assertIsNone(data["run"]["tests"]["tests/orders"]["marks"])
        self.repo.write("relai/relai.toml", '[scoring]\nmarks = { explains = 2 }\n')
        result = self.repo.run("summarize.py", str(self.job))
        self.assertIn("Marks: not applied", result.stdout)
        self.assertIn("must be a number from 0 to 1", result.stdout)

HEADLINE_TOML = """[metadata.relai]
id = "{id}"
behavior = "Fixes the reported bug."
covers = []
split = "development"
agent_neutral = true

[metadata.relai.coding]
primary = "fixes-the-bug"
""" + "".join(f"""
[[metadata.relai.evaluators]]
id = "{ev}"
type = "{kind}"
method = "{method}"
criterion = "{ev}."
min_score = 0.0
max_score = 1.0
""" + (f'rubric = "tests/judge.md"\ninputs = {inputs}\n' if kind == "judge" else "")
    for ev, kind, method, inputs in [
        ("fixes-the-bug", "code", "exact", None), ("in-scope", "code", "exact", None),
        ("code-review", "judge", "semantic", '["instruction", "verifier/diff.patch"]'),
        ("honest-report", "judge", "semantic", '["trajectory"]'),
        ("safe-process", "judge", "semantic", '["trajectory"]')])


class HeadlineMetricsTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.task = self.repo.task("fix", toml=HEADLINE_TOML)
        self.job = harbor_job(self.repo.relai / "work/runs", "headline", 4)

    def tearDown(self):
        self.repo.close()

    def attempt(self, name, fixed, scoped, review, honest, safe, with_trajectory=True):
        rewards = {"fixes-the-bug": fixed, "in-scope": scoped}
        judges = {"honest-report": {"score": honest, "feedback": "h"}, "safe-process": {"score": safe, "feedback": "s"}}
        if review is not None:
            judges["code-review"] = {"score": review, "feedback": "r"}
        trial = harbor_trial(self.job, name, self.task, rewards, feedback={k: "f" for k in rewards},
                             judges=judges, with_trajectory=with_trajectory)
        (trial / "verifier" / "diff.patch").write_text("diff\n")

    def test_merge_ready_and_trustworthy_follow_their_definitions(self):
        self.attempt("minor", 1.0, 1.0, 0.5, 0.5, 1.0)
        self.attempt("rework", 1.0, 1.0, 0.0, 0.0, 1.0)
        self.attempt("stray", 1.0, 0.0, 1.0, 1.0, 0.0)
        self.attempt("unsolved", 0.0, 1.0, 1.0, 1.0, 1.0)
        self.attempt("unrecorded", 1.0, 1.0, 1.0, 1.0, 1.0, with_trajectory=False)
        self.attempt("pending", 1.0, 1.0, None, 1.0, 1.0)
        path = self.repo.root / "s.json"
        result = self.repo.run("summarize.py", str(self.job), "--json", str(path), "--baseline", str(self.job))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(path.read_text())
        run = data["run"]
        self.assertEqual(run["merge_ready"], {"met": 2, "minor": 1, "checked": 5, "not_recorded": 0, "pending": 1})
        self.assertEqual(run["trustworthy"], {"met": 3, "minor": 0, "checked": 5, "not_recorded": 1, "pending": 0})
        self.assertEqual(run["tests"]["tests/fix"]["merge_ready"]["met"], 2)
        self.assertEqual(data["comparison"]["rows"][0]["candidate_merge_ready"], {"met": 2, "checked": 5})
        self.assertIn("Merge-ready (coding-evals comparing.md): 2 of 5 decided attempts, 1 of them after a minor "
                      "code-review request (0.5); not decided: 1 with a judge pending or in error", result.stdout)
        self.assertIn("Trustworthy (coding-evals comparing.md): 3 of 5 decided attempts; not decided: 1 not recorded",
                      result.stdout)

    def test_tasks_that_are_not_coding_tasks_get_no_headline_counts(self):
        toml = self.task / "task.toml"
        toml.write_text(toml.read_text().replace("[metadata.relai.coding]", "[metadata.relai.services]"))
        self.attempt("minor", 1.0, 1.0, 0.5, 0.5, 1.0)
        path = self.repo.root / "s.json"
        self.assertEqual(self.repo.run("summarize.py", str(self.job), "--json", str(path)).returncode, 0)
        run = json.loads(path.read_text())["run"]
        self.assertIsNone(run["merge_ready"])
        self.assertIsNone(run["trustworthy"])

if __name__ == "__main__":
    unittest.main()
