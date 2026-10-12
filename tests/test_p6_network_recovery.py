import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from p1_budget import BudgetDenied
from p6_main_budget import MainLedger,authorization
from p6_main_contract import classify_role_completion
from p6_network_policy import NetworkCheckRequired,NetworkRetryPending
from p6_network_recovery import recover,TransientNetworkError


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=ROOT/'.local-workbench/test-tmp';self.tmp.mkdir(parents=True,exist_ok=True)
    def config(self):
        return json.loads((ROOT/'configs/budget-p6-main-v5-network-approved.json').read_text())

    def test_locked_amendment_preserves_spend_and_authorization(self):
        old=json.loads((ROOT/'configs/budget-p6-main-v4-default256k-approved.json').read_text())
        with tempfile.TemporaryDirectory(dir=self.tmp) as tmp:
            p=Path(tmp)/'ledger.json';ledger=MainLedger(p,old)
            ledger.reserve_request('old/role')
            before=p.read_bytes();new=MainLedger(p,self.config())
            with self.assertRaises(BudgetDenied):new.reserve_request('new/role')
            new.amend_authorization(old,Path(tmp)/'archive.json')
            self.assertEqual((Path(tmp)/'archive.json').read_bytes(),before)
            after=json.loads(p.read_bytes());prior=json.loads(before)
            for key in ('requests','codex_turns','cash_bound_nano'):self.assertEqual(after[key],prior[key])
            new.reserve_request('new/role')
        for field,value in [('per_request_timeout_seconds',601),('per_role_inference_requests',1001),('network_consecutive_failure_limit',6),('api_cash_usd',101)]:
            c=self.config();c[field]=value
            with self.assertRaises(BudgetDenied):authorization(c)

    def test_reconnect_four_failures_then_success_counts_every_attempt(self):
        events=[];indices=[];seconds=[]
        def reserve():indices.append(len(indices)+1);return indices[-1]
        async def call(index,cap):
            seconds.append(cap)
            if index<5:raise TransientNetworkError('fixture disconnect')
            return 'one complete response'
        with patch('p6_network_recovery.asyncio.sleep',new=self.no_sleep):
            value=asyncio.run(recover(call,reserve,time.monotonic()+900,self.config(),events))
        self.assertEqual(value,'one complete response')
        self.assertEqual(indices,[1,2,3,4,5]);self.assertEqual(seconds,[600]*5)
        self.assertEqual([e['state'] for e in events],['SHOULD_RETRY']*4+['RECOVERED'])
        self.assertFalse(any(e['state']=='NETWORK_CHECK_REQUIRED' for e in events))

    @staticmethod
    async def no_sleep(_):pass

    def test_five_network_failures_are_infrastructure_not_model_failure(self):
        events=[];indices=[]
        async def call(index,cap):raise TransientNetworkError('fixture disconnect')
        def reserve():indices.append(1);return len(indices)
        with patch('p6_network_recovery.asyncio.sleep',new=self.no_sleep),self.assertRaises(NetworkCheckRequired):
            asyncio.run(recover(call,reserve,time.monotonic()+900,self.config(),events))
        self.assertEqual(len(indices),5)
        outcome=classify_role_completion({'status':'INFRA_FAIL','network_recovery_events':events})
        self.assertEqual(outcome['status'],'INFRA_RETRY_PENDING')
        self.assertEqual(outcome['operational_stop_reason'],'NETWORK_CHECK_REQUIRED')
        self.assertFalse(outcome['model_failure'])

    def test_permission_and_protocol_errors_do_not_bypass_fence_or_retry(self):
        for kind in (PermissionError,ValueError):
            events=[]
            async def call(index,cap):raise kind('not a provider connection failure')
            with self.assertRaises(kind):asyncio.run(recover(call,lambda:1,time.monotonic()+900,self.config(),events))
            self.assertEqual(len(events),1);self.assertEqual(events[0]['state'],'NON_RETRYABLE')

    def test_exhausted_time_and_cash_stay_pending_and_do_not_reset(self):
        events=[]
        async def call(index,cap):raise AssertionError('No provider request authorized')
        with self.assertRaises(NetworkRetryPending):asyncio.run(recover(call,lambda:1,time.monotonic()-1,self.config(),events))
        self.assertEqual(events[-1]['state'],'RETRY_PENDING')
        events=[]
        def denied():raise BudgetDenied('Aggregate cash exhausted')
        with self.assertRaises(BudgetDenied):asyncio.run(recover(call,denied,time.monotonic()+900,self.config(),events))
        self.assertEqual(events[-1]['reason'],'AUTHORIZED_BUDGET')

    def test_role_cap_is_1000_for_v12_not_a_default_on_old_ledgers(self):
        with tempfile.TemporaryDirectory(dir=self.tmp) as tmp:
            ledger=MainLedger(Path(tmp)/'new.json',self.config())
            for _ in range(1000):
                index=ledger.reserve_request('role')
                ledger.settle(index,{'input_tokens':1,'cache_read_input_tokens':0,'cache_creation_input_tokens':0,'output_tokens':1},{'model_id':'deepseek-flash'})
            with self.assertRaisesRegex(BudgetDenied,'Role request cap'):ledger.reserve_request('role')
            self.assertEqual(len(json.loads(ledger.path.read_text())['requests']),1000)


if __name__=='__main__':unittest.main()
