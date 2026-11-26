"""Fresh three-model benchmark controller. Official Harnesses own all coding/tools."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
import os
import resource
from pathlib import Path
import sys
import time
import traceback
sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).parent/'src'),'/opt/workbench/benchmark/envs/science-tms-v1/lib/python3.12/site-packages']
import p6_guidance_linux as old
import p6_main_runtime_linux as main
from p6_main_budget import MainLedger,task_limits
from p6_refresh_protocol import (TASKS,MODELS,METHODS,REVISION,expected_model,model_for_job,
    handoff_prompt,verify_handoff_trace,method_order,require_clean_barrier,complete_group,require_operational_worker,execution_host_failure,
    refresh_judge_prompt,require_valid_refresh_judgment)
from p6_refresh_sessions import write_slot
from p6_io_accounting import Epoch,require_group,actual_controls,group_path
from p6_trace_evidence import tool_trace
from p6_network_policy import RETRY10_POLICY
from p2_candidates import exclusive_json,digest
from p2_judges import J3,evidence
from p6_main_contract import enhanced_selection
from pi_full_protocol import Journal,exclusive,UncertainStage
shared=main.shared
BASE=Path('/opt/workbench/benchmark/private/model-refresh')
LEDGER=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
OBSERVER=None


def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def measured_test(tester,source,hidden=False):
    start_wall=time.time_ns();start_mono=time.perf_counter_ns()
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    result=tester(source,hidden)
    end_mono=time.perf_counter_ns();end_wall=time.time_ns()
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    result=dict(result,trusted_measurement={
        'wall_clock_ns_start':start_wall,'wall_clock_ns_end':end_wall,
        'monotonic_ns_start':start_mono,'monotonic_ns_end':end_mono,
        'monotonic_seconds':(end_mono-start_mono)/1e9,
        'wall_minus_monotonic_seconds':((end_wall-start_wall)-(end_mono-start_mono))/1e9,
        'child_user_seconds':after.ru_utime-before.ru_utime,
        'child_system_seconds':after.ru_stime-before.ru_stime,
        'gpu_kernel_time':'unavailable_unless_native_oracle_records_it',
        'clock_consistency_does_not_prove_historical_clock_cause':True})
    return result


def setup(payload,name,scope,role='builder',source=None,view=None,prompt=None,offline=False,matched=False):
    model=expected_model(scope);backend='dsh' if model=='deepseek-flash' else 'codex'
    d,env=main.job(name,backend,role,source=source,view=view,prompt=prompt,
        mode='humanize_flow' if role in ('verifier','reviewer') else 'native_driver',offline=offline,handoff_bytes=8_000_000)
    d.update(scope=scope,requested_model=model,refresh_handoff_required=role in ('verifier','reviewer'))
    authority=group_path(payload['run_id'],controls=offline)
    membership=Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    current_group=Path('/sys/fs/cgroup')/membership.lstrip('/')
    d['authority_write_denied_paths']=list({str(authority/'cgroup.procs'),str(current_group/'cgroup.procs')})
    model_for_job(d)
    raw=Path(d['input_file']).read_bytes()
    d['prompt']=handoff_prompt(d['input_file'],raw,d['prompt'])
    d['deepseek_transport_policy']=RETRY10_POLICY
    if backend=='codex':
        directory=payload['plan']['codex_binary_directory']
        vendor=payload['plan']['codex_installation_directory']
        env['PATH']=directory+':'+vendor+'/codex-path:'+env['PATH'];d['public_read_paths'].append(vendor)
        d['refresh_cli_sha256']=payload['plan']['codex_binary_sha256']
    # Exact private authority/cross-role states are denied. Full input is inlined,
    # but that never grants access to sibling worktrees, hidden truth or credentials.
    for p in shared.ACTIVE['root'].glob('*/input.json'):
        if str(p)!=d['input_file']:d['denied_paths'].append(str(p))
    if matched:
        seconds=shared.ACTIVE['generation_seconds']
        d.update(refresh_slots=6,refresh_per_turn_seconds=seconds,role_seconds=6*seconds,
                 refresh_slot_file=str(Path(d['root'])/'controller-slot.json'))
        write_slot(d,1);d['denied_paths'].append(d['refresh_slot_file'])
    return {'descriptor':d,'env':env}


def execute(spec):
    d=spec['descriptor']
    if not d.get('offline_control'):
        ledger=shared.ACTIVE['ledger'];current=read(LEDGER);ledger.validate(current)
        if d['backend']=='dsh' and (len(current['requests'])>=ledger.requests or current['cash_bound_nano']+ledger.request_reserve>ledger.cash_nano):
            raise RuntimeError('CUMULATIVE_BUDGET_STOP: preserve finished substeps; no role may be dispatched')
    if OBSERVER:OBSERVER.role(d['scope'],'STARTED')
    w=shared.launch(d,spec['env'])
    if d.get('refresh_slots')==6:
        base=d['scope'].rsplit('/',1)[0]
        w['additional_accounting_scopes']=[base+'/matched-'+str(i) for i in range(2,7)]
    if not d.get('offline_control') and d['backend']=='codex':
        trace=tool_trace(d['root'],max_bytes=8_000_000)
        failure=execution_host_failure(trace)
        if failure:w.update(raw_worker_status=w['status'],status=failure['status'],execution_host_evidence=failure)
        elif d.get('refresh_handoff_required'):
            receipt=verify_handoff_trace(trace,d['input_file'],Path(d['input_file']).read_bytes())
            w['handoff_receipt']=receipt
            if receipt['status']!='HANDOFF_READ_RECEIPT_OBSERVED':
                w.update(raw_worker_status=w['status'],status='INFRA_HANDOFF_UNCONSUMED')
    if OBSERVER:OBSERVER.role(d['scope'],w['status'])
    shared.ACTIVE['workers'][Path(d['root']).name]=w
    return w


def candidate(journal,payload,name,scope,source=None,view=None,prompt=None,matched=False):
    spec=journal.run(name+'-setup',lambda:setup(payload,name,scope,source=source,view=view,prompt=prompt,matched=matched))
    worker=journal.run(name+'-model',lambda:execute(spec))
    require_operational_worker(worker)
    shared.ACTIVE['workers'][name]=worker
    value=journal.run(name+'-public',lambda:shared.candidate(name,worker))
    frozen=journal.run(name+'-freeze',lambda:old.freeze(value))
    return {'candidate':value,'worker':worker,'frozen':frozen}


def judge(journal,payload,name,scope,pool):
    view=evidence(pool)
    prompt=refresh_judge_prompt(pool)
    spec=journal.run(name+'-setup',lambda:setup(payload,name,scope,'verifier',view=view,prompt=prompt))
    worker=journal.run(name+'-model',lambda:execute(spec));require_operational_worker(worker);shared.ACTIVE['workers'][name]=worker
    def decision():
        if worker['status']!='COMPLETED':return {'status':worker['status']}
        try:return J3(lambda _: (worker['answer']['judgment'],{'session_id':worker['session_id'],'usage':worker['usage']})).judge(pool)
        except (ValueError,KeyError,TypeError) as error:
            return {'status':'INVALID_JUDGMENT','error_type':type(error).__name__,'reason':str(error)}
    value=journal.run(name+'-judgment',decision)
    return require_valid_refresh_judgment(value)


def run_model_task(root,payload,tid,label):
    dest=root/tid/label;dest.mkdir(parents=True,exist_ok=True);(dest/'control').mkdir(exist_ok=True)
    canary=dest/'control/canary'
    if not canary.exists():canary.write_text('private controller authority')
    j=Journal(dest/'control/stages');tp,task,tester=old.make_task(payload,tid)
    io_root=require_group(payload['run_id']);results={};timings={};base_scope='REFRESH/'+payload['run_id']+'/'+tid+'/'+label
    with task['fixture_context'] as url:
        old.activate(dest,payload,tp,task,tester,url)
        shared.test_source=lambda source,hidden=False:measured_test(tester,source,hidden)
        for method in method_order(TASKS.index(tid),list(MODELS).index(label)):
            # Family activity limits apply to each method, not an unfair combined
            # envelope consumed by whichever method happens to run first.
            limits=task_limits(payload['budget'],tp['task'])
            shared.ACTIVE['deadline']=time.monotonic()+limits['active_seconds']
            with Epoch(io_root,tid+'--'+label+'--'+method) as io_epoch:
                start=j.run(method+'-clock-start',lambda:{'wall_ns':time.time_ns(),'monotonic_ns':time.perf_counter_ns(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()})
                if method=='Direct':
                    results[method]=candidate(j,payload,'direct',base_scope+'/Direct/direct')
                elif method=='SingleAgent-MatchedBudget':
                    results[method]=candidate(j,payload,'matched',base_scope+'/'+method+'/matched-1',matched=True)
                else:
                    pool_rows=[];prepared=[]
                    # Independent model work runs concurrently. Public/GPU checks
                    # remain serial after all three builders finish.
                    for cid in ('A','B','C'):
                        name='pool-'+cid;scope=base_scope+'/Enhanced/'+name
                        spec=j.run(name+'-setup',lambda n=name,s=scope:setup(payload,n,s))
                        prepared.append((cid,name,spec))
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        pending=[(cid,name,executor.submit(j.run,name+'-model',lambda v=spec:execute(v))) for cid,name,spec in prepared]
                        completed=[(cid,name,future.result()) for cid,name,future in pending]
                    for cid,name,worker in completed:
                        require_operational_worker(worker)
                        shared.ACTIVE['workers'][name]=worker
                        value=j.run(name+'-public',lambda n=name,w=worker:shared.candidate(n,w))
                        j.run(name+'-freeze',lambda v=value:old.freeze(v))
                        pool_rows.append(dict(value,id=cid))
                    pool=j.run('public-pool',lambda:shared.public_pool(pool_rows))
                    initial_judge=judge(j,payload,'judge-input',base_scope+'/Enhanced/judge-input',pool)
                    view={'task':task['prompt'],'pool':pool,'judgments':[initial_judge]}
                    prompt=task['prompt']+'\nAct as an independent Reviewer. Consider every A/B/C candidate including failures. Implement and commit M, or explicitly REFUSE. Existing tests/dependencies immutable; read and hash full input. Report all considered IDs.'
                    spec=j.run('reviewer-setup',lambda:setup(payload,'reviewer',base_scope+'/Enhanced/reviewer','reviewer',view=view,prompt=prompt))
                    w=j.run('reviewer-model',lambda:execute(spec));require_operational_worker(w);shared.ACTIVE['workers']['reviewer']=w
                    merged=j.run('reviewer-public',lambda:shared.candidate('M',w))
                    decision=w.get('answer',{}).get('decision',{})
                    if sorted(decision.get('considered_candidates',[]))!=['A','B','C'] or decision.get('action')!='IMPLEMENTED':merged['verdict']='FAIL'
                    expanded=j.run('expanded-pool',lambda:shared.public_pool(pool_rows+[merged],'JUDGE_COMPARISON'))
                    final_judge=judge(j,payload,'judge-final',base_scope+'/Enhanced/judge-final',expanded)
                    chosen=enhanced_selection(pool,expanded,initial_judge,final_judge) if initial_judge.get('status')=='COMPLETED' and final_judge.get('status')=='COMPLETED' else None
                    c=next((c for c in pool_rows+[merged] if c['id']==chosen),None)
                    results[method]={'candidate':c,'worker':{'status':'COMPLETED' if chosen else 'FAIL' if initial_judge.get('status')=='COMPLETED' and final_judge.get('status')=='COMPLETED' else 'INDETERMINATE'},'frozen':old.freeze(c) if c else None,'pool':pool,'expanded':expanded,'initial_judgment':initial_judge,'final_judgment':final_judge}
                end=j.run(method+'-clock-end',lambda:{'wall_ns':time.time_ns(),'monotonic_ns':time.perf_counter_ns(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()})
                timings[method]={'start':start,'end':end,'elapsed_seconds':(end['monotonic_ns']-start['monotonic_ns'])/1e9 if start['boot_id']==end['boot_id'] else 'unavailable_cross_boot','includes_public_checks':True,'excludes_hidden_acceptance':True}
            timings[method]['journal_clock_elapsed_seconds']=timings[method]['elapsed_seconds']
            timings[method]['elapsed_seconds']=io_epoch.measurement['raw_elapsed_seconds']
            timings[method]['io_adjustment']=j.run(method+'-io-observation',lambda:io_epoch.measurement)
        barrier=j.run('three-methods-frozen',lambda:{m:{'program_sha256':r['frozen']['program_sha256'] if r['frozen'] else '0'*64,'hidden_seen':False,'no_eligible_selection':r['candidate'] is None} for m,r in results.items()})
        require_clean_barrier(barrier);rows=[]
        for method in METHODS:
            r=results[method];c=r['candidate'];w=r['worker']
            if c:old.verify(c,r['frozen'])
            def accept():
                if not c or w['status']!='COMPLETED' or c.get('verdict')!='PASS':return {'verdict':'NOT_RUN','reason':'Completed clean publicly eligible program required'}
                try:return measured_test(tester,Path(c['root'])/'code',True)
                except (OSError,ImportError,ValueError,KeyError,TypeError) as e:return {'verdict':'INFRA_FAIL','error_type':type(e).__name__,'reason':str(e)[:700]}
            with Epoch(io_root,tid+'--'+label+'--'+method+'-acceptance') as acceptance_io:
                acceptance=j.run(method+'-acceptance',accept)
            acceptance_io_measurement=j.run(method+'-acceptance-io',lambda:acceptance_io.measurement)
            if c:old.verify(c,r['frozen'])
            status=w['status'] if w['status']!='COMPLETED' else c['verdict'] if c['verdict']!='PASS' else acceptance['verdict']
            from p6_refresh_accounting import summarize
            metrics=summarize(read(LEDGER),shared.ACTIVE['workers'],base_scope+'/'+method)
            rows.append({'task_id':tid,'model':label,'method':method,'outcome':status,'candidate':c,'acceptance':acceptance,'frozen':r['frozen'],'barrier_sha256':digest(barrier),'scientific_review':'PENDING_SOURCE_REPORT_FIGURE' if tp['task']['family']=='scientific' else 'NOT_APPLICABLE','metrics':metrics,'method_timing':timings[method],'acceptance_io_adjustment':acceptance_io_measurement})
    return {'task_id':tid,'model':label,'status':'THREE_METHOD_EXECUTION_CLOSED','rows':rows,'methods':results,'workers':shared.ACTIVE['workers']}


def verify_plan(payload):
    p=payload['plan'];body=dict(p);h=body.pop('plan_sha256')
    if digest(body)!=h:raise ValueError('Frozen plan differs')
    if p['tasks']!=list(TASKS) or p['models']!=MODELS or p['methods']!=list(METHODS):raise ValueError('Exact 16x3x3 plan required')
    if payload['budget']!=p['budget']:raise ValueError('Budget differs')
    for path,value in {**p['source_sha256'],**p['retained_sha256'],**p.get('runtime_tools_sha256',{})}.items():
        if sha(path)!=value:raise ValueError('Frozen/retained file changed: '+path)
    return p


def compare(payload):
    plan=verify_plan(payload);controls=read(plan['controls_receipt'])
    if controls['status']!='PASS_REFRESH_ZERO_MODEL_CONTROLS' or controls['plan_sha256']!=plan['plan_sha256'] or controls['source_sha256']!=plan['source_sha256']:raise ValueError('Exact runtime controls required')
    ledger=MainLedger(LEDGER,payload['budget']);ledger.validate(read(LEDGER))
    prior=read(plan['ledger_archive']);current=read(LEDGER)
    if any(current[k][:len(prior[k])]!=prior[k] for k in ('requests','codex_turns')):raise ValueError('Legacy ledger prefix differs')
    root=BASE/payload['run_id'];root.mkdir(parents=True,exist_ok=True);j=Journal(root/'stages');results=[]
    for task_index,tid in enumerate(TASKS):
        labels=list(MODELS);shift=task_index%len(labels)
        for label in labels[shift:]+labels[:shift]:
            name=tid+'--'+label;done=root/'stages'/(name+'.completed.json')
            # Never mark an entire model-task started: only exact completed
            # stages are reusable; uncertain model stages remain blocked.
            if done.exists():result=j.run(name,lambda:None)
            else:
                result=run_model_task(root,payload,tid,label)
                complete_group(done,name,result)
            results.append(result)
            if OBSERVER:OBSERVER.closed=len(results)*3
            (root/'progress.json').write_text(json.dumps({'status':'RUNNING','closed_model_task_groups':len(results),'closed_result_cells':len(results)*3,'expected_result_cells':144,'checked_unix':time.time()},indent=2))
    receipt={'status':'REFRESH_EXECUTION_COMPLETED_SCIENCE_REVIEW_PENDING','closed_result_cells':144,'results':results,'ledger_sha256':sha(LEDGER),'plan_sha256':plan['plan_sha256'],'old_experiment_replays':0}
    exclusive(root/'receipt.json',receipt);(root/'progress.json').write_text(json.dumps({k:v for k,v in receipt.items() if k!='results'},indent=2))
    return {'status':receipt['status'],'root':str(root)}



def controls(payload):
    plan=verify_plan(payload);before=sha(LEDGER)
    io_control=actual_controls(require_group(payload['run_id'],controls=True))
    root=BASE/(payload['run_id']+'-controls');root.mkdir(parents=True,exist_ok=False)
    from p6_refresh_controls import session_controls
    sessions=session_controls(payload['budget'])
    from p6_codex_tools_control import run_controls as actual_tool_controls
    tools=actual_tool_controls({'vendor':plan['codex_installation_directory'],'missing_binary_directory':'/opt/workbench/model-refresh-20261126/tools/codex-0.172.0','prefix':str(main.BASE/'envs/black-py383'),'budget':payload['budget']})
    rows=[];positives=[]
    for tid in TASKS:
        dest=root/tid;dest.mkdir();(dest/'control').mkdir();(dest/'control/canary').write_text('controller only')
        tp,task,tester=old.make_task(payload,tid)
        with task['fixture_context'] as url:
            old.activate(dest,payload,tp,task,tester,url,offline=True)
            gold=None
            if tp['task']['family']!='scientific':
                frozen=read(main.BASE/'science/private/public-main-controls-frozen-v2.json')
                entry=next(c for c in frozen['tasks'] if c['task_id']==tid);gold=read(entry['receipt'])['gold']
                pg=tester(gold,False);hg=tester(gold,True);hb=tester(task['base'],True)
                record={'task_id':tid,'public_gold':pg['verdict'],'hidden_gold':hg['verdict'],'hidden_buggy':hb['verdict'],'helper_binding':task['helper_binding']}
                positives.append(record)
                if (pg['verdict'],hg['verdict'],hb['verdict'])!=('PASS','PASS','FAIL'):raise ValueError('Exact public/hidden helpers failed: '+tid)
            settings=[('direct-'+label,label,'Direct','direct','builder',False) for label in MODELS]
            settings+=[('matched-'+label,label,'SingleAgent-MatchedBudget','matched-1','builder',True) for label in ('GPT62-Sol','DS41-Flash1017')]
            settings+=[('readonly','GPT61-Sol','Enhanced','judge-input','verifier',False)]
            for name,label,method,role,agent_role,matched in settings:
                scope='REFRESH/'+payload['run_id']+'/'+tid+'/'+label+'/'+method+'/'+role
                spec=setup(payload,name,scope,agent_role,source=gold if agent_role=='builder' else None,offline=True,matched=matched)
                if agent_role=='builder' and tp['task']['family']=='scientific' and task.get('kind') not in ('gc','egl'):
                    spec['descriptor'].pop('offline_public_command',None)
                worker=execute(spec)
                if worker['status']!='COMPLETED':raise ValueError('Worker control failed; inspect preserved logs: '+str(worker['root']))
                fence=read(Path(worker['root'])/'isolation.json')
                rows.append({'task_id':tid,'role':name,'status':worker['status'],'isolation':fence})
                if worker['status']!='COMPLETED' or fence['verdict']!='PASS':raise ValueError('Actual OS fence/public command failed: '+tid+'/'+name)
    if sha(LEDGER)!=before:raise ValueError('Controls modified real ledger')
    result={'status':'PASS_REFRESH_ZERO_MODEL_CONTROLS','rows':rows,'public_helper_controls':positives,
        'plan_sha256':plan['plan_sha256'],'source_sha256':plan['source_sha256'],
        'ledger_sha256_before':before,'ledger_sha256_after':sha(LEDGER),'provider_model_calls':0,'matched_session_control':sessions,'io_accounting_controls':io_control,'actual_codex_tool_controls':tools}
    exclusive(root/'receipt.json',result)
    return {'status':result['status'],'receipt':str(root/'receipt.json'),'fenced_roles':len(rows),'public_task_positive_negative_controls':len(positives)}


def prelaunch(payload):
    plan=verify_plan(payload);control=read(plan['controls_receipt'])
    if control['status']!='PASS_REFRESH_ZERO_MODEL_CONTROLS' or control['plan_sha256']!=plan['plan_sha256'] or control['source_sha256']!=plan['source_sha256']:
        raise ValueError('Exact frozen controls required before dispatch')
    if sha(Path(plan['codex_binary_directory'])/'codex')!=plan['codex_binary_sha256']:raise ValueError('Official CLI changed')
    if sha(LEDGER)!=plan['prior_ledger_sha256']:raise ValueError('Existing ledger changed; reconcile before first launch')
    with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return {'status':'PASS_EXACT_PRELAUNCH_ZERO_MODEL','plan_sha256':plan['plan_sha256']}


def entry(payload):
    global OBSERVER
    with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            require_group(payload['run_id'],controls=payload['mode']=='controls')
            if payload['mode']=='controls':return controls(payload)
            # Repeat all pre-spend checks under the actual run-owner lock.
            plan=verify_plan(payload);control=read(plan['controls_receipt'])
            if control['status']!='PASS_REFRESH_ZERO_MODEL_CONTROLS' or control['plan_sha256']!=plan['plan_sha256'] or control['source_sha256']!=plan['source_sha256']:
                raise ValueError('Exact controls missing')
            if sha(LEDGER)!=plan['prior_ledger_sha256']:raise ValueError('Ledger changed before authorized amendment')
            ledger=MainLedger(LEDGER,payload['budget'])
            # This infrastructure trial already has the exact authorized caps.
            # Preserve the current bytes, including the invalid trial's charges;
            # do not amend, reset or refund any request/subscription reservation.
            from p6_refresh_accounting import preserve_authorized_ledger
            amendment=preserve_authorized_ledger(ledger,plan['prior_ledger_sha256'],plan['ledger_archive'])
            root=BASE/payload['run_id'];root.mkdir(parents=True,exist_ok=True)
            exclusive(root/'amendment.json',amendment);exclusive(root/'plan.json',plan)
            from p6_refresh_observer import Observer
            OBSERVER=Observer(root,plan,LEDGER);OBSERVER.start()
            result=compare(payload);OBSERVER.close(result['status']);return result
        except BaseException as error:
            root=BASE/(payload['run_id']+'-controls' if payload['mode']=='controls' else payload['run_id'])
            root.mkdir(parents=True,exist_ok=True)
            exclusive(root/('stopped-'+str(time.time_ns())+'.json'),{'status':'STOPPED_PRESERVED','error_type':type(error).__name__,'message':str(error)[:1000],'traceback':traceback.format_exc()[-5000:]})
            if OBSERVER:OBSERVER.close('STOPPED_PRESERVED')
            raise


if __name__=='__main__':
    from p1_broker import protect_memory
    protect_memory();print(json.dumps(entry(json.load(sys.stdin))))
