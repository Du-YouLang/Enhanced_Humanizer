import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from guidance_final_analysis import (AFFECTED, METHODS, build, deepseek_usage,
                                     paired, subscription_usage)
from p6_guidance_protocol import TASKS


def token_entry(segment=None):
    row = {'session_id': 'session', 'usage': {'input_tokens': 100, 'cached_input_tokens': 40,
           'output_tokens': 10, 'reasoning_output_tokens': 3}}
    if segment:
        row['usage_segment'] = segment
    return row


def fixture():
    intake = {'workers': {}, 'requests': [], 'subscriptions': [], 'global_budget': {},
              'receipt': {'completed_tasks': 16, 'status': 'GUIDANCE_SHUTDOWN_CONTINUATION_COMPLETED',
                          'results': [], 'supplements': []}}
    science = {}
    for tid in TASKS:
        prefix = 'GUIDANCE/guidance-20261016T060944Z/' + tid + '/'
        for role in ('initial-ds', 'code-tests-mentor', 'code-tests-trace-mentor', 'code-tests-ds', 'code-tests-trace-ds'):
            scope = prefix + role
            entry = token_entry(); entry['session_id'] = scope
            intake['workers'][scope] = {'scope': scope, 'status': 'COMPLETED', 'wall_seconds': 10,
                                      'usage': [entry] if role.endswith('-mentor') else []}
            if role.endswith('-mentor'):
                intake['subscriptions'].append({'experiment': scope})
            else:
                intake['requests'].append({'experiment': scope, 'status': 'SETTLED_USAGE_UPPER_BOUND',
                    'usage': {'input_tokens': 60, 'cache_read_input_tokens': 40,
                              'cache_creation_input_tokens': 0, 'output_tokens': 10}, 'charge_bound_nano': 1000})
        task = {'task_id': tid, 'initial': {'test_report': {'elapsed_seconds': 1}}, 'branches': {}, 'rows': []}
        for method in METHODS:
            task['rows'].append({'method': method, 'outcome': 'PASS', 'candidate': {'head_commit': 'head'},
                                 'frozen': {}, 'acceptance': {'elapsed_seconds': 2}})
            science[tid, method] = {'formal': 'PASS', 'quality_without_timing': 'PASS', 'numeric': 'PASS', 'reason': 'test'}
        for branch in ('code-tests', 'code-tests-trace'):
            task['branches'][branch] = {'candidate': {'test_report': {'elapsed_seconds': 1}}}
        intake['receipt']['results'].append(task)
    return intake, science


class GuidanceFinalAnalysisTests(unittest.TestCase):
    def test_unknown_usage_is_not_zero_and_cash_reserve_is_retained(self):
        value = deepseek_usage([{'status': 'UNKNOWN_USAGE', 'charge_bound_nano': 500000000}])
        self.assertIsNone(value['observed']['input_including_cache'])
        self.assertEqual(value['unknown_requests'], 1)
        self.assertFalse(value['complete'])
        self.assertEqual(value['charge_bound_usd'], .5)

    def test_resumed_subscription_adds_nonoverlapping_segments_once(self):
        w = {'scope': 'mentor', 'usage': [token_entry('BEFORE_USER_SHUTDOWN'), token_entry('RESUMED_DELTA')]}
        value = subscription_usage([w])
        self.assertEqual((value['known_sessions'], value['observed_segments']), (1, 2))
        self.assertEqual(value['observed']['input_including_cache'], 200)
        self.assertEqual(value['observed']['total_excluding_reasoning_subset'], 220)
        self.assertEqual(value['observed']['reasoning'], 6)

    def test_overlapping_or_partial_subscription_segments_are_rejected(self):
        for entries in ([token_entry(), token_entry()], [token_entry('RESUMED_DELTA')],
                        [token_entry(), token_entry('BEFORE_USER_SHUTDOWN'), token_entry('RESUMED_DELTA')]):
            with self.assertRaises(ValueError):
                subscription_usage([{'scope': 'mentor', 'usage': entries}])

    def test_shared_initial_is_once_in_paid_activity_and_visible_in_projections(self):
        intake, science = fixture(); before = copy.deepcopy(intake)
        value = build(intake, science)
        self.assertEqual(value['unique_paid_activity']['ds']['requests'], 48)
        self.assertEqual([m['ds']['requests'] for m in value['methods']], [16, 32, 32])
        self.assertEqual(value['methods'][0]['openai']['observed']['input_including_cache'], 0)
        self.assertEqual(intake, before)

    def test_helper_quality_supplement_does_not_restore_process_equivalence(self):
        intake, science = fixture(); task = next(t for t in intake['receipt']['results'] if t['task_id'] in AFFECTED)
        task['rows'][0]['outcome'] = 'FAIL'
        intake['receipt']['supplements'].append({'task_id': task['task_id'], 'method': METHODS[0],
            'raw_original_outcome': 'FAIL', 'model_replays': 0, 'supplemental_quality_outcome': 'PASS'})
        value = build(intake, science)
        row = next(r for r in value['rows'] if r['task_id'] == task['task_id'] and r['method'] == METHODS[0])
        self.assertEqual(row['formal_status'], 'PASS')
        self.assertEqual(row['raw_status'], 'FAIL')
        self.assertTrue(row['helper_process_affected'])
        self.assertEqual(paired(value['rows'], METHODS[0], METHODS[1], exclude_affected=True)['comparable_tasks'], 12)

    def test_unresolved_science_is_not_counted_as_failed_in_decidable_pairs(self):
        rows = [{'task_id': 't', 'method': m, 'formal_status': 'INDETERMINATE', 'coding_public_seconds': 10} for m in METHODS[:2]]
        value = paired(rows, METHODS[0], METHODS[1], field='formal_status')
        self.assertEqual(value['comparable_tasks'], 0)
        self.assertEqual(value['left_only'], [])

    def test_incomplete_or_foreign_evidence_is_refused(self):
        intake, science = fixture(); intake['workers'].pop(next(iter(intake['workers'])))
        with self.assertRaises(ValueError):
            build(intake, science)
        intake, science = fixture(); science['SCI-EGL', METHODS[0]]['head'] = 'another-program'
        with self.assertRaises(ValueError):
            build(intake, science)


if __name__ == '__main__':
    unittest.main()
