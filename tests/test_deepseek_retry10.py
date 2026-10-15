import asyncio
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from p1_budget import BudgetDenied
from p6_main_budget import authorization
from p6_network_policy import RETRY10_POLICY,retry10_transport,NetworkCheckRequired,NetworkRetryPending
from p6_network_recovery import recover,TransientNetworkError


class DeepSeekRetry10Tests(unittest.TestCase):
    def run_case(self,failures):
        indices=[];events=[];delays=[]
        def reserve():indices.append(len(indices)+1);return indices[-1]
        async def call(index,seconds):
            self.assertEqual(seconds,600)
            if index<=failures:raise TransientNetworkError('synthetic connection reset')
            return 'complete response only'
        async def wait(seconds):delays.append(seconds)
        with patch('p6_network_recovery.asyncio.sleep',new=wait):
            try:result=asyncio.run(recover(call,reserve,time.monotonic()+900,RETRY10_POLICY,events))
            except NetworkCheckRequired:result='NETWORK_CHECK_REQUIRED'
        return result,indices,events,delays

    def test_nine_failures_then_success_and_tenth_failure_stop(self):
        result,indices,events,delays=self.run_case(9)
        self.assertEqual(result,'complete response only');self.assertEqual(indices,list(range(1,11)))
        self.assertEqual(delays,[2,4,8,16,30,45,60,60,60]);self.assertEqual(events[-1]['state'],'RECOVERED')
        self.assertTrue(events[4]['network_warning'])
        result,indices,events,delays=self.run_case(10)
        self.assertEqual(result,'NETWORK_CHECK_REQUIRED');self.assertEqual(len(indices),10)
        self.assertEqual(events[-1]['state'],'NETWORK_CHECK_REQUIRED')

    def test_transport_is_exact_and_cannot_silently_amend_budget(self):
        self.assertEqual(retry10_transport(RETRY10_POLICY),RETRY10_POLICY)
        for key,value in [('network_consecutive_failure_limit',11),('per_request_timeout_seconds',601),('network_retry_backoff_seconds',[0]*9)]:
            with self.assertRaises(ValueError):retry10_transport({**RETRY10_POLICY,key:value})
        old=json.loads((ROOT/'configs/budget-p6-main-v6-cash200-approved.json').read_bytes())
        authorization(old)
        with self.assertRaises(BudgetDenied):authorization({**old,**RETRY10_POLICY})

    def test_time_and_budget_cannot_be_extended_by_retry(self):
        events=[];reserved=[]
        async def fail(index,seconds):raise TransientNetworkError('connection reset')
        def reserve():reserved.append(1);return len(reserved)
        with self.assertRaises(NetworkRetryPending):
            asyncio.run(recover(fail,reserve,time.monotonic()+.01,RETRY10_POLICY,events))
        self.assertEqual(len(reserved),1);self.assertEqual(events[-1]['reason'],'ROLE_DEADLINE')
        def denied():raise BudgetDenied('cash cap')
        with self.assertRaises(BudgetDenied):asyncio.run(recover(fail,denied,time.monotonic()+900,RETRY10_POLICY,[]))
        for error in (PermissionError,ValueError):
            async def nonretry(index,seconds):raise error('not transport')
            events=[]
            with self.assertRaises(error):asyncio.run(recover(nonretry,lambda:1,time.monotonic()+900,RETRY10_POLICY,events))
            self.assertEqual(len(events),1);self.assertEqual(events[0]['state'],'NON_RETRYABLE')

    def test_successor_can_change_only_transport_and_executor_source(self):
        import copy,importlib.util
        spec=importlib.util.spec_from_file_location('retry10_continuation',ROOT/'benchmarks/pi-comparison/runners/pi_full_continue_policy.py')
        policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
        original={'budget':{'api_cash_usd':200},'plan':{'cells':[1,2],'request_seconds':600,'public_role_seconds':900,
            'scientific_role_seconds':1200,'models':{'deepseek':'deepseek-flash'},'source_sha256':{'old':'pin'},'plan_sha256':'old'}}
        new=copy.deepcopy(original);new['plan'].update(source_sha256={'new':'pin'},plan_sha256='new',deepseek_transport_policy=RETRY10_POLICY)
        self.assertEqual(policy.transport_successor(original,new),new)
        for key,value in [('cells',[1]),('request_seconds',601),('public_role_seconds',901),('models',{'deepseek':'other'})]:
            changed=copy.deepcopy(new);changed['plan'][key]=value
            with self.assertRaises(ValueError):policy.transport_successor(original,changed)
        changed=copy.deepcopy(new);changed['budget']['api_cash_usd']=201
        with self.assertRaises(ValueError):policy.transport_successor(original,changed)


if __name__=='__main__':unittest.main()
