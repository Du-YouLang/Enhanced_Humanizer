"""New-model scope and cumulative ledger gates, all zero-provider controls."""
import copy
import hashlib
import json
from pathlib import Path,PurePosixPath
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'benchmarks/pi-comparison/runners')]
from p6_refresh_protocol import (REVISION,TASKS,MODELS,expected_model,allowed_scope,model_for_job,
    verify_session,handoff_prompt,verify_handoff_trace,method_order,require_clean_barrier)
from p6_main_budget import MainLedger,BudgetDenied,authorization


def scope(label='DS41-Flash1017',method='Direct',role='direct'):
    return 'REFRESH/refresh-20261126T010000Z/'+TASKS[0]+'/'+label+'/'+method+'/'+role


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.old=json.loads((ROOT/'configs/budget-p6-main-v10-guidance-approved.json').read_bytes())
        self.new=json.loads((ROOT/'configs/budget-p6-model-refresh-approved.json').read_bytes())
    def test_scope_model_backend_binding(self):
        for label,model in MODELS.items():
            s=scope(label)
            self.assertEqual(expected_model(s),model)
            provider='deepseek' if model=='deepseek-flash' else 'subscription'
            self.assertTrue(allowed_scope(s,provider,model))
            self.assertFalse(allowed_scope(s,provider,'gpt-6-sol'))
            backend='dsh' if provider=='deepseek' else 'codex'
            self.assertEqual(model_for_job({'scope':s,'requested_model':model,'backend':backend,'budget':self.new}),model)
        self.assertEqual(expected_model(scope(method='Enhanced',role='reviewer')),'gpt-6.1-sol')
        for bad in [scope()+'/extra',scope().replace(TASKS[0],'other'),scope().replace('/direct','/matched-7')]:
            self.assertFalse(allowed_scope(bad,'deepseek'))
    def test_infrastructure_stops_after_preserved_worker_without_reclassifying_role_budgets(self):
        from p6_refresh_protocol import require_operational_worker
        for status in ('INFRA_FAIL','INFRA_RETRY_PENDING','INFRA_HANDOFF_UNCONSUMED'):
            with self.assertRaisesRegex(RuntimeError,'INFRASTRUCTURE_BOUNDARY_STOP'):
                require_operational_worker({'status':status,'scope':scope()})
        for status in ('COMPLETED','TIMEOUT','OUTPUT_LIMIT','BUDGET_EXHAUSTED'):
            self.assertEqual(require_operational_worker({'status':status})['status'],status)

    def test_no_silent_model_or_harness_substitution(self):
        j={'scope':scope('GPT62-Sol'),'requested_model':'gpt-6.2-sol','backend':'codex','budget':self.new}
        for bad in [{**j,'requested_model':'gpt-6.1-sol'},{**j,'backend':'dsh'},{**j,'budget':self.old}]:
            with self.assertRaises(ValueError):model_for_job(bad)
    def test_amendment_preserves_exact_old_bytes_unknowns_and_legacy_reservations(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger';old=MainLedger(p,self.old,fixture=True)
            old.reserve_request('legacy-unknown')
            n=old.reserve_request('legacy-settled')
            old.settle(n,{'input_tokens':3,'cache_read_input_tokens':2,'cache_creation_input_tokens':0,'output_tokens':1},{'model_id':'deepseek-flash'})
            old.reserve_codex_turn('legacy-sol','gpt-6.1-sol')
            before=p.read_bytes();value=json.loads(before)
            new=MainLedger(p,self.new);archive=Path(d)/'archive'
            r=new.amend_authorization(self.old,archive)
            self.assertEqual(archive.read_bytes(),before)
            after=json.loads(p.read_bytes())
            for k in ['requests','codex_turns','cash_bound_nano']:self.assertEqual(after[k],value[k])
            self.assertEqual(after['aggregate_caps']['requests'],25000)
            self.assertEqual(after['aggregate_caps']['cash_nano'],500_000_000_000)
            self.assertEqual(r['requests_retained'],2)
            new.reserve_codex_turn(scope('GPT62-Sol'),'gpt-6.2-sol')
            with self.assertRaises(BudgetDenied):new.reserve_codex_turn(scope('GPT62-Sol'),'gpt-6.2-sol')
            with self.assertRaises(BudgetDenied):new.reserve_codex_turn(scope('GPT61-Sol'),'gpt-6.2-sol')
            with self.assertRaises(BudgetDenied):new.reserve_request('GUIDANCE/old/role')
            with self.assertRaises(BudgetDenied):new.reserve_request(scope('GPT62-Sol'))
            new.reserve_request(scope())
    def test_scope_amendment_cannot_relax_cash_or_role_watchdogs(self):
        for key,value in [('api_cash_usd',501),('per_role_inference_requests',2000),('per_request_timeout_seconds',1200),('deepseek_inference_requests',26000)]:
            c={**self.new,key:value}
            with self.assertRaises(BudgetDenied):authorization(c)
    def test_returned_model_identity_and_usage_are_required(self):
        turns=[{'status':'COMPLETED','session_id':'s','model_requested':'gpt-6.2-sol'}]
        row={'session_id':'s','model_id':'gpt-6.2-sol','usage':{'input_tokens':4,'output_tokens':2,'cached_input_tokens':3}}
        self.assertEqual(verify_session([row],turns,'gpt-6.2-sol'),row)
        for bad in [{**row,'model_id':'gpt-6.1-sol'},{**row,'usage':{'input_tokens':1,'output_tokens':2,'cached_input_tokens':3}}]:
            with self.assertRaises(ValueError):verify_session([bad],turns,'gpt-6.2-sol')
    def test_handoff_full_input_and_observable_receipt_not_just_advice_generated(self):
        raw=b'{"mentor_guidance":"fix boundary"}';path=PurePosixPath('/opt/task/input.json')
        prompt=handoff_prompt(path,raw,'task')
        self.assertIn(raw.decode(),prompt);self.assertIn(str(path),prompt)
        h=hashlib.sha256(raw).hexdigest()
        trace={'truncated':False,'records':[{'type':'tool/call','data':{'callId':'a','arguments':str(path)}},
            {'type':'tool/result','data':{'message':{'source':{'callId':'a'},'content':[{'type':'text','text':str(len(raw))+' '+h}]}}}]}
        self.assertEqual(verify_handoff_trace(trace,path,raw)['status'],'HANDOFF_READ_RECEIPT_OBSERVED')
        trace['records'].pop()
        self.assertEqual(verify_handoff_trace(trace,path,raw)['status'],'INFRA_HANDOFF_UNCONSUMED')
        with self.assertRaises(ValueError):handoff_prompt(path,b'x'*8_000_001,'task')
    def test_three_method_freeze_and_counterbalanced_order(self):
        self.assertEqual({method_order(i,0)[0] for i in range(3)},set(('Direct','Enhanced','SingleAgent-MatchedBudget')))
        rows={k:{'hidden_seen':False,'program_sha256':'a'*64} for k in method_order(0,0)}
        self.assertTrue(require_clean_barrier(rows))
        del rows['Direct']
        with self.assertRaises(ValueError):require_clean_barrier(rows)


class RefreshJournalTests(unittest.TestCase):
    def test_completed_unicode_group_is_reused_without_replaying_any_child(self):
        from pi_full_protocol import Journal
        from p6_refresh_protocol import complete_group
        with tempfile.TemporaryDirectory() as d:
            j=Journal(d);value={'scientific_report':'μV 中文','completed_roles':6}
            complete_group(Path(d)/'task--model.completed.json','task--model',value)
            self.assertEqual(j.run('task--model',lambda:self.fail('Completed group replayed')),value)


class RefreshAccountingTests(unittest.TestCase):
    def test_six_subscription_slots_one_session_and_unknown_ds_are_not_zero_or_double_counted(self):
        from p6_refresh_accounting import summarize
        prefix='REFRESH/run/task/model/method'
        ledger={'requests':[{'experiment':prefix+'/role','charge_bound_nano':20,'usage':{'input_tokens':3,'cache_read_input_tokens':2,'output_tokens':4}}, {'experiment':prefix+'/role','charge_bound_nano':30}],
                'codex_turns':[{'experiment':prefix+'/matched-'+str(i)} for i in range(1,7)]}
        usage={'session_id':'same','usage':{'input_tokens':10,'cached_input_tokens':4,'output_tokens':7}}
        w={'scope':prefix+'/matched-1','status':'COMPLETED','wall_seconds':3,'turns':[{'harness':'codex'}]*6,'usage':[usage],'matched_slot_receipts':[{'index':i} for i in range(1,7)]}
        value=summarize(ledger,{'w':w},prefix)
        self.assertEqual(value['openai']['input_tokens_recorded'],10)
        self.assertEqual(value['openai']['subscription_reservations'],6)
        self.assertEqual(value['completed_role_slots'],6)
        self.assertEqual(value['deepseek']['input_tokens_known'],5)
        self.assertTrue(value['deepseek']['token_totals_are_lower_bounds'])
        self.assertEqual(value['deepseek']['unknown_usage_requests'],1)
        self.assertEqual(value['openai']['actual_subscription_cash_usd'],'unavailable')
    def test_failed_subscription_without_turn_or_complete_usage_stays_unknown(self):
        from p6_refresh_accounting import summarize
        prefix='REFRESH/run/task/model/method';sc=prefix+'/role'
        ledger={'requests':[],'codex_turns':[{'experiment':sc}]}
        for usage in ([],[{'session_id':'s','usage':{'output_tokens':4}}]):
            value=summarize(ledger,{'w':{'scope':sc,'status':'INFRA_FAIL','usage':usage}},prefix)
            self.assertEqual(value['openai']['unknown_usage_scopes'],[sc])
            self.assertTrue(value['openai']['token_totals_are_lower_bounds'])
            self.assertEqual(value['openai']['recorded_session_usage_segments'],0)

    def test_matched_slot_ledger_denies_slot_seven_and_maps_each_request_to_exact_trusted_slot(self):
        from p6_refresh_sessions import write_slot,MatchedSlotLedger
        with tempfile.TemporaryDirectory() as d:
            job={'root':d,'scope':scope(method='SingleAgent-MatchedBudget',role='matched-1'),
                 'requested_model':'deepseek-flash','backend':'dsh','refresh_slots':6,'role_seconds':5400,
                 'refresh_per_turn_seconds':900,'refresh_slot_file':str(Path(d)/'controller-slot.json'),
                 'budget':{'cash_budget_revision':REVISION}}
            class Recorder:
                max_output=256000
                def __init__(self):self.scopes=[]
                def reserve_request(self,s,**kwargs):self.scopes.append((s,kwargs));return len(self.scopes)
            inner=Recorder();ledger=MatchedSlotLedger(inner,job)
            for i in range(1,7):write_slot(job,i);ledger.reserve_request('ignored')
            self.assertEqual([s.rsplit('/',1)[-1] for s,_ in inner.scopes],['matched-'+str(i) for i in range(1,7)])
            with self.assertRaises(ValueError):write_slot(job,7)
            Path(job['refresh_slot_file']).write_text(json.dumps({'index':7,'scope':'arbitrary'}))
            with self.assertRaises(ValueError):ledger.reserve_request('ignored')

if __name__=='__main__':unittest.main()
