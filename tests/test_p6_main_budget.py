"""Main authorization/ledger safety; synthetic reservations, zero model requests."""
import copy
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from p6_main_budget import MainLedger, PHASE, BudgetDenied, REQUEST_RESERVE


def reserve_process(path, config):
    try:
        MainLedger(path, config).reserve_request('TEST_ONLY/shared')
    except BudgetDenied:
        pass


class MainBudgetTests(unittest.TestCase):
    def setUp(self):
        root = ROOT/'.local-workbench/test-tmp'; root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'main.json'
        self.config = json.loads((ROOT/'configs/budget-p6-main-approved.json').read_text())

    def ledger(self): return MainLedger(self.path, self.config)

    def test_unlimited_aggregate_is_explicit_and_old_phase_cannot_be_opened(self):
        for index in range(21): self.ledger().reserve_request('TEST_ONLY/role-'+str(index))
        value = json.loads(self.path.read_text())
        self.assertEqual(value['aggregate_caps'], {'requests':None,'codex_turns':None,'cash_nano':None})
        self.assertEqual(value['cash_bound_nano'], 21*REQUEST_RESERVE)
        value['phase'] = 'P6'; self.path.write_text(json.dumps(value))
        before = self.path.read_bytes()
        with self.assertRaises(BudgetDenied): self.ledger().reserve_request('another')
        self.assertEqual(before, self.path.read_bytes())

    def test_authorization_and_watchdog_edits_fail_before_ledger_creation(self):
        for key, changed in [('api_cash_usd',12),('per_role_inference_requests',200),
                             ('model_execution_enabled',False),('top_up_allowed',True),
                             ('per_request_timeout_seconds',120.0),('authorization_reference','')]:
            value = copy.deepcopy(self.config); value[key] = changed
            with self.assertRaises(BudgetDenied): MainLedger(self.path, value)
        self.assertFalse(self.path.exists())

    def test_unknown_usage_and_failed_subscription_remain_reserved_after_restart(self):
        for _ in range(20): self.ledger().reserve_request('TEST_ONLY/role')
        with self.assertRaises(BudgetDenied): self.ledger().reserve_request('TEST_ONLY/role')
        self.ledger().reserve_codex_turn('TEST_ONLY/judge','gpt-6.1-sol')
        with self.assertRaises(BudgetDenied): self.ledger().reserve_codex_turn('TEST_ONLY/judge','gpt-6.1-sol')
        with self.assertRaises(BudgetDenied): self.ledger().reserve_codex_turn('TEST_ONLY/other','different-model')
        self.assertEqual(json.loads(self.path.read_text())['cash_bound_nano'],20*REQUEST_RESERVE)

    def test_complete_settlement_and_corruption_cannot_erase_spend(self):
        index = self.ledger().reserve_request('TEST_ONLY/role')
        usage = {'input_tokens':10,'cache_read_input_tokens':2,'cache_creation_input_tokens':0,'output_tokens':3}
        for bad in ({'status':'erased'},{'experiment':'different'}):
            with self.assertRaises(BudgetDenied): self.ledger().settle(index,usage,bad)
        with self.assertRaises(BudgetDenied): self.ledger().settle(0,usage,{})
        with self.assertRaises(BudgetDenied): self.ledger().settle(index,{}, {})
        self.ledger().settle(index,usage,{'bill_cash_usd':'unavailable','model_id':'deepseek-flash'})
        with self.assertRaises(BudgetDenied): self.ledger().settle(index,usage,{})
        value = json.loads(self.path.read_text()); value['cash_bound_nano'] = 0
        self.path.write_text(json.dumps(value)); before = self.path.read_bytes()
        with self.assertRaises(BudgetDenied): self.ledger().reserve_request('new')
        self.assertEqual(before,self.path.read_bytes())

    def test_balanced_tampering_cannot_claim_zero_spend_for_settled_tokens(self):
        index=self.ledger().reserve_request('TEST_ONLY/role')
        self.ledger().settle(index,{'input_tokens':10,'cache_read_input_tokens':0,'cache_creation_input_tokens':0,'output_tokens':3},
                             {'model_id':'deepseek-flash','bill_cash_usd':'unavailable'})
        value=json.loads(self.path.read_text());value['cash_bound_nano']=0;value['requests'][0]['charge_bound_nano']=0
        self.path.write_text(json.dumps(value))
        with self.assertRaises(BudgetDenied):self.ledger().reserve_request('other')

    def test_fingerprint_cannot_be_rebound_by_restarting_controller(self):
        self.ledger().reserve_request('TEST_ONLY/role')
        value = copy.deepcopy(self.config); value['authorization_reference'] += ' changed'
        with self.assertRaises(BudgetDenied): MainLedger(self.path,value).reserve_request('other')

    @unittest.skipUnless(os.name == 'posix', 'Production uses native Linux flock')
    def test_parallel_controllers_share_exact_role_count(self):
        children = [multiprocessing.Process(target=reserve_process,args=(self.path,self.config)) for _ in range(24)]
        for child in children: child.start()
        for child in children: child.join(30); self.assertEqual(child.exitcode,0)
        value = json.loads(self.path.read_text())
        self.assertEqual(len(value['requests']),20)
        self.assertEqual(value['cash_bound_nano'],20*REQUEST_RESERVE)


if __name__ == '__main__': unittest.main()
