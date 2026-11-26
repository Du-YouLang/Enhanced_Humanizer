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
    def test_infrastructure_trial_archives_existing_authorization_without_a_ledger_write(self):
        from p6_refresh_accounting import preserve_authorized_ledger
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger';ledger=MainLedger(p,self.new,fixture=True)
            ledger.reserve_request('old-unknown-preserved')
            ledger.reserve_codex_turn('old-completed-infra-role','gpt-6.1-sol')
            raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest();archive=Path(d)/'archive'
            result=preserve_authorized_ledger(ledger,sha,archive)
            self.assertEqual(p.read_bytes(),raw);self.assertEqual(archive.read_bytes(),raw)
            self.assertEqual(result['requests_retained'],1);self.assertEqual(result['subscriptions_retained'],1)
            with self.assertRaises(ValueError):preserve_authorized_ledger(ledger,'0'*64,Path(d)/'wrong')
            self.assertFalse((Path(d)/'wrong').exists())

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
    def test_actual_codex_custom_tool_envelope_and_missing_host_negative(self):
        from p6_refresh_protocol import execution_host_failure
        raw=b'{"public":"complete"}';path=PurePosixPath('/opt/task/input.json');sha=hashlib.sha256(raw).hexdigest()
        call={'type':'tool/call','source_backend':'codex','data':{'type':'custom_tool_call','call_id':'call-real-envelope','name':'exec','input':"text(await tools.exec_command({cmd:'python reads "+str(path)+"'}));"}}
        output={'type':'tool/result','source_backend':'codex','data':{'type':'custom_tool_call_output','call_id':'call-real-envelope','output':str(len(raw))+' '+sha}}
        trace={'truncated':False,'records':[call,output]}
        self.assertEqual(verify_handoff_trace(trace,path,raw)['status'],'HANDOFF_READ_RECEIPT_OBSERVED')
        output['data']['output']='failed to spawn code-mode host /opt/tools/codex-code-mode-host: host executable was not found'
        self.assertEqual(execution_host_failure(trace)['status'],'INFRA_EXECUTION_HOST_UNAVAILABLE')
        self.assertEqual(verify_handoff_trace(trace,path,raw)['status'],'INFRA_HANDOFF_UNCONSUMED')
        output['data']['output']='Chunk ID: example\nOutput: failed to spawn code-mode host is quoted documentation'
        self.assertIsNone(execution_host_failure(trace))

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

class IOAccountingTests(unittest.TestCase):
    def test_adjustment_uses_full_union_not_some_or_summed_process_delays(self):
        from p6_io_accounting import pressure,correction
        a=pressure('some avg10=0.0 total=1000000\nfull avg10=0.0 total=500000\n')
        b=pressure('some avg10=20.0 total=9000000\nfull avg10=10.0 total=2500000\n')
        v=correction(a,b,10)
        self.assertEqual(v['some_local_io_stall_seconds'],8)
        self.assertEqual(v['full_local_io_stall_seconds'],2)
        self.assertEqual(v['io_adjusted_elapsed_estimate_seconds'],8)
        self.assertEqual(v['primary_metric'],'RAW_ELAPSED')
    def test_missing_or_incompatible_accounting_never_becomes_zero(self):
        from p6_io_accounting import pressure,correction,group_path
        for raw in ('some total=0','some total=nan\nfull total=0','some total=1\nfull total=2'):
            with self.assertRaises(ValueError):pressure(raw)
        with self.assertRaises(ValueError):correction({'some':0,'full':0},{'some':10000000,'full':9000000},1)
        with self.assertRaises(ValueError):group_path('../other-project')
        self.assertTrue(str(group_path('refresh-20261126T030117Z')).replace('\\','/').endswith('/non-systemd/eh-refresh-20261126T030117Z'))


