"""User-authorized single-pool checkpoint continuation; upstream tools unchanged.

Deployed separately from the frozen original runtime. Completed DS0/B/C programs
and traces are copied byte-for-byte; only Pool-A gets a new Humanize/DSH session.
The original request scope and remaining time are retained. Started uncertain
stages fail closed on restart; completed stages never call a model again.
"""
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import signal
import sys
import time

sys.path.insert(0, '/opt/workbench/source')
sys.path.insert(0, '/opt/workbench/source/src')
import p6_main_runtime_linux as main
import p6_runtime_linux as shared
from p1_broker import protect_memory
from p2_candidates import digest, exclusive_json
from p2_judges import J0
from p6_checkpoint_recovery import Stages, inventory, remaining_limits, sha
from p6_main_budget import MainLedger, authorization, task_limits
from p6_main_contract import enhanced_selection

ORIGINAL = 'p6-main-execute-BIP-black-5-20261012T151835Z'


def read(path):
    return json.loads(Path(path).read_bytes())


def run(payload):
    protect_memory()
    if os.getuid() == 0 or payload['original_run'] != ORIGINAL:
        raise ValueError('Only the explicitly authorized non-root Black-5 continuation')
    from workbench.benchmark import check_manifest
    check_manifest(payload['manifest'])
    _, budget_sha = authorization(payload['budget'])
    if payload['manifest']['budget_authorization_sha256'] != budget_sha:
        raise ValueError('Authorization changed')
    for path, expected in payload['source_sha256'].items():
        if sha(path) != expected:
            raise ValueError('Pinned executable changed: '+path)
    original = main.BASE/'private/main-runs'/ORIGINAL
    root = main.BASE/'private/main-runs'/payload['run_id']
    if root.exists():
        raise FileExistsError('Existing continuation requires explicit stage reconciliation')
    original_files = inventory(original)
    if digest(original_files) != payload['original_inventory_sha256']:
        raise ValueError('Original checkpoint bytes changed')
    task = main.public_task(payload)
    old_contract = read(original/'control/run-contract.json')
    if payload['task'] != old_contract['task']:
        raise ValueError('Original task identity or time allocation changed')
    ledger = MainLedger(main.LEDGER, payload['budget'])
    ledger_value = read(main.LEDGER)
    ledger.validate(ledger_value)
    old_worker = read(original/'pool-A/controller-outcome.json')
    launch = read(main.BASE/'private/main-launches'/(ORIGINAL+'.json'))
    debit = math.ceil((original/'failure.json').stat().st_mtime-launch['started_unix'])
    limits = task_limits(payload['budget'], payload['task'])
    bounds = remaining_limits(old_worker, ledger_value['requests'], ORIGINAL+'/pool-A',
                              limits['role_seconds'], ledger.role_requests, debit,
                              limits['active_seconds'])
    if bounds != payload['continuation_limits']:
        raise ValueError('Continuation limits changed after freezing')
    root.mkdir()
    (root/'control').mkdir()
    (root/'control/canary').write_text('withheld continuation controller state')
    contract = {k:v for k,v in payload.items() if k != 'key'}
    contract['public_prompt_sha256'] = digest(task['prompt'].encode())
    exclusive_json(root/'control/run-contract.json', contract)
    exclusive_json(root/'control/original-inventory.json', original_files)
    prep = read(original/'preparation.json')
    if prep['env_sha256'] != task['seal']['env_sha256'] or prep['base_commit'] != task['base_commit']:
        raise ValueError('Original environment or baseline changed')
    exclusive_json(root/'preparation.json', prep)
    shared.ACTIVE.clear()
    shared.ACTIVE.update(root=root, task=task, payload=payload, key=payload.pop('key'),
        ledger=ledger, deadline=time.monotonic()+bounds['activity_seconds_remaining'],
        generation_seconds=limits['role_seconds'], active_seconds=limits['active_seconds'],
        started_monotonic=time.monotonic(), workers={}, contract_sha256=digest(contract),
        preparation=prep, main_phase=True, defer_hidden=True, fixture_url=None)
    shared.LEDGER_PATH=main.LEDGER
    shared.test_source=main.public_test
    stages = Stages(root/'control/stages')
    def interrupted(signum, frame):
        raise InterruptedError('Continuation interrupted by signal '+str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    def unchanged():
        if inventory(original) != original_files:
            raise ValueError('Original checkpoint changed during continuation')
    # Copies contain only the role program and its own prior traces, not auth homes.
    def preserved_role(name):
        src, dest = original/name, root/name
        dest.mkdir()
        from p6_evaluate_linux import validate_source_links
        validate_source_links(src/'code')
        shutil.copytree(src/'code', dest/'code', symlinks=True)
        if (src/'humanize/epics').exists():
            shutil.copytree(src/'humanize/epics', dest/'humanize/epics', symlinks=True)
        (dest/'humanize').mkdir(exist_ok=True)
        (dest/'humanize/canary').write_text('non-secret retained peer state')
        worker=read(src/'controller-outcome.json')
        row=read(src/'candidate-private.json')
        worker.update(root=str(dest), work=str(dest/'code'))
        row['root']=str(dest)
        patch, source = shared.program_evidence(dest/'code', task['base_commit'])
        if patch != row['patch'] or source != row['source']:
            raise ValueError('Completed candidate changed: '+name)
        for filename, value in (('controller-outcome.json',worker),('candidate-private.json',row)):
            exclusive_json(dest/filename,value)
        exclusive_json(dest/'retained-origin.json',{'original_run':ORIGINAL,
            'original_role':name,'candidate_sha256':sha(src/'candidate-private.json'),
            'controller_sha256':sha(src/'controller-outcome.json'),'model_replayed':False})
        shared.ACTIVE['workers'][name]=worker
        return row
    raw=preserved_role('native-ds')
    b=preserved_role('pool-B');c=preserved_role('pool-C')
    staging=root/'control/pool-A-checkpoint';staging.mkdir()
    shutil.copytree(original/'pool-A/code',staging/'code',symlinks=True)
    descriptor, env=main.job('pool-A','dsh',source=staging/'code',offline=payload.get('mode')=='offline')
    descriptor['scope']=bounds['scope']
    descriptor['role_seconds']=bounds['role_seconds_remaining']
    descriptor['prompt'] += ('\nHuman explicitly authorized continuation of your own interrupted '
        'Pool-A workspace. This is a NEW DSH SESSION from the exact saved files; '
        'the earlier Humanize Flow is non-resumable. Inspect existing changes and '
        'finish only incomplete work. Do not start over or repeat completed tools. '
        'Your own earlier trajectories are retained under your Humanize HOME. '
        'Commit the finished change; the remaining role time is '+str(descriptor['role_seconds'])+' seconds.')
    if (original/'pool-A/humanize/epics').exists():
        shutil.copytree(original/'pool-A/humanize/epics',root/'pool-A/humanize/epics',symlinks=True)
    exclusive_json(root/'control/continuation-lineage.json',{
        'original_run':ORIGINAL,'original_pool_sha256':sha(original/'frozen-public-pool.json'),
        'bounds':bounds,'completed_candidate_model_replays':0,
        'original_conversation_resumed':False,'original_failure_preserved':True,
        'original_wall_interval':'unavailable','cash_budget_usd':200})
    tick=time.perf_counter()
    def model(name, action):
        if time.monotonic()>=shared.ACTIVE['deadline']:
            raise TimeoutError('Remaining activity cap exhausted')
        result=stages.run(name,action)
        unchanged()
        return result
    w=model('pool-A-model',lambda:shared.launch(descriptor,env))
    if payload.get('mode')=='offline':
        unchanged()
        after=read(main.LEDGER)
        if after!=ledger_value or w['status']!='COMPLETED':
            raise ValueError('Zero-model continuation preflight failed')
        value={'status':'PASS_ZERO_MODEL_CONTINUATION_CONTROL','model_requests':0,
               'bounds':bounds,'completed_candidate_model_replays':0,
               'original_bytes_unchanged':True,'ledger_sha256':sha(main.LEDGER),
               'actual_isolation':read(root/'pool-A/isolation.json')}
        exclusive_json(root/'receipt.json',value)
        return value
    shared.ACTIVE['workers']['pool-A']=w
    a=stages.run('pool-A-public',lambda:shared.candidate('A',w))
    pool_rows=[a,b,c];workers=[w,shared.ACTIVE['workers']['pool-B'],shared.ACTIVE['workers']['pool-C']]
    pool=shared.public_pool(pool_rows)
    oldpool=read(original/'frozen-public-pool.json')
    for cid in ('B','C'):
        if next(x for x in pool['candidates'] if x['id']==cid) != next(x for x in oldpool['candidates'] if x['id']==cid):
            raise ValueError('Completed public candidate changed')
    exclusive_json(root/'frozen-public-pool.json',pool)
    if w['status']=='INFRA_RETRY_PENDING':
        from p6_network_policy import NetworkRetryPending
        raise NetworkRetryPending('Pool-A interrupted again; new checkpoint preserved without replay')
    if w['status']=='INFRA_FAIL':
        raise RuntimeError('Pool-A continuation infrastructure failure preserved')
    judgments={'J0':J0().judge(pool),'J2':main.region_blocked(pool)}
    selected=shared.select(pool,judgments['J0'])
    selections={'A':raw,'B':next((x for x in pool_rows if x['id']==selected),None)}
    scopes={'A':[raw['scope']],'B':[x['scope'] for x in workers]}
    judgments['J3']=model('judge-input',lambda:main.judge('judge-input',pool))
    view={'task':task['prompt'],'pool':pool,'judgments':[judgments['J3']]}
    prompt=task['prompt']+'\nAct as an independent Reviewer. Read input.json, consider every A/B/C candidate including failures. Freely implement a new M from this baseline, or explicitly REFUSE. Preserve existing tests/dependencies. Report every considered candidate ID and commit cleanly.'
    mw=model('reviewer',lambda:main.launch('reviewer','codex','reviewer',view=view,prompt=prompt))
    m=stages.run('reviewer-public',lambda:shared.candidate('M',mw))
    decision=mw.get('answer',{}).get('decision',{})
    considered=decision.get('considered_candidates',[])
    if mw['status']=='COMPLETED' and (not isinstance(considered,list) or not all(isinstance(x,str) for x in considered) or sorted(considered)!=['A','B','C'] or decision.get('action')!='IMPLEMENTED'):
        m['verdict']='FAIL'
    expanded=shared.public_pool(pool_rows+[m],'JUDGE_COMPARISON')
    jm=model('judge-merge',lambda:main.judge('judge-merge',expanded))
    exclusive_json(root/'frozen-expanded-public-pool.json',expanded)
    chosen=enhanced_selection(pool,expanded,judgments['J3'],jm)
    enhanced=next((x for x in pool_rows+[m] if x['id']==chosen),None)
    shared.ACTIVE['enhancement_judge_incomplete']=judgments['J3']['status']!='COMPLETED' or jm['status']!='COMPLETED'
    selections['C']=enhanced
    scopes['C']=scopes['B']+[shared.ACTIVE['workers'][n]['scope'] for n in ('judge-input','reviewer','judge-merge')]
    exclusive_json(root/'merge-ablation-public.json',{'pool_hash':pool['pool_hash'],'best_of_n':selected,
        'with_m':chosen,'judgment':jm,'all_originals_failed_visible':all(x['verdict']!='PASS' for x in pool_rows)})
    transfer=enhanced or next((x for x in pool_rows+[m] if x['id']==(jm.get('ranking') or ['M'])[0]),m)
    for arm,name,prior,mode in [('D','native-sol',None,'native_driver'),('E','relay',raw,'humanize_flow'),('F','enhanced-relay',transfer,'humanize_flow')]:
        source=Path(prior['root'])/'code' if prior else None
        public={'task':task['prompt'],'prior':{k:prior.get(k) for k in ('id','head_commit','patch','test_report','verdict')} if prior else None}
        bw=model(name,lambda:main.launch(name,'codex',source=source,view=public,mode=mode,
            prompt=task['prompt']+'\nAct as a fresh Builder. Inspect and improve the current program, freely redesign if needed, run public checks, and commit a clean change.'))
        selections[arm]=stages.run(name+'-public',lambda:shared.candidate(arm,bw))
        scopes[arm]=(scopes['A'][:] if arm=='E' else scopes['C'][:] if arm=='F' else [])+[bw['scope']]
    judgments['J1']=model('J1',lambda:main.lav('J1',pool))
    merge_j1=model('J1-merge',lambda:main.lav('J1-merge',expanded))
    exclusive_json(root/'merge-judgments.json',{'J0':J0().judge(expanded),'J1':merge_j1,'J2':main.region_blocked(expanded),'J3':jm})
    exclusive_json(root/'judgments.json',judgments)
    exclusive_json(root/'frozen-selections.json',{'heads':{arm:x.get('head_commit') if x else None for arm,x in selections.items()},
        'public_candidate_hashes':{arm:digest(x) if x else None for arm,x in selections.items()},'hidden_results_seen':False})
    segment=time.perf_counter()-tick
    shared.ACTIVE['key']=''
    truth={};cache={};oracle_tick=time.perf_counter()
    all_candidates={x['id']:x for x in [raw,*pool_rows,m,*[x for x in selections.values() if x is not None]]}
    for cid,x in all_candidates.items():
        identity=digest({'patch':x.get('patch'),'source':x.get('source')})
        if x['verdict']!='PASS' or x['worker_status']!='COMPLETED':
            checked={'verdict':'FAIL','private_execution':'NOT_RUN_PUBLIC_HARD_GATE_FAILED','elapsed_seconds':0}
        else:
            if identity not in cache:cache[identity]=main.public_test(Path(x['root'])/'code',True)
            checked=cache[identity]
        truth[cid]={'program_identity':identity,'worker_status':x['worker_status'],'public_verdict':x['verdict'],'acceptance':checked}
        exclusive_json(root/('private-acceptance-'+cid+'.json'),truth[cid])
    exclusive_json(root/'private-candidate-acceptance.json',truth)
    # Preserve the runtime's outcome classification/schema, but do not invent the
    # lost historical end-to-end interval. Capture before its exclusive writer.
    original_writer=main.exclusive_json
    results=[]
    try:
        for arm,x in selections.items():
            saved=[]
            main.exclusive_json=lambda path,value:saved.append((path,value))
            row=main.record(arm,x,scopes[arm],0,truth[x['id']]['acceptance'] if x else None)
            row['metrics'].update(end_to_end_seconds='unavailable',model_and_public_check_seconds='unavailable')
            row.update(reason='User-authorized Pool-A checkpoint continuation; completed DS0/B/C retained; selections frozen before private acceptance',
                timing_scope='ORIGINAL_WALL_INTERVAL_UNAVAILABLE',continuation_run=payload['run_id'])
            from workbench.benchmark import validate_result
            validate_result(row,payload['manifest'],prep)
            if len(saved)!=1:raise ValueError('Unexpected result writer count')
            original_writer(saved[0][0],row);results.append(row)
    finally:main.exclusive_json=original_writer
    unchanged()
    receipt={'status':'MAIN_TASK_COMPLETED','task_id':task['id'],'run_id':root.name,'results':results,
        'continuation_of':ORIGINAL,'recovery_kind':bounds['recovery_kind'],'completed_candidate_model_replays':0,
        'model_activity_seconds':'unavailable','controller_end_to_end_seconds':'unavailable',
        'continuation_model_and_public_seconds':segment,'original_activity_debit_seconds':debit,
        'common_generation_timeout_seconds':limits['role_seconds'],'model_activity_time_cap_seconds':limits['active_seconds'],
        'judgments':{k:v['status'] for k,v in judgments.items()},'benchmark_oracle_audit_seconds':time.perf_counter()-oracle_tick,
        'private_unique_program_evaluations':len(cache),'full_tool_trace_sensitivity':'PENDING_SEPARATE_SAME_POOL_REVIEW',
        'original_inventory_sha256':digest(original_files),'failures_preserved':True,'api_cash_usd':'unavailable'}
    exclusive_json(root/'receipt.json',receipt)
    return {k:v for k,v in receipt.items() if k!='results'}|{'arms':{r['arm']:r['outcome'] for r in results}}


if __name__=='__main__':
    try:print(json.dumps(run(json.load(sys.stdin))),flush=True)
    except Exception as error:
        import traceback
        from p6_network_policy import NetworkCheckRequired,NetworkRetryPending
        pending=isinstance(error,(NetworkCheckRequired,NetworkRetryPending))
        failure={'status':'INFRA_RETRY_PENDING' if pending else 'INFRA_FAIL','error_type':type(error).__name__,
                 'model_failure':False if pending else 'unavailable','traceback':traceback.format_exc()}
        root=shared.ACTIVE.get('root')
        if root and not (root/'failure.json').exists():exclusive_json(root/'failure.json',failure)
        print(json.dumps({k:v for k,v in failure.items() if k!='traceback'}),flush=True)
        raise
