"""Cash-only extension controls: no provider calls, old rows and caps stay bound."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from p6_main_budget import MainLedger,BudgetDenied,authorization,CASH_REVISION


class CashExtensionTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.local-workbench/test-tmp';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.json'
        self.old=json.loads((ROOT/'configs/budget-p6-main-v5-network-approved.json').read_text())
        self.new=json.loads((ROOT/'configs/budget-p6-main-v6-cash200-approved.json').read_text())

    def test_explicit_amendment_preserves_settled_unknown_and_subscription(self):
        before_ledger=MainLedger(self.path,self.old)
        first=before_ledger.reserve_request('CONTROL/known')
        before_ledger.settle(first,dict(input_tokens=17,cache_read_input_tokens=500,cache_creation_input_tokens=0,output_tokens=3),dict(model_id='deepseek-flash'))
        before_ledger.reserve_request('CONTROL/unknown')
        before_ledger.reserve_codex_turn('CONTROL/judge','gpt-6.1-sol')
        before=self.path.read_bytes();new_ledger=MainLedger(self.path,self.new)
        with self.assertRaises(BudgetDenied):new_ledger.reserve_request('CONTROL/premature')
        archive=self.path.parent/'before.json'
        receipt=new_ledger.amend_authorization(self.old,archive)
        self.assertEqual(before,archive.read_bytes())
        after=json.loads(self.path.read_bytes());old=json.loads(before)
        for key in ('requests','codex_turns','cash_bound_nano'):self.assertEqual(old[key],after[key])
        self.assertEqual(after['aggregate_caps'],dict(requests=10000,codex_turns=None,cash_nano=200_000_000_000))
        self.assertEqual(after['authorization_history'][-1]['amendment_kind'],CASH_REVISION)
        self.assertEqual(receipt['requests_retained'],2)
        self.assertEqual(new_ledger.role_requests,1000)
        self.assertEqual(new_ledger.max_output,256000)
        with self.assertRaises(BudgetDenied):before_ledger.reserve_request('CONTROL/stale')
        new_ledger.reserve_request('CONTROL/future')
        with self.assertRaises(BudgetDenied):new_ledger.amend_authorization(self.old,self.path.parent/'repeat.json')

    def test_unapproved_cap_revision_and_coupled_controls_rejected(self):
        for field,value in [('cash_budget_revision','unknown'),('api_cash_usd',201),('api_cash_usd',200.0),('deepseek_inference_requests',10001),('per_request_timeout_seconds',601),('per_role_inference_requests',1001),('top_up_allowed',True),('authorization_reference','')]:
            bad=copy.deepcopy(self.new);bad[field]=value
            with self.assertRaises(BudgetDenied):authorization(bad)
        bad=copy.deepcopy(self.old);bad['api_cash_usd']=200
        with self.assertRaises(BudgetDenied):authorization(bad)
        MainLedger(self.path,self.old).reserve_request('CONTROL/old');before=self.path.read_bytes()
        for field,value in [('scope','changed'),('scientific_evaluation_timeout_seconds',{'SCI-PC-ALM':1}),('extra_permission',True)]:
            bad=copy.deepcopy(self.new);bad[field]=value
            with self.assertRaises(BudgetDenied):MainLedger(self.path,bad).amend_authorization(self.old,self.path.parent/'bad.json')
            self.assertEqual(before,self.path.read_bytes())

    def test_200_cash_cap_and_10000_request_cap_still_stop_before_append(self):
        ledger=MainLedger(self.path,self.new);ledger.reserve_request('CONTROL/template')
        template=json.loads(self.path.read_bytes())
        for request_limit in (False,True):
            value=copy.deepcopy(template);count=10000 if request_limit else ledger.cash_nano//ledger.request_reserve
            value['requests']=[]
            for index in range(count):
                row=copy.deepcopy(template['requests'][0]);row.update(index=index+1,experiment='CONTROL/role-'+str(index//1000))
                if request_limit:row.update(status='SETTLED_USAGE_UPPER_BOUND',charge_bound_nano=0,model_id='deepseek-flash',usage=dict(input_tokens=0,cache_read_input_tokens=0,cache_creation_input_tokens=0,output_tokens=0))
                value['requests'].append(row)
            value['cash_bound_nano']=sum(r['charge_bound_nano'] for r in value['requests'])
            self.path.write_text(json.dumps(value));before=self.path.read_bytes()
            with self.assertRaisesRegex(BudgetDenied,'Main request/cash cap exhausted'):ledger.reserve_request('CONTROL/over-limit')
            self.assertEqual(before,self.path.read_bytes())


if __name__=='__main__':unittest.main()
