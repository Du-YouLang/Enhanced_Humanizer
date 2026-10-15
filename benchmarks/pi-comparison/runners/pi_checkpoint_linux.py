"""Scoped, source-pinned recovery of PC acceptance followed by unstarted cells."""
import fcntl,hashlib,json,os,sys,time,traceback
from pathlib import Path
from unittest.mock import patch
from pi_checkpoint_policy import AUTHORIZATION,AcceptanceJournal,checkpoint_cells,retained_value,remaining_acceptance_seconds

def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def bind(plan):
    sys.path.insert(0,plan['original_wrapper'])
    import pi_full_continue_linux as previous
    core,_=previous.bind({'continuation_plan':plan['continuation_plan']})
    body=dict(plan);expected=body.pop('recovery_sha256')
    if core.digest(body)!=expected or plan['authorization']!=AUTHORIZATION:raise ValueError('Recovery authorization changed')
    if plan.get('prior_acceptance_debit_seconds')!=1900:raise ValueError('Original acceptance time must not reset')
    for p,h in {**plan['sources'],**plan['evidence_sha256']}.items():
        if sha(p)!=h:raise ValueError('Recovery evidence changed: '+p)
    root=Path(plan['root']);rows=[]
    for cell in plan['continuation_plan']['remaining_cells'][:61]:
        name=cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
        rows.append(retained_value(root/'control/stages'/(name+'-cell.completed.json'),name+'-cell'))
    checkpoint_cells(plan['continuation_plan'],rows,plan['cell'])
    if core.digest(rows)!=plan['completed_results_sha256']:raise ValueError('Completed61 changed')
    old=read(plan['ledger_archive']);current=read(core.pi.LEDGER)
    if any(current[k][:len(old[k])]!=old[k] for k in ('requests','codex_turns')):raise ValueError('Ledger prefix changed')
    target=root/'SCI-PC-ALM-P0-deepseek'
    worker=retained_value(root/'control/stages/SCI-PC-ALM-P0-deepseek-model.completed.json','SCI-PC-ALM-P0-deepseek-model')
    candidate=retained_value(root/'control/stages/SCI-PC-ALM-P0-deepseek-public.completed.json','SCI-PC-ALM-P0-deepseek-public')
    frozen=read(target/'frozen-program.json')
    if worker['status']!='COMPLETED' or candidate['verdict']!='PASS':raise ValueError('Completed model and public PASS required')
    core.verify_frozen(Path(worker['work']),candidate,frozen)
    if (root/'receipt.json').exists():raise ValueError('Original batch is already closed')
    if plan['continuation_plan']['remaining_cells'][62:]!=plan['unstarted_cells']:raise ValueError('Unstarted23 changed')
    for c in plan['unstarted_cells']:
        if (root/(c['task_id']+'-'+c['profile']+'-'+c['provider'])).exists():raise ValueError('Unstarted cell already exists')
    return core,rows


def cached_worker():
    # This runs only inside the unchanged science sandbox and uses the original
    # candidate source verbatim. No parent imports or repairs candidate code.
    return '''import json,runpy,subprocess,sys,time
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4]);tick=time.perf_counter()
sys.path.insert(0,str(inputs));from pi_checkpoint_policy import cached_training_runner
cache=json.loads((inputs/'recovery-cache.json').read_text());events=[]
original=subprocess.run
subprocess.run=cached_training_runner(original,cache,output/'result',events)
sys.path.insert(0,str(source));sys.argv=[str(source/'run_benchmark.py'),'--data-dir',str(inputs),'--output-dir',str(output/'result')]
try:
 runpy.run_path(str(source/'run_benchmark.py'),run_name='__main__')
except SystemExit as e:
 if e.code not in (0,None):raise
(output/'controller.json').write_text(json.dumps({'wall_seconds':time.perf_counter()-tick,'reused_completed_trainings':events,'recovery':'UNMODIFIED_CANDIDATE_WITH_VALIDATED_CACHED_TRAININGS'}))
'''


