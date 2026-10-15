"""Meaningful guards for evidence-bound reporting; fixtures are synthetic only."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from p6_pi_full_analysis import summarize, validate_input


def fixture():
    rows = []
    for t in range(16):
        for p in range(4):
            for m in ('deepseek', 'subscription'):
                rows.append({'task_id': f'task{t}', 'profile': f'P{p}', 'provider': m,
                             'original_outcome': 'FAIL', 'official_status': 'FAIL',
                             'cohort': 'retained_original16' if t < 2 else 'missing112',
                             'head_commit': 'a'*40, 'result_sha256': 'b'*64,
                             'coding_and_public_seconds': 'unavailable' if t == 0 else 10})
    return {'pi_rows': rows, 'main_rows': [{'task_id': t, 'arm': a, 'official_status': 'PASS'} for t in range(16) for a in 'ABCDEF'],
            'ledger': {'actual_cash_usd': 'unavailable', 'settled_requests': 8, 'unknown_requests': 2, 'deepseek_requests': 10,
                       'api_upper_bound_usd': 25., 'unknown_charge_bound_usd': 5., 'max_usd': 250., 'max_requests': 10000},
            'supplemental_redo_count': 1, 'new_model_calls': 0, 'new_candidate_executions': 0, 'limitations': []}


class PiFullAnalysisTests(unittest.TestCase):
    def test_no_duplicate_or_redo_as_129th_sample(self):
        data = fixture(); data['pi_rows'].append(copy.deepcopy(data['pi_rows'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicates'): validate_input(data)
        data = fixture(); data['pi_rows'][-1] = copy.deepcopy(data['pi_rows'][0])
        with self.assertRaisesRegex(ValueError, 'duplicates'): validate_input(data)

    def test_scientific_promotion_needs_exact_head_and_raw_binding(self):
        data = fixture(); r = data['pi_rows'][0]; r['official_status'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'bound supplement'): validate_input(data)
        r['supplement'] = {'evidence_sha256': 'c'*64, 'head_commit': r['head_commit'], 'raw_result_sha256': r['result_sha256']}
        self.assertEqual(summarize(data)['pi_reviewed_status_counts']['PASS'], 1)
        r['supplement']['head_commit'] = 'd'*40
        with self.assertRaisesRegex(ValueError, 'bound supplement'): validate_input(data)

    def test_infrastructure_not_waived_by_excluding_conditions(self):
        data = fixture(); r = data['pi_rows'][0]; r['original_outcome'] = 'INFRA_FAIL'; r['official_status'] = 'PASS'
        r['supplement'] = {'evidence_sha256': 'c'*64, 'head_commit': r['head_commit'], 'raw_result_sha256': r['result_sha256']}
        with self.assertRaisesRegex(ValueError, 'Infrastructure'): validate_input(data)
        r['official_status'] = 'INFRA_FAIL'
        self.assertEqual(summarize(data)['profiles'][0]['INFRA'], 1)
        self.assertEqual(summarize(data)['profiles'][0]['total'], 16)

    def test_missing_timing_not_zero_and_unknown_charge_not_refunded(self):
        s = summarize(fixture()); self.assertEqual(s['profiles'][0]['coding_time_coverage'], 15)
        self.assertEqual(s['profiles'][0]['median_original_coding_and_public_seconds'], 10)
        self.assertEqual(s['ledger']['settled_usage_charge_bound_usd'], 20.)
        self.assertEqual(s['ledger']['remaining_upper_bound_usd'], 225.)
        self.assertEqual(s['profiles'][0]['total_end_to_end_seconds'], 'unavailable')

    def test_cannot_invent_invoice_or_drop_unknown_requests(self):
        data = fixture(); data['ledger']['actual_cash_usd'] = 25.
        with self.assertRaisesRegex(ValueError, 'invoice'): validate_input(data)
        data = fixture(); data['ledger']['unknown_requests'] = 0
        with self.assertRaisesRegex(ValueError, 'Unknown reservations'): validate_input(data)


if __name__ == '__main__': unittest.main()
