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


if __name__ == "__main__":
    unittest.main()
