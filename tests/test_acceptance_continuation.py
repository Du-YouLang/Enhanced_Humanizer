import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from continue_p6_acceptance_linux import recover_truth, program_identity, incomplete_timing, validate_truth, shutdown_interruption


class AcceptanceContinuationTests(unittest.TestCase):
    def candidate(self, cid, source=None, verdict='PASS', worker='COMPLETED'):
        return {'id': cid, 'source': source or cid, 'patch': '', 'verdict': verdict, 'worker_status': worker}

    def truth(self, c, verdict):
        return {'program_identity': program_identity(c), 'worker_status': c['worker_status'],
                'public_verdict': c['verdict'], 'acceptance': {'verdict': verdict, 'elapsed_seconds': 7}}

    def test_all_completed_verdicts_are_reused(self):
        candidates = {c: self.candidate(c) for c in 'ABC'}
        existing = {c: self.truth(candidates[c], v) for c, v in zip('ABC', ['PASS', 'FAIL', 'INDETERMINATE'])}
        actual, count = recover_truth(candidates, existing, lambda _: self.fail('Completed result regraded'),
                                      lambda *_: self.fail('Completed result rewritten'))
        self.assertEqual(actual, existing)
        self.assertEqual(count, 3)

    def test_only_missing_program_is_graded(self):
        candidates = {c: self.candidate(c) for c in 'DE'}
        existing = {'D': self.truth(candidates['D'], 'FAIL')}
        graded, saved = [], []
        result, count = recover_truth(candidates, existing,
            lambda c: graded.append(c['id']) or {'verdict': 'PASS', 'elapsed_seconds': 8},
            lambda cid, v: saved.append(cid))
        self.assertEqual(graded, ['E']); self.assertEqual(saved, ['E'])
        self.assertEqual(result['D'], existing['D']); self.assertEqual(count, 2)

    def test_duplicate_program_uses_existing_failure_without_retry(self):
        d, e = self.candidate('D', 'same'), self.candidate('E', 'same')
        result, count = recover_truth({'D': d, 'E': e}, {'D': self.truth(d, 'FAIL')},
                                      lambda _: self.fail('Duplicate regraded'), lambda *_: None)
        self.assertEqual(result['E']['acceptance']['verdict'], 'FAIL'); self.assertEqual(count, 1)

    def test_public_failure_never_enters_private_grader(self):
        c = self.candidate('D', verdict='FAIL')
        actual, count = recover_truth({'D': c}, {}, lambda _: self.fail('Public failure graded'), lambda *_: None)
        self.assertEqual(actual['D']['acceptance']['private_execution'], 'NOT_RUN_PUBLIC_HARD_GATE_FAILED')
        self.assertEqual(count, 0)

    def test_changed_program_verdict_or_worker_is_rejected(self):
        original = self.candidate('D'); truth = self.truth(original, 'FAIL')
        for key, value in [('source', 'tampered'), ('verdict', 'FAIL'), ('worker_status', 'TIMEOUT')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                c = copy.deepcopy(original); c[key] = value
                validate_truth(c, truth)

    def test_nonterminal_acceptance_is_not_a_checkpoint(self):
        c = self.candidate('D')
        with self.assertRaises(ValueError): validate_truth(c, self.truth(c, 'RUNNING'))

    def test_conflicting_identical_program_acceptance_is_rejected(self):
        d, e = self.candidate('D', 'same'), self.candidate('E', 'same')
        with self.assertRaises(ValueError):
            recover_truth({'D': d, 'E': e}, {'D': self.truth(d, 'PASS'), 'E': self.truth(e, 'FAIL')},
                          lambda _: self.fail('Conflict regraded'), lambda *_: None)

    def test_lost_parallel_wall_intervals_are_unavailable(self):
        row = {'metrics': {'end_to_end_seconds': 0, 'independent_acceptance_seconds': 51}, 'reason': 'Frozen'}
        incomplete_timing(row)
        self.assertEqual(row['metrics']['end_to_end_seconds'], 'unavailable')
        self.assertEqual(row['metrics']['model_and_public_check_seconds'], 'unavailable')
        self.assertEqual(row['metrics']['independent_acceptance_seconds'], 51)

    def test_only_exact_human_shutdown_signal_can_exclude_failure(self):
        pause = {'completed_private_acceptance_files': ['private-acceptance-A.json'], 'at_unix': 100}
        value = {'acceptance': {'verdict': 'FAIL', 'error_type': 'InterruptedError',
                 'reason': 'Owned main controller interrupted by signal 15', 'elapsed_seconds': 0}}
        self.assertTrue(shutdown_interruption('private-acceptance-D.json', value, 100.2, pause))
        self.assertFalse(shutdown_interruption('private-acceptance-A.json', value, 100.2, pause))
        self.assertFalse(shutdown_interruption('private-acceptance-D.json', value, 99, pause))
        self.assertFalse(shutdown_interruption('private-acceptance-D.json', value, 120, pause))
        value['acceptance']['error_type'] = 'ValueError'
        self.assertFalse(shutdown_interruption('private-acceptance-D.json', value, 100.2, pause))


if __name__ == '__main__': unittest.main()
