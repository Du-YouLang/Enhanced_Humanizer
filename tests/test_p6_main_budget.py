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
from p6_main_budget import authorization


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

    def test_explicit_finite_amendment_preserves_bytes_requests_and_counts(self):
        self.ledger().reserve_request('TEST_ONLY/old');before=self.path.read_bytes()
        finite=json.loads((ROOT/'configs/budget-p6-main-v2-approved.json').read_text())
        ledger=MainLedger(self.path,finite);archive=self.path.parent/'before.json'
        with self.assertRaises(BudgetDenied):ledger.reserve_request('TEST_ONLY/new')
        receipt=ledger.amend_authorization(self.config,archive)
        self.assertEqual(archive.read_bytes(),before)
        after=json.loads(self.path.read_text());old=json.loads(before)
        for key in ('requests','codex_turns','cash_bound_nano'):self.assertEqual(after[key],old[key])
        self.assertEqual(receipt['requests_retained'],1)
        self.assertEqual(after['aggregate_caps'],{'requests':10000,'cash_nano':100_000_000_000,'codex_turns':None})
        ledger.reserve_request('TEST_ONLY/new')
        self.assertEqual(len(json.loads(self.path.read_text())['requests']),2)
        with self.assertRaises(BudgetDenied):ledger.amend_authorization(self.config,self.path.parent/'twice.json')

    def test_finite_total_request_and_cash_limits_deny_before_append(self):
        finite=json.loads((ROOT/'configs/budget-p6-main-v2-approved.json').read_text())
        ledger=MainLedger(self.path,finite);ledger.reserve_request('TEST_ONLY/setup')
        template=json.loads(self.path.read_text())
        for request_limit in (True,False):
            value=copy.deepcopy(template)
            count=10000 if request_limit else 100_000_000_000//REQUEST_RESERVE
            value['requests']=[]
            for index in range(count):
                row=copy.deepcopy(template['requests'][0]);row.update(index=index+1,experiment='TEST_ONLY/scope-'+str(index//100))
                if request_limit:
                    row.update(status='SETTLED_USAGE_UPPER_BOUND',charge_bound_nano=0,model_id='deepseek-flash',usage={k:0 for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')})
                value['requests'].append(row)
            value['cash_bound_nano']=sum(r['charge_bound_nano'] for r in value['requests'])
            self.path.write_text(json.dumps(value));before=self.path.read_bytes()
            with self.assertRaisesRegex(BudgetDenied,'Main request/cash cap exhausted'):ledger.reserve_request('TEST_ONLY/another')
            self.assertEqual(self.path.read_bytes(),before)
        for key,changed in [('api_cash_usd',101),('deepseek_inference_requests',10001),('per_role_inference_requests',101)]:
            bad=copy.deepcopy(finite);bad[key]=changed
            with self.assertRaises(BudgetDenied):authorization(bad)

    @unittest.skipUnless(os.name == 'posix', 'Production uses native Linux flock')
    def test_parallel_controllers_share_exact_role_count(self):
        children = [multiprocessing.Process(target=reserve_process,args=(self.path,self.config)) for _ in range(24)]
        for child in children: child.start()
        for child in children: child.join(30); self.assertEqual(child.exitcode,0)
        value = json.loads(self.path.read_text())
        self.assertEqual(len(value['requests']),20)
        self.assertEqual(value['cash_bound_nano'],20*REQUEST_RESERVE)


if __name__ == '__main__': unittest.main()
