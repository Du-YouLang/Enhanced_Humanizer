import importlib.util
from pathlib import Path
import unittest
import tempfile
import os
import json
import sys

p=Path(__file__).resolve().parents[1]/'benchmarks/pi-comparison/runners/pi_recovery_policy.py'
s=importlib.util.spec_from_file_location('pi_recovery_policy',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class PiOverloadRecoveryTests(unittest.TestCase):
    def test_recovery_reserves_a_new_turn_without_refunding_the_old_one(self):
        root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
        from p6_main_budget import MainLedger
        from p1_budget import BudgetDenied
        cache=root/'.local-workbench/tests/pi-recovery';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            ledger=MainLedger(Path(tmp)/'ledger.json',json.loads((root/'configs/budget-p6-main-v6-cash200-approved.json').read_text()))
            scope='PI_FORMAL/original/role';ledger.reserve_codex_turn(scope,'gpt-6.1-sol')
            before=json.loads(ledger.path.read_bytes())['codex_turns']
            with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn(scope,'gpt-6.1-sol')
            retry=m.subscription_retry_scope(scope,'formal-overload-recover-20261014T090000Z')
            ledger.reserve_codex_turn(retry,'gpt-6.1-sol')
            after=json.loads(ledger.path.read_bytes())['codex_turns']
            self.assertEqual(len(after),2);self.assertEqual(after[:1],before)
    def test_copy_retains_readonly_baseline_and_preserves_internal_links(self):
        cache=Path(__file__).resolve().parents[1]/'.local-workbench/tests/pi-recovery';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            root=Path(tmp);source=root/'source';dest=root/'code';source.mkdir();dest.mkdir()
            (source/'pack').write_text('checkpoint');(dest/'pack').write_text('baseline');(dest/'pack').chmod(0o444)
            if os.name!='nt':(source/'doc-link').symlink_to('missing-document')
            retained=m.copy_checkpoint(source,dest)
            self.assertEqual((dest/'pack').read_text(),'checkpoint');self.assertEqual((retained/'pack').read_text(),'baseline')
            self.assertEqual((source/'pack').read_text(),'checkpoint')
            if os.name!='nt':self.assertEqual(os.readlink(dest/'doc-link'),'missing-document')
            (retained/'pack').chmod(0o644)
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
