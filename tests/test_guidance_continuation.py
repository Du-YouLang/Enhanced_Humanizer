import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p6_guidance_continuation import *


class ContinuationTests(unittest.TestCase):
    def test_exact_prefix_and_only_one_remaining_partial_role(self):
        order=role_order(PARTIAL_TASK)
        self.assertEqual(remaining_partial_roles(order[:4]),('code-tests-ds',))
        self.assertEqual(len(RETAINED_TASKS),9);self.assertEqual(len(NEW_TASKS),6)
        with self.assertRaises(ValueError):remaining_partial_roles(order[:3])
        with self.assertRaises(ValueError):remaining_partial_roles(order)
    def test_paid_launch_cannot_replay_any_closed_or_partial_completed_role(self):
        run_id='guidance-20261016T180000Z'
        for tid in TASKS:
            for role in role_order(tid):
                scope='GUIDANCE/'+run_id+'/'+tid+'/'+role
                self.assertEqual(permit_launch(scope,run_id,'new-suffix'),tid in NEW_TASKS)
                oldscope='GUIDANCE/'+ORIGINAL_RUN+'/'+tid+'/'+role
                self.assertEqual(permit_launch(oldscope,run_id,'original-partial'),tid==PARTIAL_TASK and role=='code-tests-ds')


if __name__=='__main__':unittest.main()
