"""Schedule unstarted cells with the exact frozen Pi executor, without failed-cell replay."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

from pi_full_continue_policy import remaining_cells


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(payload):
    plan=payload['continuation_plan'];body=dict(plan);expected=body.pop('continuation_sha256')
    sys.path.insert(0,plan['original_controller'])
    import pi_full_main_linux as core
    if core.digest(body)!=expected:raise ValueError('Continuation plan changed')
    for path,h in {**plan['successor_sources'],**plan['retained_sha256']}.items():
        if sha(path)!=h:raise ValueError('Pinned continuation/original evidence changed: '+path)
    original=plan['original_payload'];core.validate_bindings(original);control=core.require_controls(original)
    receipt=read(plan['original_root']+'/receipt.json')
    if remaining_cells(original['plan'],receipt['results'])!=plan['remaining_cells']:
        raise ValueError('Unstarted cell set differs from original prefix')
    if core.digest(receipt['results'])!=plan['retained_results_sha256']:raise ValueError('Retained results changed')
    # A partial model stage must never be silently reclassified as unstarted.
    for c in plan['remaining_cells']:
        name=c['task_id']+'-'+c['profile']+'-'+c['provider']
        if (Path(plan['original_root'])/name).exists():raise ValueError('Uncertain or existing cell cannot be replayed')
    legacy=read(plan['ledger_archive']);current=read(core.pi.LEDGER)
    if current['requests'][:len(legacy['requests'])]!=legacy['requests'] or current['codex_turns'][:len(legacy['codex_turns'])]!=legacy['codex_turns']:
        raise ValueError('Old cumulative rows changed')
    return core,control


def controls(payload):
    core,control=bind(payload);core.pi.quiet();plan=payload['continuation_plan']
    value={'status':'PASS_UNSTARTED_ONLY_CONTINUATION_CONTROLS','new_model_calls':0,'retained_cells':plan['retained_cells'],
           'remaining_cells':len(plan['remaining_cells']),'continuation_sha256':plan['continuation_sha256'],
           'unchanged_executor_controls':control,'ledger_sha256':sha(core.pi.LEDGER)}
    core.exclusive(Path(plan['controls_receipt']),value);return value


def compare(payload):
    core,control=bind(payload);plan=payload['continuation_plan'];core.pi.quiet()
    gate=read(plan['controls_receipt'])
    if gate['status']!='PASS_UNSTARTED_ONLY_CONTINUATION_CONTROLS' or gate['continuation_sha256']!=plan['continuation_sha256']:
        raise ValueError('Actual zero-model continuation controls required')
    root=core.pi.RUNS/payload['run_id'];root.mkdir(parents=True)
    core.exclusive(root/'continuation-plan.json',plan);core.exclusive(root/'plan.json',plan['original_payload']['plan'])
    (root/'control').mkdir();(root/'control/canary').write_text('controller only')
    core.exclusive(root/'ledger-before.private.json',read(core.pi.LEDGER))
    journal=core.Journal(root/'control/stages');results=[];status='FULL_MAIN_COMPLETED'
    original={**plan['original_payload'],'run_id':payload['run_id'],'key':payload['key']}
    for index,cell in enumerate(plan['remaining_cells']):
        if not core.budget_available(read(core.pi.LEDGER)):status='CUMULATIVE_BUDGET_STOP';break
        name=cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
        row=core.run_cell(root,original,cell,journal)
        core.exclusive(root/'control/stages'/(name+'-cell.completed.json'),{'stage':name+'-cell','value':row,'value_sha256':core.digest(row)})
        results.append(row);core.exclusive(root/('progress-'+str(index+1).zfill(3)+'.json'),{'completed_new_cells':len(results),'last':row})
        if row['worker_status'] in ('INFRA_FAIL','INFRA_RETRY_PENDING'):status='INFRASTRUCTURE_RECONCILIATION_REQUIRED';break
    receipt={'status':status,'results':results,'completed_new_cells':len(results),'total_new_cells':len(plan['remaining_cells']),
             'prior_completed_cells':plan['retained_cells'],'original_root':plan['original_root'],
             'continuation_sha256':plan['continuation_sha256'],'old_cells_replayed':0,'failed_cell_replayed':False,
             'api_cash_actual':'unavailable','scientific_review_required':True,'external_release_authorized':False}
    core.exclusive(root/'receipt.json',receipt);return {k:v for k,v in receipt.items() if k!='results'}


if __name__=='__main__':
    payload=json.load(sys.stdin);core,_=bind(payload);core.pi.protect_memory()
    if os.getuid()==0:raise RuntimeError('Non-root local WSL required')
    with (core.pi.BASE/'full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:print(json.dumps(controls(payload) if payload['mode']=='controls' else compare(payload)),flush=True)
        except Exception as error:
            if payload['mode']!='controls':
                root=core.pi.RUNS/payload['run_id'];root.mkdir(parents=True,exist_ok=True)
                core.exclusive(root/('failure-'+str(time.time_ns())+'.json'),{'status':'INFRA_FAIL','error_type':type(error).__name__,'traceback':traceback.format_exc(),'automatic_replay':False})
            raise
