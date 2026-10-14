"""Scoped, explicit overload continuations around the installed official Pi SDK."""
import json,math,os,shutil,sys,time
from pathlib import Path
sys.path[:0]=[str(Path(__file__).parent),'/opt/workbench/source','/opt/workbench/source/src']
from p1_broker import protect_memory
from p2_candidates import exclusive_json,digest
from p6_checkpoint_recovery import inventory,Stages,sha
from p6_evaluate_linux import validate_source_links
from pi_recovery_policy import overload_bounds,is_overload_message,copy_checkpoint
from pi_formal_linux import execute,read,RUNS,LEDGER,main,shared,quiet

ORIGINAL='formal-compare-20261014T071703Z'
AUTH='USER_PROVIDER_OVERLOAD_RETRY_20261014'

def eligible(name):
    root=RUNS/ORIGINAL/name
    worker=read(root/'controller-outcome.json');result=read(root/'result.json')
    if worker.get('status') not in ('INFRA_FAIL','INFRA_RETRY_PENDING') or result['outcome'] not in ('INFRA_FAIL','INFRA_RETRY_PENDING'):
        raise ValueError('Original completed/model failures are not overload recovery targets')
    events=[json.loads(s) for s in (root/'events.private.jsonl').read_text().split('\n') if s.strip()]
    messages=[e['message'] for e in events if e['type']=='message_end' and e.get('message',{}).get('role')=='assistant']
    if not messages or not is_overload_message(messages[-1]):raise ValueError('Exact final provider-overload evidence required')
    if any(c.get('type')=='toolCall' for c in messages[-1].get('content',[])):
        raise ValueError('Failed response tool calls require independent reconciliation')
    if not any(e['type']=='agent_settled' for e in events):raise ValueError('Unsettled prior process')
    files=list((root/'agent/sessions').glob('*.jsonl'))
    if len(files)!=1:raise ValueError('One exact official prior session required')
    limits=overload_bounds(worker,result['role_seconds'])
    return {'cell':name,'result_sha256':sha(root/'result.json'),'worker_sha256':sha(root/'controller-outcome.json'),
      'trace_sha256':sha(root/'events.private.jsonl'),'session_file':str(files[0]),'session_sha256':sha(files[0]),
      'inventory_sha256':digest(inventory(root)),'cell_descriptor':result['cell'],'scope':worker['scope'],'limits':limits}

def controls(payload):
    root=RUNS/payload['run_id'];root.mkdir();(root/'control').mkdir();canary=root/'control/canary';canary.write_text('controller only')
    results={};driver=Path(__file__).with_name('pi_session.mjs')
    def one(name,fault,retry=True,source=None):
        dest=root/name;dest.mkdir();work=dest/'code'
        if source:shutil.copytree(source/'code',work,symlinks=True);shutil.copyfile(source/'fixture-ledger.json',dest/'fixture-ledger.json')
        else:
            work.mkdir();shared.trusted_git(work,'init','-q');shared.trusted_git(work,'config','user.name','Pi recovery control');shared.trusted_git(work,'config','user.email','control@example.invalid')
        recovery={'authorization':AUTH,'authorized_role_seconds':900,'authorized_role_requests':1000,
            'role_requests_remaining':997 if source else 1000,'prior_consecutive_failures':1 if source else 0,
            'fixture_agent_retry':retry}
        if source:
            recovery.update(session_file=str(next((source/'agent/sessions').glob('*.jsonl'))),scope=read(source/'controller-outcome.json')['scope'])
        w=execute(dest,work,'P3','fixture',payload['budget'],'Continue unfinished work from the existing checkpoint; write, test and commit probe_value.py as required.',
            890 if source else 900,driver,fixture_fault=fault,denied=[canary],recovery=recovery if retry or source else None)
        results[name]=w;return dest
    one('broker-reconnect','broker-overload',False)
    one('sdk-reconnect','agent-overload')
    one('sdk-five-stop','agent-overload-five')
    one('quota-no-retry','agent-quota')
    prior=one('prior-session','agent-overload',False);prior_inventory=inventory(prior)
    one('fork-recovery',None,source=prior)
    one_good=results['sdk-reconnect'];five=results['sdk-five-stop'];quota=results['quota-no-retry'];fork=results['fork-recovery']
    good=(results['broker-reconnect']['status']=='COMPLETED' and results['broker-reconnect']['wire_count']==6 and results['broker-reconnect']['sdk_dispatches']==5
          and one_good['status']=='COMPLETED' and one_good['wire_count']==6 and one_good['summary']['total_tool_calls']==4
          and one_good['unknown_wire_usage_reservations']==1 and one_good['summary']['provider_retries']==1
          and five['status']=='INFRA_RETRY_PENDING' and five['wire_count']==7 and five['summary']['total_tool_calls']==2
          and quota['status']=='INFRA_FAIL' and quota['wire_count']==3 and quota['summary']['provider_retries']==0
          and results['prior-session']['status']=='INFRA_FAIL' and fork['status']=='COMPLETED'
          and fork['summary']['total_tool_calls']==2 and fork['wire_count']==3
          and inventory(prior)==prior_inventory)
    rec={'status':'PASS_OVERLOAD_RECOVERY_CONTROLS' if good else 'CONTROL_FAILED','results':results,
         'original_checkpoint_unchanged':inventory(prior)==prior_inventory,'model_calls':0,'source_sha256':payload['source_sha256']}
    exclusive_json(root/'receipt.json',rec)
    return {'status':rec['status'],'root':str(root),'model_calls':0,
            'workers':{k:{n:v.get(n) for n in ('status','wire_count','sdk_dispatches')} for k,v in results.items()}}

