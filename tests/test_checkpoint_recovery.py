import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_checkpoint_recovery import Stages, remaining_limits


class RecoveryTests(unittest.TestCase):
    def limits(self, **change):
        args = dict(worker={'status':'INFRA_RETRY_PENDING','wall_seconds':370.9964,
                            'elapsed_seconds':370.654},
                    requests=[{'experiment':'old/pool-A'}]*63,
                    scope='old/pool-A', role_seconds=900, role_requests=1000,
                    original_activity_upper=1029, activity_cap=7200)
        args.update(change)
        return remaining_limits(**args)

    def test_original_requests_and_time_are_not_reset(self):
        v = self.limits()
        self.assertEqual((v['role_seconds_remaining'],v['role_requests_remaining'],
                          v['activity_seconds_remaining']), (529,937,6171))
        self.assertEqual(v['scope'],'old/pool-A')

    def test_model_failure_and_exhausted_allowance_cannot_be_retried(self):
        for change in ({'worker':{'status':'TIMEOUT'}},
                       {'requests':[{'experiment':'old/pool-A'}]*1000},
                       {'original_activity_upper':7200},
                       {'original_activity_upper':100}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.limits(**change)

    def test_restart_skips_completed_and_refuses_uncertain_model_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            s = Stages(folder)
            s.run('finished',lambda:{'head':'frozen'})
            self.assertEqual(s.run('finished',lambda:self.fail('replayed')),{'head':'frozen'})
            def interrupted():
                raise InterruptedError('simulated power loss')
            with self.assertRaises(InterruptedError):s.run('interrupted',interrupted)
            with self.assertRaises(FileExistsError):s.run('interrupted',lambda:self.fail('replayed'))

    def test_native_payload_retains_the_frozen_manifest_hash(self):
        from resume_p6_pool import load_frozen
        p=Path(__file__).resolve().parents[1]/'configs/benchmark-p6-v12-cash200.json'
        self.assertEqual(load_frozen(p),json.loads(p.read_bytes()))


if __name__=='__main__':unittest.main()
