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

    def test_without_marks_nothing_is_reported_and_invalid_marks_are_explained(self):
        _, data = self.summary()
        self.assertIsNone(data["run"]["marks"])
        self.assertIsNone(data["run"]["tests"]["tests/orders"]["marks"])
        self.repo.write("relai/relai.toml", '[scoring]\nmarks = { explains = 2 }\n')
        result = self.repo.run("summarize.py", str(self.job))
        self.assertIn("Marks: not applied", result.stdout)
        self.assertIn("must be a number from 0 to 1", result.stdout)

if __name__ == "__main__":
    unittest.main()
