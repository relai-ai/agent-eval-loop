"""Descriptive reports preserve evidence without imposing improvement or confidence gates."""
import json
import unittest
from helpers import Repo, harbor_job, harbor_trial


class DescriptiveSummaryTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.task = self.repo.task()

    def tearDown(self):
        self.repo.close()

    def run_data(self, name, scores, task=None, checksum='same'):
        task = task or self.task
        job = harbor_job(self.repo.relai / 'work/runs', name, len(scores))
        for index, score in enumerate(scores):
            harbor_trial(job, f't{index}', task,
                         {'looks-up-order': score} if score is not None else None,
                         checksum=checksum, exception='FixtureFailure' if score is None else None,
                         feedback={'looks-up-order': 'synthetic feedback'},
                         judges={'explains': {'score': score, 'feedback': 'synthetic feedback'}} if score is not None else None)
        return job

    def compare(self, base, cand, *args):
        out = self.repo.root / 'summary.json'
        result = self.repo.run('summarize.py', str(cand), '--baseline', str(base), '--json', str(out), *args)
        return result, json.loads(out.read_text())

    def test_constant_sparse_scores_are_observations_not_certainty(self):
        result, data = self.compare(self.run_data('before', [0.0, 0.0]), self.run_data('after', [1.0, 1.0]))
        self.assertEqual(result.returncode, 0, result.stderr)
        row = data['comparison']['rows'][0]
        self.assertEqual((row['observed_change'], row['noise']), ('higher', 0.0))
        self.assertEqual((row['baseline_scored'], row['candidate_scored']), (2, 2))
        self.assertIn('does not establish confidence', result.stdout)
        self.assertNotIn('improved', result.stdout)
        self.assertNotIn('regressed', result.stdout)

    def test_unequal_counts_keep_unavailable_spread_null(self):
        result, data = self.compare(self.run_data('before', [1.0]), self.run_data('after', [1.0, 1.0, 1.0]))
        row = data['comparison']['rows'][0]
        self.assertEqual((row['observed_change'], row['attempts'], row['noise']), ('equal', '1/3', None))
        self.assertIsNone(data['baseline']['tests']['tests/orders']['stdev'])
        self.assertEqual(data['run']['tests']['tests/orders']['stdev'], 0.0)
        self.assertIsNone(data['comparison']['overall']['se'])
        self.assertIn('equivalence', result.stdout)

    def test_unscored_evidence_is_not_comparable_or_zero(self):
        result, data = self.compare(self.run_data('before', [None]), self.run_data('after', [1.0]))
        row = data['comparison']['rows'][0]
        self.assertEqual((row['observed_change'], row['delta'], row['baseline']), ('not-comparable', None, None))
        self.assertIsNone(data['comparison']['overall'])
        self.assertIn('runtime failure 1', result.stdout)
        self.assertEqual(data['baseline']['tests']['tests/orders']['trials'][0]['status'], 'runtime failure')

    def test_details_and_concise_output_have_identical_complete_json(self):
        base, cand = self.run_data('before', [0.0, 0.5]), self.run_data('after', [0.5, 1.0])
        short, data = self.compare(base, cand)
        detailed, full = self.compare(base, cand, '--details')
        self.assertEqual(data, full)
        self.assertNotIn('| tests/orders |', short.stdout)
        self.assertIn('| tests/orders |', detailed.stdout)
        self.assertIn('Integrity warnings:', short.stdout)
        self.assertTrue(data['warnings']['candidate'])
        trials = data['run']['tests']['tests/orders']['trials']
        self.assertEqual(len(trials), 2)
        self.assertTrue(all(t['dir'] and t['evaluators'] for t in trials))

    def test_unmatched_cases_are_exposed_and_excluded_from_delta(self):
        base = self.run_data('before', [1.0])
        other = self.repo.task('another-issue')
        cand = self.run_data('after', [1.0], task=other)
        result, data = self.compare(base, cand)
        self.assertEqual(data['comparison']['rows'], [])
        self.assertEqual(data['comparison']['baseline only'], ['tests/orders'])
        self.assertEqual(data['comparison']['candidate only'], ['tests/another-issue'])
        self.assertIn('baseline only: 1 test(s)', result.stdout)

    def test_missing_resource_measurements_are_not_reported_as_zero(self):
        job = self.run_data('run', [1.0, 1.0])
        for path in job.glob('*/result.json'):
            result = json.loads(path.read_text())
            result['agent_result'] = {'n_input_tokens': 10}
            path.write_text(json.dumps(result))
        result, data = self.compare(job, job)
        self.assertIsNone(data['run']['usage']['cost_usd'])
        self.assertIsNone(data['run']['usage']['n_output_tokens'])
        self.assertEqual(data['run']['usage_counts']['n_input_tokens'], 2)
        self.assertIn('cost_usd not measured', result.stdout)
        self.assertNotIn('$0.0000', result.stdout)

    def test_changed_runner_and_test_versions_are_advisory_and_keep_numeric_delta(self):
        base = self.run_data('before', [0.0], checksum='v1')
        cand = self.run_data('after', [1.0], checksum='v2')
        path = next(cand.glob('*/result.json'))
        path.write_text(json.dumps(json.loads(path.read_text()) | {'runner': 'native', 'runner_id': 'other'}))
        result, data = self.compare(base, cand, '--details')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['comparison']['rows'][0]['delta'], 1.0)
        self.assertNotIn('refused', data['comparison'])
        warnings = data['warnings']['comparison']
        self.assertTrue(any('different runners' in w for w in warnings))
        self.assertTrue(any('different test versions' in w for w in warnings))
        self.assertIn('different test versions', result.stdout)

    def test_mixed_and_missing_identity_notices_cover_run_and_baseline(self):
        base = self.run_data('before', [0.0, 1.0])
        cand = self.run_data('after', [0.5, 1.0])
        for job in (base, cand):
            paths = sorted(job.glob('*/result.json'))
            first = json.loads(paths[0].read_text()) | {'task_checksum': 'old', 'runner': 'native'}
            second = json.loads(paths[1].read_text()) | {'task_checksum': 'new', 'runner': 'native', 'runner_id': 'new'}
            paths[0].write_text(json.dumps(first))
            paths[1].write_text(json.dumps(second))
        result, data = self.compare(base, cand)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data['comparison']['rows'][0]['delta'], 0.25)
        for side in ('candidate', 'baseline'):
            warnings = data['warnings'][side]
            self.assertTrue(any('mixed test versions' in w for w in warnings))
            self.assertTrue(any('mixed runner identities' in w for w in warnings))
            self.assertTrue(any('runner_id is missing' in w for w in warnings))
        path = next(cand.glob('*/result.json'))
        record = json.loads(path.read_text())
        record.pop('task_checksum')
        path.write_text(json.dumps(record))
        _, data = self.compare(base, cand)
        self.assertTrue(any('test version identity is missing' in w for w in data['warnings']['candidate']))

    def test_malformed_trajectory_notice_preserves_available_score(self):
        for index, text in enumerate(('invalid json', '[]')):
            with self.subTest(text=text):
                base = self.run_data(f'before{index}', [0.0])
                cand = self.run_data(f'after{index}', [1.0])
                trajectory = next(cand.glob('*/agent/trajectory.json'))
                trajectory.write_text(text)
                result, data = self.compare(base, cand)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(data['run']['tests']['tests/orders']['mean'], 1.0)
                self.assertEqual(data['comparison']['rows'][0]['delta'], 1.0)
                self.assertTrue(any('trajectory JSON' in w for w in data['warnings']['candidate']))
                self.assertEqual(trajectory.read_text(), text)
