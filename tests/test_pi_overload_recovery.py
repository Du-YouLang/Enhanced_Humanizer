import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/'benchmarks/pi-comparison/runners/pi_recovery_policy.py'
s=importlib.util.spec_from_file_location('pi_recovery_policy',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class PiOverloadRecoveryTests(unittest.TestCase):
    def test_original_allowances_are_debited_without_rounding_up(self):
        w={'status':'INFRA_FAIL','wall_seconds':252.364191531,'elapsed_seconds':252.364191531,'sdk_dispatches':21}
        b=m.overload_bounds(w,900)
        self.assertEqual(b['role_seconds_remaining'],647);self.assertEqual(b['role_requests_remaining'],979)
        self.assertEqual(m.overload_bounds(w,900,[{'wall_seconds':2.5,'sdk_dispatches':2}])['role_seconds_remaining'],645)
        for update in ({'status':'COMPLETED'},{'wall_seconds':float('inf')},{'sdk_dispatches':1000}):
            with self.assertRaises(ValueError):m.overload_bounds({**w,**update},900)
    def test_only_explicit_overload_failure_is_eligible(self):
        self.assertTrue(m.is_overload_message({'stopReason':'error','errorMessage':'Our servers are currently overloaded.'}))
        for stop,text in [('stop','overloaded'),('error','insufficient_quota overloaded'),('error','invalid api key'),('error','generic test failure')]:
            self.assertFalse(m.is_overload_message({'stopReason':stop,'errorMessage':text}))

if __name__=='__main__':unittest.main()
