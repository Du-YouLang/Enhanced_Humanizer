"""Meaningful P6 checks: immutable identities, fair environments, and missing data accounting."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from workbench.benchmark import (ARMS, REQUIRED_METRICS, check_manifest, digest,
                                 freeze_manifest, plan, same_pool, summarize, validate_result)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_evaluate_linux import validate_source_links, task_path


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((Path(__file__).resolve().parents[1]/'configs/benchmark-p6-v2.json').read_text())

    def test_immutable_task_material_and_original_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'manifest.json'
            raw = check_manifest(self.manifest)
            first = freeze_manifest(raw, path)
            self.assertEqual(freeze_manifest(raw, path), first)
            changed = copy.deepcopy(raw)
            changed['tasks'][0]['base_commit'] = 'a'*40
            with self.assertRaises(ValueError): freeze_manifest(changed, path)
            first['tasks'].pop()
            with self.assertRaises(ValueError): check_manifest(first)

    def test_unrun_tasks_are_not_zero_success_or_zero_cost(self):
        rows = plan(self.manifest)
        self.assertEqual(len(rows), 96)
        summary = summarize(rows)
        for arm in ARMS:
            self.assertEqual(summary['arms'][arm]['completion_rate'], 'unavailable')
            self.assertEqual(summary['arms'][arm]['metrics']['api_cash_usd']['total'], 'unavailable')
            self.assertEqual(summary['arms'][arm]['outcomes'], {'NOT_RUN': 16})
        self.assertNotIn('patch', json.dumps(self.manifest))
        self.assertEqual(sum(task['preparation_status'] == 'NOT_RUN_MISSING_MATERIAL' for task in self.manifest['tasks']), 4)

    def test_science_ready_requires_real_material_identities(self):
        raw=check_manifest(self.manifest)
        task=next(t for t in raw['tasks'] if t['family']=='scientific')
        task.update(preparation_status='READY',paper='unspecified paper',data_sha256='fake',gold_sha256='fake',
                    license='unspecified',tolerances={'atol':.01},invariants=['check'])
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            freeze_manifest(raw,Path(directory)/'bad-science.json')

    def real_row(self):
        row = plan(self.manifest)[0]
        preparation = dict(status='READY', task_id=row['task_id'], env_sha256='a'*64,
                           hardware_sha256='b'*64, permissions_sha256='c'*64,
                           base_commit=self.manifest['tasks'][0]['base_commit'], hidden_suite_sha256='d'*64)
        row.update({key: preparation[key] for key in ('env_sha256', 'hardware_sha256', 'permissions_sha256', 'base_commit', 'hidden_suite_sha256')})
        row.update(outcome='PASS', evidence_kind='REAL_MODEL', time_cap_seconds=1200,
                   evidence_sha256='e'*64, run_contract_sha256='f'*64,
                   independent_acceptance='PASS', head_commit='a'*40,
                   metrics={key: 'unavailable' for key in REQUIRED_METRICS})
        row['metrics'].update(end_to_end_seconds=20, api_upper_bound_usd=.01, subscription_turns=0)
        return row, preparation

    def test_mock_score_changed_hardware_or_time_cannot_pass(self):
        row, preparation = self.real_row()
        validate_result(row, self.manifest, preparation)
        for key, bad in [('evidence_kind', 'MOCK'), ('hardware_sha256', 'f'*64),
                         ('independent_acceptance', 'FAIL'), ('time_cap_seconds', 1300),
                         ('model_identity', 'some-other-model')]:
            changed = copy.deepcopy(row); changed[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_result(changed, self.manifest, preparation)
        changed = copy.deepcopy(row); changed['metrics']['input_tokens'] = True
        with self.assertRaises(ValueError): validate_result(changed, self.manifest, preparation)

    def test_failed_unknown_measurements_retained_and_no_seed_selection(self):
        row, _ = self.real_row()
        failed = copy.deepcopy(row); failed.update(task_id=self.manifest['tasks'][1]['task_id'], outcome='INFRA_FAIL')
        failed['metrics']['end_to_end_seconds'] = 'unavailable'
        result = summarize([row, failed])['arms']['A']
        self.assertEqual(result['attempted'], 2)
        self.assertEqual(result['completion_rate'], .5)
        self.assertEqual(result['metrics']['end_to_end_seconds']['known_sum'], 20)
        self.assertEqual(result['metrics']['end_to_end_seconds']['total'], 'unavailable')
        self.assertEqual(result['api_cash_per_success'], 'unavailable')
        with self.assertRaises(ValueError): summarize([row, row])

    def test_judge_and_merge_comparisons_bind_the_same_public_pool(self):
        one = dict(pool_sha256='a'*64, rubric_sha256='b'*64, public_evidence_sha256='c'*64)
        two = copy.deepcopy(one)
        self.assertTrue(same_pool([one, two]))
        two['public_evidence_sha256'] = digest({'leaked_hidden_answer': 'anything'})
        with self.assertRaises(ValueError): same_pool([one, two])

    def test_hidden_paths_and_source_links_do_not_escape(self):
        for name in ('../answer.py', '/private/answer.py', 'tests/../../answer.py', '.git/config'):
            with self.subTest(name=name), self.assertRaises(ValueError): task_path(name)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';root.mkdir();(root/'actual').write_text('fixture')
            try:(root/'internal').symlink_to('actual')
            except OSError:self.skipTest('Platform does not permit test symlinks')
            (root/'generated-doc').symlink_to('missing-generated-file')
            validate_source_links(root)
            (root/'outside').symlink_to('../outside-file')
            with self.assertRaises(ValueError):validate_source_links(root)

    def test_phase_budget_is_closed_until_p6_authorization(self):
        from p1_budget import Ledger, BudgetDenied
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(BudgetDenied):Ledger(Path(directory)/'ledger.json', phase='P6')
            self.assertFalse((Path(directory)/'ledger.json').exists())


if __name__ == '__main__':
    unittest.main()