def execute(payload):
    plan=payload['plan'];core,rows=bind(plan);core.pi.protect_memory()
    if os.getuid()==0:raise RuntimeError('Non-root project WSL required')
    with (core.pi.BASE/'full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);core.pi.quiet()
        if payload['mode']=='controls':
            return {'status':'PASS_CHECKPOINT_RECOVERY_BINDINGS','completed_reused':61,'unstarted':23,'model_calls':0,'ledger_sha256':sha(core.pi.LEDGER)}
        if payload['mode']!='execute':raise ValueError('Unknown recovery mode')
        root=Path(plan['root']);recovery=Path(plan['recovery_root']);recovery.mkdir()
        core.exclusive(recovery/'plan.json',plan)
        core.exclusive(recovery/'started.json',{'authorization':AUTHORIZATION,'provider_call_required_for_acceptance':False})
        name='SCI-PC-ALM-P0-deepseek';journal=AcceptanceJournal(root/'control/stages',recovery/'stages',name)
        original={**plan['continuation_plan']['original_payload'],'run_id':root.name,'key':payload['key']}
        import p6_pc_grader as grader
        real_execute=grader.execute;real_grade=grader.grade;counter=[0]
        def bounded_grade(*args,**kwargs):
            kwargs['timeout']=remaining_acceptance_seconds(plan['prior_acceptance_debit_seconds'])
            return real_grade(*args,**kwargs)
        def resumed_execute(source,prefix,program,**kwargs):
            counter[0]+=1
            if counter[0]!=1:return real_execute(source,prefix,program,**kwargs)
            inputs=dict(kwargs.get('inputs',{}))
            inputs['recovery-cache.json']=Path(plan['cache_file']).read_bytes()
            inputs['pi_checkpoint_policy.py']=Path(__file__).with_name('pi_checkpoint_policy.py').read_bytes()
            inputs['pi_full_protocol.py']=Path(core.__file__).with_name('pi_full_protocol.py').read_bytes()
            kwargs['inputs']=inputs
            return real_execute(source,prefix,cached_worker(),**kwargs)
        before=sha(core.pi.LEDGER)
        with patch.object(core.pi,'execute',side_effect=RuntimeError('Model replay forbidden during acceptance recovery')):
            with patch.object(grader,'execute',side_effect=resumed_execute):
                with patch.object(grader,'grade',side_effect=bounded_grade):
                    row=core.run_cell(root,original,plan['cell'],journal)
        if sha(core.pi.LEDGER)!=before:raise ValueError('Acceptance recovery changed model ledger')
        # Preserve the interrupted started marker; append the independently
        # audited completion and never replace an existing raw result.
        acceptance=retained_value(recovery/'stages'/(name+'-acceptance.completed.json'),name+'-acceptance')
        core.exclusive(root/'control/stages'/(name+'-acceptance.completed.json'),{'stage':name+'-acceptance','value':acceptance,'value_sha256':core.digest(acceptance),'recovery_receipt':str(recovery)})
        core.exclusive(root/'control/stages'/(name+'-cell.completed.json'),{'stage':name+'-cell','value':row,'value_sha256':core.digest(row)})
        rows.append(row)
        core.exclusive(root/'progress-062.json',{'completed_new_cells':62,'last':row,'acceptance_recovered':True})
        core.exclusive(recovery/'acceptance-receipt.json',{'status':'ACCEPTANCE_RECOVERED','result':row,'old_model_replayed':False,'ledger_sha256_before':before,'ledger_sha256_after':sha(core.pi.LEDGER),'model_calls':0})
        status='FULL_MAIN_COMPLETED'
        ordinary=core.Journal(root/'control/stages')
        for cell in plan['unstarted_cells']:
            if not core.budget_available(read(core.pi.LEDGER)):status='CUMULATIVE_BUDGET_STOP';break
            name=cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
            row=core.run_cell(root,original,cell,ordinary)
            core.exclusive(root/'control/stages'/(name+'-cell.completed.json'),{'stage':name+'-cell','value':row,'value_sha256':core.digest(row)})
            rows.append(row);core.exclusive(root/('progress-'+str(len(rows)).zfill(3)+'.json'),{'completed_new_cells':len(rows),'last':row})
            if row['worker_status'] in ('INFRA_FAIL','INFRA_RETRY_PENDING'):status='INFRASTRUCTURE_RECONCILIATION_REQUIRED';break
        for p,h in plan['evidence_sha256'].items():
            if sha(p)!=h:raise ValueError('Preserved original evidence changed')
        receipt={'status':status,'results':rows,'completed_new_cells':len(rows),'total_new_cells':85,'prior_completed_cells':27,
                 'original_root':plan['continuation_plan']['original_root'],'old_cells_replayed':0,'failed_cell_replayed':False,
                 'acceptance_recovery_receipt':str(recovery/'acceptance-receipt.json'),'scientific_review_required':True,
                 'external_release_authorized':False,'api_cash_actual':'unavailable'}
        core.exclusive(root/'receipt.json',receipt)
        return {k:v for k,v in receipt.items() if k!='results'}


if __name__=='__main__':
    payload=json.load(sys.stdin)
    try:print(json.dumps(execute(payload)),flush=True)
    except Exception:
        if payload['mode']=='execute':
            r=Path(payload['plan']['recovery_root']);r.mkdir(parents=True,exist_ok=True)
            from pi_full_protocol import exclusive
            exclusive(r/('failure-'+str(time.time_ns())+'.json'),{'traceback':traceback.format_exc(),'automatic_replay':False})
        raise
