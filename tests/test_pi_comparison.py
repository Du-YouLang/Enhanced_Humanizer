import importlib.util
import json
from pathlib import Path
import unittest

BASE=Path(__file__).resolve().parents[1]/'benchmarks/pi-comparison/runners'
def module(name):
    spec=importlib.util.spec_from_file_location('pi_'+name,BASE/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
events=module('events');plan=module('plan')


class PiComparisonTests(unittest.TestCase):
    def test_only_message_end_counts_usage_and_unicode_does_not_break_framing(self):
        msg={'role':'assistant','id':'x','content':'hello\u2028world','provider':'deepseek','model':'deepseek-flash',
             'usage':{'input':8,'output':6,'cacheRead':2,'cacheWrite':0},'stopReason':'stop'}
        rows=[{'type':'turn_start'},{'type':'message_end','message':msg},
              {'type':'turn_end','message':msg},{'type':'agent_end','messages':[msg]},
              {'type':'agent_settled','aborted':False}]
        raw=('\r\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\r\n').encode()
        got=events.summarize(raw)
        self.assertEqual(got['assistant_requests_observed'],1)
        self.assertEqual(got['usage']['output_tokens'],6)
        self.assertTrue(got['agent_settled']);self.assertEqual(got['hidden_grade'],'NOT_RUN')

    def test_missing_usage_retry_and_duplicate_are_not_free_success(self):
        rows=[{'type':'turn_start'},{'type':'message_end','message':{'role':'assistant','id':'same'}},
              {'type':'message_end','message':{'role':'assistant','id':'same'}},
              {'type':'auto_retry_start'},{'type':'agent_settled','aborted':True}]
        got=events.summarize(('\n'.join(json.dumps(r) for r in rows)).encode())
        self.assertIsNone(got['usage']['output_tokens']);self.assertIsNone(got['api_cost_usd_actual_or_reconciled'])
        self.assertEqual(got['provider_retries'],1);self.assertEqual(got['duplicate_assistant_events'],1)
        self.assertFalse(got['agent_settled'])

    def test_manifest_retains_all_tasks_and_live_calls_are_disabled(self):
        got=plan.plan(plan.ROOT/'configs/benchmark-p6-v11.json')
        self.assertEqual(len(got['task_contracts']),16);self.assertEqual(len(got['smoke_rows']),16)
        self.assertFalse(got['model_execution_enabled']);self.assertFalse(got['bulk_256_attempts_enabled'])
        self.assertEqual(got['upstream_main_manifest_sha256'],'f327d2c9b3eb0485571c06ee7f905dbd9dbc1220a663ef5f121eb0e15ca6875d')
        self.assertTrue(all(r['material_sha256'] for r in got['task_contracts']))
        self.assertEqual({r['task_role_seconds'] for r in got['task_contracts']},{900,1200})
        self.assertTrue(all(r['max_output_tokens']==256000 for r in got['task_contracts']))


if __name__=='__main__':unittest.main()