class JudgeWireContractTests(unittest.TestCase):
    def test_prompt_example_roundtrips_real_j3_and_ten_point_output_stays_rejected(self):
        from p6_refresh_protocol import refresh_judge_prompt,require_valid_refresh_judgment
        from p2_candidates import RUBRIC,digest
        from p2_judges import J3
        task='Frozen public task'
        p={'task_contract':task,'task_hash':digest(task.encode()),'base_commit':'base','env_hash':'env',
           'rubric':copy.deepcopy(RUBRIC),'rubric_hash':digest(RUBRIC),'candidates':[
               {'id':c,'base_commit':'base','env_hash':'env','prompt_hash':digest(task.encode()),'verdict':'PASS'} for c in 'ABCM']}
        p['pool_hash']=digest(p);before=copy.deepcopy(p)
        prompt=refresh_judge_prompt(p)
        raw=json.loads(prompt.split('Required judgment JSON shape: ',1)[1])
        raw['candidates'][0]['correctness']=4
        value=J3(lambda _:(raw,{})).judge(p)
        self.assertEqual(value['status'],'COMPLETED');self.assertEqual(p,before)
        self.assertIn('INTEGER from 0 through 4 inclusive',prompt)
        for bad in (9,4.0,True,-1):
            invalid=copy.deepcopy(raw);invalid['candidates'][0]['correctness']=bad
            with self.assertRaisesRegex(ValueError,'out of range'):J3(lambda _:(invalid,{})).judge(p)
        self.assertEqual(require_valid_refresh_judgment(value),value)
        with self.assertRaisesRegex(RuntimeError,'JUDGMENT_CONTRACT_BOUNDARY_STOP'):
            require_valid_refresh_judgment({'status':'INVALID_JUDGMENT','reason':'Sol rubric score out of range'})
        # A role budget outcome keeps its actual status; it is not a wire-contract failure.
        self.assertEqual(require_valid_refresh_judgment({'status':'TIMEOUT'}),{'status':'TIMEOUT'})


class RecoveryPreservationTests(unittest.TestCase):
    def test_completed_session_copy_never_calls_model_and_hash_mismatch_denies(self):
        from p6_refresh_recovery import seed_partial,journal_value,sha
        from p6_refresh_protocol import complete_group
        from pi_full_protocol import Journal
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'old/code';source.mkdir(parents=True);(source/'solver.py').write_text('print(1)')
            old=root/'model.completed.json';worker={'status':'COMPLETED','scope':'REFRESH/old/task/model/SingleAgent-MatchedBudget/matched-1','model_id':'deepseek-flash','root':str(source.parent),'work':str(source),'usage':[]}
            complete_group(old,'matched-model',worker);raw=old.read_bytes()
            spec={'partial_work':str(source),'partial_worker_journal':str(old),'partial_worker_sha256':sha(old)}
            dest=root/'new/task';j=Journal(dest/'control/stages');seed_partial(j,dest,spec)
            def replay():raise AssertionError('Must not dispatch')
            reused=j.run('matched-model',replay)
            self.assertEqual((Path(reused['work'])/'solver.py').read_bytes(),(source/'solver.py').read_bytes())
            self.assertEqual(reused['scope'],worker['scope']);self.assertEqual(old.read_bytes(),raw)
            self.assertTrue(j.run('matched-setup',replay)['descriptor']['retained_only'])
            seed_partial(j,dest,spec)
            spec['partial_worker_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'journal changed'):seed_partial(j,dest,spec)
            self.assertEqual(old.read_bytes(),raw)
    def test_only_identical_public_helper_alias_preserves_original_task_bytes(self):
        from p6_refresh_recovery import bind_retained_public_task,sha
        from p6_refresh_protocol import complete_group
        from p2_candidates import digest
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=root/'old';new=root/'new';prior=root/'prior'
            for folder in (old,new,prior):folder.mkdir()
            for folder in (old,new):(folder/'p6_public_visible.py').write_text('public checker only')
            legacy='Solve task; run '+str(old)+'/p6_public_visible.py'
            groups={}
            for label in ('GPT61-Sol','GPT62-Sol'):
                p=prior/(label+'.json');complete_group(p,label,{'methods':{'Enhanced':{'pool':{'task_contract':legacy}}}});groups[label]=str(p)
            (prior/'plan.json').write_text(json.dumps({'source_sha256':{str(old/'p6_refresh_linux.py'):'unused',str(old/'p6_public_visible.py'):sha(old/'p6_public_visible.py')}}))
            payload={'folder':str(new),'plan':{'score_contract_recovery':{'prior_root':str(prior),'retained_groups':groups}}}
            task={'id':'BIP-black-1','prompt':legacy.replace(str(old),str(new)),'public_read_paths':[]}
            value=bind_retained_public_task(copy.deepcopy(task),payload)
            self.assertEqual(value['prompt'],legacy);self.assertEqual(value['recovery_public_helper_binding']['task_hash'],digest(legacy.encode()))
            self.assertEqual(value['public_read_paths'],[str(old/'p6_public_visible.py')])
            with self.assertRaisesRegex(ValueError,'differs beyond'):bind_retained_public_task(dict(task,prompt=task['prompt']+'change threshold'),payload)
            (new/'p6_public_visible.py').write_text('different checker')
            with self.assertRaisesRegex(ValueError,'not the identical'):bind_retained_public_task(copy.deepcopy(task),payload)

    def test_changed_journal_is_not_accepted(self):
        from p6_refresh_recovery import journal_value
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'stage.json';p.write_text(json.dumps({'value':{'x':1},'value_sha256':'0'*64}))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):journal_value(p)

if __name__=='__main__':unittest.main()
