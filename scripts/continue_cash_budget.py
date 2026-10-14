"""Keep old PC acceptance/sensitivity intact; then activate the approved USD200 ceiling.

This local supplementary supervisor calls the existing restart controller, never
implements agent tools. Every child console is hidden. No completed task is replayed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from p6_boot_recovery import atomic,Journal,singleton,SupervisorAlreadyRunning,validate_sources,background_process_options

def sha(raw):return hashlib.sha256(raw).hexdigest()

def boundary_ready(state):
    """Only the original PC pair can unlock the prospective cash cohort."""
    if state.get('status') not in ('ALL_COMPLETED','FINISHED_WITH_PENDING_INTERRUPTED'):
        return False
    receipts=state.get('completed_receipts',{})
    return (sum(name.startswith('p6-main-execute-SCI-PC-ALM-') for name in receipts)==1 and
            sum(name.startswith('p6-main-sensitivity-SCI-PC-ALM-') for name in receipts)==1)

def check_gate(value,expected):
    if (value.get('commit')!=expected or value.get('checks')!={'integrity':'SUCCESS','secrets':'SUCCESS','linux-budget':'SUCCESS'}):
        raise ValueError('Exact cash-extension CI gate is incomplete')

def bound_config(project,path,expected):
    file=Path(path).resolve()
    if not file.is_relative_to(project/'.local-workbench') or sha(file.read_bytes())!=expected:
        raise ValueError('Handover configuration changed or escaped project')
    return json.loads(file.read_bytes())

def supervisor_once(config):
    folder=Path(config).parent
    result=subprocess.run([sys.executable,'-B',str(folder/'p6_boot_recovery.py'),'supervise','--config',str(config),'--execute','--once'],
        capture_output=True,timeout=210,**background_process_options())
    if result.returncode:raise RuntimeError('Frozen cohort supervisor refused; no task retry')
    return json.loads((folder/'state.private.json').read_bytes())

def activate(config,old_state):
    project=Path(config['project']);future=json.loads(Path(config['future_config']).read_bytes())
    target=Path(future['project'])
    validate_sources(future)
    check_gate(json.loads((project/config['ci_gate']['receipt']).read_bytes()),config['ci_gate']['commit'])
    # Preserve every old receipt, including failures, in the bridge provenance.
    boundaries=[]
    for name,expected in old_state['completed_receipts'].items():
        boundaries.append(dict(root='/opt/workbench/benchmark/private/main-runs/'+name,sha256=expected,
            status='FULL_TOOL_TRACE_SENSITIVITY_COMPLETED' if name.startswith('p6-main-sensitivity-') else 'MAIN_TASK_COMPLETED'))
    old=json.loads((project/'configs/budget-p6-main-v5-network-approved.json').read_bytes())
    new=json.loads((target/'configs/budget-p6-main-v6-cash200-approved.json').read_bytes())
    modules={}
    for name in ('p6_main_budget.py','p1_budget.py','p6_output_policy.py','p6_network_policy.py'):
        code=(target/'scripts'/name).read_text(encoding='utf-8');modules[name]=dict(code=code,sha256=sha(code.encode()))
    code=Path(__file__).with_name('cash_amend_linux.py').read_text(encoding='utf-8')
    result=subprocess.run(['wsl.exe','-d','EnhancedHumanizer-P0','-u','workbench','--cd','/opt/workbench','--exec',
            '/opt/workbench/.venv-linux/bin/python','-B','-c',code],
        input=json.dumps(dict(old=old,new=new,modules=modules,boundaries=boundaries)).encode(),capture_output=True,timeout=90,
        env=dict(os.environ,WSLENV='',WSL_UTF8='1'),**background_process_options())
    if result.returncode:raise RuntimeError('Idle cash handover refused; original evidence retained')
    receipt=json.loads(result.stdout)
    if receipt['aggregate_caps']!=dict(requests=10000,codex_turns=None,cash_nano=200_000_000_000) or receipt['model_calls']!=0:
        raise ValueError('Cash handover returned unexpected controls')
    return receipt

def supervise(path,once=False):
    path=Path(path).resolve();config=json.loads(path.read_bytes());project=Path(config['project']).resolve();folder=path.parent
    if not folder.is_relative_to(project/'.local-workbench') or config['authorization']!='USER_APPROVED_2026-10-13_CUMULATIVE_USD200':
        raise ValueError('Explicit local cash handover authorization required')
    for name,expected in config['files'].items():
        if sha((folder/name).read_bytes())!=expected:raise ValueError('Pinned bridge executable changed')
    old=bound_config(project,config['old_config'],config['old_config_sha256'])
    future=bound_config(project,config['future_config'],config['future_config_sha256'])
    if future['tasks']!=['SCI-STROKE','SCI-EGL','SCI-GRANGER-GPU'] or old['tasks']!=config['old_tasks'] or any(t in future['tasks'] for t in old['tasks']):
        raise ValueError('Prospective cohorts must not replay or overlap tasks')
    check_gate(json.loads((project/config['ci_gate']['receipt']).read_bytes()),config['ci_gate']['commit'])
    with singleton(folder/'bridge.lock'):
        journal=Journal(folder/'events.private.ndjson');state_path=folder/'state.private.json'
        state=json.loads(state_path.read_bytes()) if state_path.exists() else dict(phase='OLD_COHORT')
        expected=sha(path.read_bytes())
        if state.get('config_sha256',expected)!=expected:raise ValueError('Cash bridge state/config mismatch')
        state['config_sha256']=expected
        while json.loads((folder/'enabled.private.json').read_bytes())['enabled']:
            try:
                if state['phase']=='OLD_COHORT':
                    old_state=supervisor_once(config['old_config'])
                    state.update(status=old_state['status'],ledger=old_state.get('ledger'),old_pending=old_state.get('decision',{}).get('pending',[]))
                    if boundary_ready(old_state):
                        state['phase']='AMEND_IDLE';journal.append('OLD_PC_BOUNDARY_COMPLETE',{'completed_receipts':old_state['completed_receipts']})
                        atomic(state_path,state)
                if state['phase']=='AMEND_IDLE':
                    old_state=json.loads((Path(config['old_config']).parent/'state.private.json').read_bytes())
                    if not boundary_ready(old_state):raise ValueError('Old PC boundary changed')
                    receipt=activate(config,old_state)
                    atomic(folder/'cash-activation.private.json',receipt)
                    journal.append('CASH200_ACTIVATED_WITHOUT_RESET',receipt)
                    state.update(phase='FUTURE_COHORT',status='CASH200_ACTIVE',activation=receipt)
                    # Durable phase switch precedes any possible new provider request.
                    atomic(state_path,state)
                if state['phase']=='FUTURE_COHORT':
                    future_state=supervisor_once(config['future_config'])
                    state.update(status=future_state['status'],ledger=future_state.get('ledger'),future_pending=future_state.get('decision',{}).get('pending',[]))
                    if state['status'] in ('ALL_COMPLETED','FINISHED_WITH_PENDING_INTERRUPTED'):
                        state['phase']='FINISHED';journal.append('PROSPECTIVE_COHORT_FINISHED',{'status':state['status'],'old_pending':state.get('old_pending',[]),'future_pending':state.get('future_pending',[])})
                state.update(last_probe_unix=time.time());state.pop('error_type',None);atomic(state_path,state)
                if once or state['phase']=='FINISHED':return state
            except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
                journal.append('HANDOVER_BLOCKED',{'error_type':type(error).__name__,'message':str(error)[:180]})
                state.update(status='HANDOVER_BLOCKED',error_type=type(error).__name__,last_probe_unix=time.time());atomic(state_path,state)
                if once:raise
            time.sleep(30)
    return dict(status='DISABLED')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--once',action='store_true');args=p.parse_args()
    try:print(json.dumps(supervise(args.config,args.once)))
    except SupervisorAlreadyRunning:print(json.dumps({'status':'ANOTHER_BRIDGE_OWNS_LOCK'}))
