"""Request-sized accounting across a prospective cap change; no provider calls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from p1_budget import BudgetDenied,CONTEXT_TOKENS,INPUT_NANO,OUTPUT_NANO,REQUEST_RESERVE
from p6_main_budget import MainLedger,authorization


class OutputPolicyTests(unittest.TestCase):
    def setUp(self):
        scratch=ROOT/'.local-workbench/test-tmp';scratch.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch);self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'ledger.json'
        self.old=json.loads((ROOT/'configs/budget-p6-main-v3-time-approved.json').read_text())
        self.new=json.loads((ROOT/'configs/budget-p6-main-v4-default256k-approved.json').read_text())

    def test_amendment_preserves_unknown_and_settled_requests_but_new_reserves_are_larger(self):
        old=MainLedger(self.path,self.old)
        pending=old.reserve_request('TEST_ONLY/old-pending');settled=old.reserve_request('TEST_ONLY/old-complete')
        old.settle(settled,dict(input_tokens=9,cache_read_input_tokens=5,cache_creation_input_tokens=0,output_tokens=7),{'model_id':'deepseek-flash'})
        old.reserve_codex_turn('TEST_ONLY/old-codex','gpt-6.1-sol')
        before=self.path.read_bytes();new=MainLedger(self.path,self.new)
        with self.assertRaises(BudgetDenied):new.reserve_request('TEST_ONLY/no-silent-rebind')
        archive=self.path.parent/'old.json';new.amend_authorization(self.old,archive)
        self.assertEqual(archive.read_bytes(),before)
        for key in ('requests','codex_turns','cash_bound_nano'):
            self.assertEqual(json.loads(before)[key],json.loads(self.path.read_text())[key])
        self.assertEqual(new.max_output,256000)
        self.assertEqual(new.request_reserve,CONTEXT_TOKENS*INPUT_NANO+256000*OUTPUT_NANO)
        index=new.reserve_request('TEST_ONLY/new-role')
        usage=dict(input_tokens=8,cache_read_input_tokens=2,cache_creation_input_tokens=0,output_tokens=5000)
        new.settle(index,usage,{'model_id':'deepseek-flash'})
        self.assertEqual(json.loads(self.path.read_text())['requests'][index-1]['usage']['output_tokens'],5000)
        prior=self.path.read_bytes()
        with self.assertRaises(BudgetDenied):new.settle(pending,usage,{'model_id':'deepseek-flash'})
        self.assertEqual(self.path.read_bytes(),prior)
        self.assertEqual(json.loads(prior)['requests'][pending-1]['charge_bound_nano'],REQUEST_RESERVE)
        with self.assertRaises(BudgetDenied):old.reserve_request('TEST_ONLY/stale-auth')

    def test_invalid_output_policy_and_other_limit_changes_are_rejected(self):
        for cap in (True,256000.0,4096,16384,256001):
            bad=copy.deepcopy(self.new);bad['per_request_output_tokens']=cap
            with self.assertRaises(BudgetDenied):authorization(bad)
        MainLedger(self.path,self.old).reserve_request('TEST_ONLY/preserved')
        prior=self.path.read_bytes();bad=copy.deepcopy(self.new)
        bad['scientific_evaluation_timeout_seconds']['SCI-PC-ALM']+=1
        with self.assertRaises(BudgetDenied):MainLedger(self.path,bad).amend_authorization(self.old,self.path.parent/'bad.json')
        self.assertEqual(self.path.read_bytes(),prior)

    def test_new_bound_is_reserved_before_calls_and_bad_settlements_do_not_refund(self):
        ledger=MainLedger(self.path,self.new);index=ledger.reserve_request('TEST_ONLY/new')
        prior=self.path.read_bytes()
        for output in (256001,True,-1):
            with self.assertRaises(BudgetDenied):
                ledger.settle(index,dict(input_tokens=0,cache_read_input_tokens=0,cache_creation_input_tokens=0,output_tokens=output),{'model_id':'deepseek-flash'})
            self.assertEqual(self.path.read_bytes(),prior)
        # Move a valid settled accounting total just close enough to USD100 that
        # a 4096 reserve would fit, but the new 256000 reserve must be refused.
        value=json.loads(prior);rows=[];remaining=100_000_000_000-REQUEST_RESERVE
        i=0
        while remaining:
            amount=min(remaining,(CONTEXT_TOKENS*INPUT_NANO))
            amount-=amount%INPUT_NANO
            if not amount:break
            i+=1;rows.append(dict(index=i,experiment='TEST_ONLY/old-'+str(i//100),observed_at='fixture',
                status='SETTLED_USAGE_UPPER_BOUND',charge_bound_nano=amount,model_id='deepseek-flash',
                usage=dict(input_tokens=amount//INPUT_NANO,cache_read_input_tokens=0,cache_creation_input_tokens=0,output_tokens=0)))
            remaining-=amount
        value['requests']=rows;value['cash_bound_nano']=sum(r['charge_bound_nano'] for r in rows)
        self.path.write_text(json.dumps(value));prior=self.path.read_bytes()
        with self.assertRaisesRegex(BudgetDenied,'Main request/cash cap exhausted'):ledger.reserve_request('TEST_ONLY/denied')
        self.assertEqual(self.path.read_bytes(),prior)


if __name__=='__main__':unittest.main()
