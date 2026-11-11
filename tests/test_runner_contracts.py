"""Selection, runner-aware contracts and prerequisite checks, using synthetic local fixtures."""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from helpers import Repo, TEMPLATE, GOOD_TASK_TOML, harbor_job, harbor_trial, trajectory


def module(name):
    path = TEMPLATE / "bin" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"relai_{name}", path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.task = self.repo.task()

    def tearDown(self):
        self.repo.close()

    def test_overall_paired_delta_describes_equal_mean_without_inference(self):
        tasks = [self.task] + [self.repo.task(f"t{i}") for i in range(1, 6)]
        base_scores = [0.0, 1.0, 0.5, 0.0, 1.0, 0.5]
        cand_scores = [1.0, 0.0, 0.5, 0.5, 1.0, 0.0]  # mixed per-test changes, zero mean
        for name, scores in (("b", base_scores), ("c", cand_scores)):
            job = harbor_job(self.repo.root / "runs" / name, "job", len(tasks))
            for task, score in zip(tasks, scores):
                harbor_trial(job, task.name, task, {"looks-up-order": score}, feedback={"looks-up-order": "f"},
                             judges={"explains": {"score": score, "feedback": "f"}})
        result = self.repo.run("summarize.py", str(self.repo.root / "runs" / "c"),
                               "--baseline", str(self.repo.root / "runs" / "b"), "--json",
                               str(self.repo.root / "s.json"))
        overall = json.loads((self.repo.root / "s.json").read_text())["comparison"]["overall"]
        self.assertEqual(overall["tests"], 6)
        self.assertAlmostEqual(overall["mean_delta"], 0.0)
        self.assertEqual((overall["higher"], overall["lower"], overall["equal"]), (2, 2, 2))
        self.assertIn("Overall, paired over 6 tests", result.stdout)
        self.assertEqual(overall["observed_change"], "equal")
        self.assertNotIn("improved", result.stdout.split("Overall")[1])

    def test_runs_from_different_runners_warn_and_compare(self):
        for name, runner in (("b", None), ("c", "native")):
            job = harbor_job(self.repo.root / "runs" / name, "job", 2)
            for i in range(2):
                trial = harbor_trial(job, f"t{i}", self.task, {"looks-up-order": 1.0}, feedback={"looks-up-order": "f"},
                                     judges={"explains": {"score": 1.0, "feedback": "f"}})
                if runner:
                    data = json.loads((trial / "result.json").read_text())
                    data["runner"] = runner
                    (trial / "result.json").write_text(json.dumps(data))
        result = self.repo.run("summarize.py", str(self.repo.root / "runs" / "c"),
                               "--baseline", str(self.repo.root / "runs" / "b"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Comparison warnings:", result.stdout)
        self.assertNotIn("improved", result.stdout)


class RunnerContractTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.task = self.repo.task()

    def tearDown(self):
        self.repo.close()

    def config(self, text='kind = "native"\nisolation = "host"', scoring='pass_mark = 0.8'):
        self.repo.write('relai/relai.toml', f'[runner]\n{text}\n[scoring]\n{scoring}\n[judge]\nmode = "subagent"\n')

    def check(self, *extra):
        return self.repo.run('check_task.py', str(self.task), *extra)

    def test_native_skips_unused_harbor_structure_and_configuration(self):
        self.config()
        for name in ('instruction.md', 'tests/test.sh', 'environment/Dockerfile', 'tests/Dockerfile'):
            (self.task / name).unlink()
        with (self.repo.relai / 'relai.toml').open('a') as f:
            f.write('\n[harbor]\nimage = "unused-invalid-image"\n')
        out = self.check()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn('native runner', out.stdout)
        rejected = self.check('--verifier')
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('--verifier is Harbor-only', rejected.stdout)
        (self.task / 'task.toml').write_text('[metadata.relai]\nid = "orders"\n')
        self.assertNotEqual(self.check().returncode, 0, 'shared task/evaluator contracts remain required')

    def test_invalid_runner_or_isolation_never_defaults_to_harbor(self):
        for settings in ('kind = "unknown"', 'kind = "native"\nisolation = "unknown"',
                         'kind = "harbor"\nisolation = "host"'):
            with self.subTest(settings=settings):
                self.config(settings)
                out = self.check()
                self.assertNotEqual(out.returncode, 0)
                self.assertNotIn('Harbor cannot load', out.stdout)
        self.repo.write('relai/relai.toml', 'runner = "native"')
        out = self.check()
        self.assertNotEqual(out.returncode, 0)
        self.assertIn('[runner] must be a table', out.stdout)

    def test_scoring_threshold(self):
        common = module('_common')
        self.assertIsNone(common.pass_mark({}))
        self.assertIsNone(common.pass_mark({'harbor': {'pass_mark': 0.8}}))
        self.assertEqual(common.runner_settings(self.repo.relai), ('harbor', 'container'))
        self.assertEqual(common.pass_mark({'scoring': {'pass_mark': 0.8}}), 0.8)
        for config in ({'scoring': {'pass_mark': True}}, {'scoring': {'pass_mark': 80}},
                       {'scoring': {'pass_mark': float('nan')}}):
            with self.assertRaises(ValueError):
                common.pass_mark(config)

    def test_native_checks_still_scan_configuration_and_tasks_for_secrets(self):
        self.config()
        canary = 'synthetic-private-canary-value'
        self.repo.write('relai/.env', f'TEST_KEY={canary}\n')
        with (self.repo.relai / 'relai.toml').open('a') as f:
            f.write(f'\n[fixture]\nleaked = "{canary}"\n')
        self.repo.write('relai/tests/orders/leak.txt', canary)
        out = self.check()
        self.assertNotEqual(out.returncode, 0)
        self.assertIn('contains the value of TEST_KEY', out.stdout)
        self.assertNotIn(canary, out.stdout + out.stderr)

    def test_native_trajectory_check_skips_optional_harbor_validator(self):
        self.config()
        path = self.repo.write('trajectory.json', json.dumps(trajectory([
            {'source': 'user', 'message': 'hello'}, {'source': 'agent', 'message': 'hi'}])))
        checker = module('check_trajectory')
        with patch.object(sys, 'argv', ['check_trajectory.py', str(path), '--relai-dir', str(self.repo.relai)]), \
             patch.object(checker, 'harbor_validate', side_effect=AssertionError('Harbor invoked')), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(), 0)

    def test_wrapped_measurement_identity_changes_warn(self):
        for run, identity in (("before", "own-scorer"), ("after", "different-scorer")):
            self.repo.write(f"relai/work/runs/{run}/relai-results.jsonl", json.dumps({
                "benchmark": "bx", "case": "a", "score": 1.0, "benchmark_commit": "same",
                "runner_id": identity}) + "\n")
        out = self.repo.run("summarize.py", str(self.repo.relai / "work/runs/after"),
                            "--baseline", str(self.repo.relai / "work/runs/before"))
        self.assertEqual(out.returncode, 0)
        self.assertIn("Comparison warnings:", out.stdout)

    def test_disjoint_runs_with_different_runners_warn_without_matched_rows(self):
        other = self.repo.task('different-issue')
        runs = self.repo.relai / 'work/runs'
        before = harbor_trial(harbor_job(runs, 'before', 1), 't1', self.task,
                              {'looks-up-order': 1.0}, judges={'explains': {'score': 1.0}})
        after = harbor_trial(harbor_job(runs, 'after', 1), 't2', other,
                             {'looks-up-order': 1.0}, judges={'explains': {'score': 1.0}})
        path = after / 'result.json'
        data = json.loads(path.read_text())
        path.write_text(json.dumps(data | {'runner': 'native', 'runner_id': 'native'}))
        out = self.repo.run('summarize.py', str(after.parent), '--baseline', str(before.parent))
        self.assertEqual(out.returncode, 0)
        self.assertIn('Integrity warnings:', out.stdout)

    def test_mixed_measurement_identities_within_a_test_warn(self):
        runs = self.repo.relai / 'work/runs'
        for side in ('before', 'after'):
            job = harbor_job(runs, side, 2)
            for i, identity in enumerate(('one', 'two')):
                trial = harbor_trial(job, f't{i}', self.task, {'looks-up-order': 1.0},
                                     judges={'explains': {'score': 1.0}})
                path = trial / 'result.json'
                data = json.loads(path.read_text())
                path.write_text(json.dumps(data | {'runner': 'native', 'runner_id': identity}))
        out = self.repo.run('summarize.py', str(runs / 'after'), '--baseline', str(runs / 'before'))
        self.assertEqual(out.returncode, 0)
        self.assertIn('Integrity warnings:', out.stdout)
