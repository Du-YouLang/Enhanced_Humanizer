"""No network: failure, retry and interrupted-stream cases for the actual P1 ledger."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p1_budget import BudgetDenied, ChatUsage, Ledger, MessagesUsage, REQUEST_RESERVE


class P1BudgetTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).resolve().parents[1]/'.local-workbench/test-tmp'
        scratch.mkdir(parents=True,exist_ok=True)
        self.directory=tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'ledger.json'

    def test_unknown_requests_retain_peak_cash_after_restart(self):
        ledger=Ledger(self.path)
        for _ in range(3):ledger.reserve_request('interrupted')
        with self.assertRaises(BudgetDenied):Ledger(self.path).reserve_request('retry')
        self.assertEqual(json.loads(self.path.read_text())['cash_bound_nano'],3*REQUEST_RESERVE)

    def test_settlement_frees_only_proven_unused_reservation_and_count_stays(self):
        ledger=Ledger(self.path,requests=2)
        usage={'input_tokens':12,'cache_read_input_tokens':4,'cache_creation_input_tokens':0,'output_tokens':8}
        one=ledger.reserve_request('one');ledger.settle(one,usage,{})
        Ledger(self.path,requests=2).reserve_request('two')
        with self.assertRaises(BudgetDenied):ledger.reserve_request('three')
        with self.assertRaises(BudgetDenied):ledger.settle(one,usage,{})

    def test_incomplete_or_corrupt_usage_cannot_release_cash(self):
        ledger=Ledger(self.path);index=ledger.reserve_request('missing')
        for usage in [{},{'input_tokens':-1}, {'input_tokens':1,'cache_read_input_tokens':0,'cache_creation_input_tokens':0,'output_tokens':5000}]:
            with self.assertRaises(BudgetDenied):ledger.settle(index,usage,{})
        self.assertEqual(json.loads(self.path.read_text())['cash_bound_nano'],REQUEST_RESERVE)

    def test_subscription_turns_are_independent_and_not_refunded(self):
        ledger=Ledger(self.path)
        for _ in range(6):ledger.reserve_codex_turn('test','gpt-6.1-sol')
        with self.assertRaises(BudgetDenied):Ledger(self.path).reserve_codex_turn('retry','gpt-6.1-sol')
        self.assertEqual(json.loads(self.path.read_text())['cash_bound_nano'],0)

    def test_stream_requires_stop_matching_model_and_all_usage_fields(self):
        usage=MessagesUsage();usage.event({'type':'message_start','message':{'model':'deepseek-flash','usage':{'input_tokens':1,'cache_read_input_tokens':0,'cache_creation_input_tokens':0}}})
        with self.assertRaises(BudgetDenied):usage.verified()
        usage.event({'type':'message_delta','usage':{'output_tokens':2}})
        usage.event({'type':'message_stop'})
        self.assertEqual(usage.verified()['output_tokens'],2)
        usage.model='deepseek-v4-pro'
        with self.assertRaises(BudgetDenied):usage.verified()

    def test_corrupt_ledger_fails_closed(self):
        ledger=Ledger(self.path);ledger.reserve_request('one')
        value=json.loads(self.path.read_text());value['cash_bound_nano']=0;self.path.write_text(json.dumps(value))
        with self.assertRaises(BudgetDenied):ledger.reserve_request('two')

    @unittest.skipUnless(os.name=='posix','Production ledger uses Linux flock')
    def test_separate_controllers_cannot_race_past_cash_cap(self):
        def reserve(index):
            try:Ledger(self.path).reserve_request(str(index));return True
            except BudgetDenied:return False
        with ThreadPoolExecutor(max_workers=16) as pool:
            passed=list(pool.map(reserve,range(16)))
        self.assertEqual(sum(passed),3)
        value=json.loads(self.path.read_text())
        self.assertEqual(len(value['requests']),3)
        self.assertEqual(value['cash_bound_nano'],3*REQUEST_RESERVE)

    def test_chat_usage_requires_done_model_and_consistent_cache_totals(self):
        usage=ChatUsage()
        usage.event({'model':'deepseek-flash','usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12,
                    'prompt_cache_hit_tokens':4,'prompt_cache_miss_tokens':6}})
        with self.assertRaises(BudgetDenied):usage.verified()
        usage.event('[DONE]')
        self.assertEqual(usage.verified(),{'input_tokens':6,'cache_read_input_tokens':4,'cache_creation_input_tokens':0,'output_tokens':2})
        usage.values['prompt_tokens']=11
        with self.assertRaises(BudgetDenied):usage.verified()
        with self.assertRaises(BudgetDenied):usage.event({'model':'deepseek-v4-pro'})