def intake(payload):
    root=RUNS/ORIGINAL;original_plan=read(root/'plan.json')
    for p,h in {**original_plan['source_sha256'],**original_plan['main_manifest']['runner_source_sha256']}.items():
        if sha(p)!=h:raise ValueError('Frozen original source changed')
    names=[]
    for f in root.glob('*/result.json'):
        try:names.append(eligible(f.parent.name))
        except ValueError:continue
    return {'status':'OVERLOAD_CHECKPOINT_INTAKE','original_run':ORIGINAL,'original_plan_sha256':original_plan['plan_sha256'],
            'targets':names,'original_finished':(root/'receipt.json').exists(),
            'original_receipt_sha256':sha(root/'receipt.json') if (root/'receipt.json').exists() else None}

def recover(payload):
    quiet();plan=payload['plan'];body=dict(plan);expected=body.pop('recovery_plan_sha256')
    if digest(body)!=expected or plan['authorization']!=AUTH:raise ValueError('Recovery plan changed')
    old=RUNS/ORIGINAL
    if sha(old/'receipt.json')!=plan['original_receipt_sha256']:raise ValueError('Original finite matrix is unfinished or changed')
    current=intake(payload)
    if current['targets']!=plan['targets']:raise ValueError('Original overload checkpoints or limits changed')
    root=RUNS/payload['run_id'];root.mkdir();(root/'control').mkdir();(root/'control/canary').write_text('private recovery control')
    exclusive_json(root/'control/run-contract.json',{k:v for k,v in payload.items() if k!='key'})
    exclusive_json(root/'ledger-before.private.json',read(LEDGER));stages=Stages(root/'control/stages');results=[]
    from p6_main_budget import MainLedger
    for target in plan['targets']:
        name=target['cell'];original=old/name
        before=inventory(original)
        if digest(before)!=target['inventory_sha256']:raise ValueError('Checkpoint changed')
        cell=target['cell_descriptor'];taskrow=next(t for t in plan['main_manifest']['tasks'] if t['task_id']==cell['task_id'])
        task_payload={'task':taskrow,'manifest':plan['main_manifest'],'budget':payload['budget']}
        if taskrow['family']=='scientific':
            sys.path.insert(0,'/opt/workbench/benchmark/envs/science-tms-v1/lib/python3.12/site-packages')
            import p6_science_main_linux as science
            task=science.task(task_payload);tester=science.test
        else:task=main.public_task(task_payload);tester=main.public_test
        limit=target['limits'];shared.ACTIVE.clear();shared.ACTIVE.update(root=root,task=task,payload=task_payload,
            ledger=MainLedger(LEDGER,payload['budget']),key='',deadline=time.monotonic()+limit['role_seconds_remaining'],
            generation_seconds=limit['authorized_role_seconds'],active_seconds=limit['authorized_role_seconds'],
            workers={},main_phase=True,defer_hidden=True,fixture_url=None)
        shared.LEDGER_PATH=LEDGER;shared.test_source=tester
        descriptor,_=main.job(name,'pi');dest=Path(descriptor['root']);work=Path(descriptor['work'])
        validate_source_links(original/'code')
        # Full byte-preserved program/Git checkpoint; no HOME, global auth or peers.
        copy_checkpoint(original/'code',work)
        checkpoint=dest/'prior-session.private.jsonl';shutil.copyfile(target['session_file'],checkpoint)
        if sha(checkpoint)!=target['session_sha256']:raise ValueError('Official session copy changed')
        recovery={**limit,'authorization':AUTH,'prior_consecutive_failures':1,'session_file':str(checkpoint),
                  'scope':target['scope'],'original_cell':str(original),'kind':'OFFICIAL_PI_SESSION_FORK_AND_WORKSPACE_CHECKPOINT'}
        prompt=('Continue only the unfinished work after a provider overload. Your completed files and tool history are preserved. '
                'The current work directory is '+str(work)+'. Use it for any paths from the old workspace. '
                'Do not repeat completed work. Commit a clean final result in this worktree and summarize briefly.')
        worker=stages.run(name+'-model',lambda:execute(dest,work,cell['profile'],cell['provider'],payload['budget'],prompt,
            limit['role_seconds_remaining'],Path(__file__).with_name('pi_session.mjs'),key=payload.get('key'),
            prefix=Path(task['prefix']),public_reads=descriptor['public_read_paths'],gpu=task.get('gpu_coding',False),
            denied=descriptor['denied_paths'],recovery=recovery))
        shared.ACTIVE['workers'][name]=worker
        candidate=stages.run(name+'-public',lambda:shared.candidate(name,worker))
        exclusive_json(dest/'frozen-program.json',{'head_commit':candidate.get('head_commit'),
            'candidate_sha256':digest(candidate),'private_results_seen':False,'original_cell':name,'recovery_plan_sha256':expected})
        def accept():
            try:return tester(work,True)
            except ValueError as e:
                return {'verdict':'INDETERMINATE' if 'review' in str(e).lower() else 'FAIL','error_type':type(e).__name__,'reason':str(e)[:500]}
        acceptance=stages.run(name+'-acceptance',accept) if worker['status']=='COMPLETED' and candidate['verdict']=='PASS' else {'verdict':'NOT_RUN'}
        if inventory(original)!=before:raise ValueError('Original failed checkpoint changed during recovery')
        row={'cell':cell,'original_result_sha256':target['result_sha256'],'original_outcome':read(original/'result.json')['outcome'],
             'outcome':acceptance['verdict'] if worker['status']=='COMPLETED' and candidate['verdict']=='PASS' else worker['status'] if worker['status']!='COMPLETED' else 'FAIL',
             'worker_status':worker['status'],'candidate_verdict':candidate['verdict'],'acceptance':acceptance,
             'head_commit':candidate.get('head_commit'),'recovery_seconds':worker['wall_seconds'],
             'original_seconds':limit['prior_role_seconds'],'segment_sdk_dispatches':worker['sdk_dispatches'],
             'original_sdk_dispatches':limit['prior_sdk_dispatches'],'usage':worker['summary'].get('usage'),
             'scope':target['scope'],'original_checkpoint_unchanged':True,'recovery_kind':recovery['kind']}
        exclusive_json(dest/'result.json',row);results.append(row)
        exclusive_json(root/('progress-'+str(len(results)).zfill(2)+'.json'),{'completed_cells':len(results),'last':row})
    exclusive_json(root/'ledger-after.private.json',read(LEDGER))
    receipt={'status':'OVERLOAD_CONTINUATIONS_COMPLETED','results':results,'original_run':ORIGINAL,
             'recovery_plan_sha256':expected,'failed_originals_preserved':True,'completed_original_cells_replayed':0}
    exclusive_json(root/'receipt.json',receipt)
    return {'status':receipt['status'],'root':str(root),'results':[{k:v[k] for k in ('cell','outcome')} for v in results]}

if __name__=='__main__':
    protect_memory()
    if os.getuid()==0:raise RuntimeError('Non-root only')
    payload=json.load(sys.stdin)
    for p,h in payload['source_sha256'].items():
        if sha(p)!=h:raise ValueError('Recovery source changed')
    try:print(json.dumps({'controls':controls,'intake':intake,'recover':recover}[payload['mode']](payload)),flush=True)
    except Exception as e:
        import traceback
        root=RUNS/payload['run_id']
        if root.exists() and not (root/'failure.json').exists():exclusive_json(root/'failure.json',{'status':'INFRA_FAIL','error_type':type(e).__name__,'traceback':traceback.format_exc(),'automatic_whole_cell_replay':False})
        raise
