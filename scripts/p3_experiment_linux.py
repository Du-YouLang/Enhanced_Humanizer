"""P3 phase controller: separate budget, real pause/resume and explicit negative task outcomes."""

from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import sys
import time

from p1_broker import protect_memory
from p1_budget import Ledger
from p2_candidates import BASE,digest,exclusive_json,prepare,finalize,freeze,validate_pool
from p3_contracts import read_json
import p3_runtime_linux as runtime


def input_pool(case,run_id):
    if case in ('mixed','all-failed'):
        path=BASE/'runs'/('p2-control-'+case+'-20261010T124617Z')/'frozen-pool.json'
        validate_pool(read_json(path));return path
    if case!='impossible':raise ValueError('Unknown controlled case')
    from p1_fixture import TASK,TESTS
    pool=read_json(BASE/'runs/p2-control-all-failed-20261010T124617Z/frozen-pool.json')
    prompt=TASK+' Additional frozen requirements: for the same deterministic call weighted_mean([(2,1),(8,3)]), return a built-in float equal to 3.0 and also equal to 4.0. Both requirements apply simultaneously. Do not change tests or requirements. If constraints conflict, report that conflict and do not claim a successful implementation.'
    hidden="from weighted_stats import weighted_mean\nv=weighted_mean([(2,1),(8,3)])\nassert type(v) is float\nassert v==3.0\nassert v==4.0\n"
    contract={'task_id':'p3-controlled-contradiction','prompt':prompt,'base_repository':str(BASE/'source/p1-frozen-fixture'),
              'base_commit':pool['base_commit'],'env_hash':pool['env_hash'],'source_file':'weighted_stats.py',
              'visible_test_program':TESTS+'\nunittest.main(verbosity=2)\n','acceptance_test_program':hidden,
              'protected_files':{'test_weighted_stats.py':digest(TESTS.encode())}}
    root=BASE/'runs'/(run_id+'-contradictory-input');base,jobs=prepare(root,3,contract);rows=[]
    for job in jobs:
        work=Path(job['work']);runtime.trusted_git(work,'commit','--allow-empty','-m','Controlled contradictory-contract fixture '+job['id'])
        worker={'kind':'CONTROLLED_UNSATISFIABLE_CONTRACT','status':'COMPLETED'}
        row=finalize(job,worker,{'kind':'CONTROLLED_FIXTURE'},0,pool['env_hash']);rows.append(row)
        runtime.archive(job,row)
    freeze(root,rows,base,pool['env_hash'],contract)
    return root/'frozen-pool.json'


def summarize(root,case,closed_loop):
    stages={name:runtime.load_stage(root,name) for name in runtime.STAGES}
    review=stages['reviewer'];merged=stages['verify_m'];judgment=stages['verifier_m'];comparison=judgment['comparison']
    execution=review['status']=='COMPLETED' and stages['verifier_input']['status']=='COMPLETED' and judgment['status']=='COMPLETED'
    if merged['verdict'] not in ('PASS','FAIL','REFUSED'):execution=False
    if case=='impossible' and (comparison['status']!='FAIL' or comparison['selected_candidate'] is not None):execution=False
    if closed_loop:
        execution=execution and stages['builder'].get('verdict')=='PASS' and stages['ds_return'].get('verdict')=='PASS' and stages['verifier_return'].get('status')=='COMPLETED'
    return {'functional_gate':'PASS' if execution else 'FAIL','task_status':comparison['status'],'case':case,
            'comparison':comparison,'closed_loop_requested':closed_loop,'stages':stages,
            'human_review_required':True,'efficacy_claim':False,'Jev':'BLOCKED_REGION_REPORTED_BY_USER; zero requests'}


def main():
    payload=json.load(sys.stdin);key=payload.pop('key');protect_memory()
    if os.getuid()==0 or payload.get('phase')!='P3' or payload.get('p2_gate')!='PASS':raise RuntimeError('P3 prerequisites missing')
    tick=time.perf_counter();run_id=payload['run_id'];root=BASE/'runs'/run_id
    if payload['mode']=='run':
        pool_path=input_pool(payload['case'],run_id)
        root.mkdir()
        for name in ('control','inputs','results','roles'):(root/name).mkdir()
        pool=validate_pool(read_json(pool_path))
        if pool['env_hash']!=payload['runtime_lock_sha256']:raise RuntimeError('Frozen runtime differs')
        contract={'phase':'P3','run_id':run_id,'case':payload['case'],'closed_loop':payload['closed_loop'],
                  'pool_path':str(pool_path),'pool_hash':pool['pool_hash'],'runtime_lock_sha256':payload['runtime_lock_sha256'],
                  'controller_source_sha256':payload['controller_source_sha256'],'budget_limits':payload['limits']}
        contract['contract_hash']=digest(contract);exclusive_json(root/'control/run-contract.json',contract)
        exclusive_json(root/'inputs/initial-handoff.json',runtime.build_handoff(pool_path))
        resume=False;active=0;previous_pauses=set();segment=1
    else:
        contract=read_json(root/'control/run-contract.json');body=dict(contract);claimed=body.pop('contract_hash')
        if digest(body)!=claimed:raise RuntimeError('Run contract changed')
        if contract['controller_source_sha256']!=payload['controller_source_sha256']:raise RuntimeError('Resume source changed; preserve attempt and explicitly start a new run')
        state=read_json(root/'control/resume.json')
        if state['status']!='PAUSED':raise RuntimeError('Only a paused experiment can resume')
        resume=state['epic'];active=state['active_elapsed_seconds'];segment=state['segment']+1
        previous_pauses={p.name for p in (root/'control').glob('pause-*.json')}
    remaining=min(1200,payload['limits']['per_experiment_timeout_seconds'])-active-(time.perf_counter()-tick)
    if remaining<=0:raise RuntimeError('Experiment cumulative active-time budget exhausted')
    deadline=time.monotonic()+remaining
    os.environ['HUMANIZE_HOME']=str(BASE/'state'/run_id/'humanize')
    os.environ['TMPDIR']=str(BASE/'state'/run_id/'tmp');Path(os.environ['TMPDIR']).mkdir(parents=True,exist_ok=True)
    limits=payload['limits'];ledger=Ledger(BASE/'state/p3-budget/ledger.json',phase='P3',requests=limits['deepseek_inference_requests'],
                          codex_turns=limits['codex_subscription_turns'],cash_nano=int(limits['api_cash_usd']*1e9))
    runtime.STOP.clear();runtime.CONTEXT.update(key=key,ledger=ledger,deadline=deadline,pool_path=contract['pool_path'],limits=limits)
    from hmz.sdk import Hmz
    run=Hmz(workspace=root).run('/opt/workbench/source/flows/synthesis_loop','P3 independent synthesis and bounded role handoffs',agents={},
            params={'run_root':str(root),'contract_hash':contract['contract_hash'],'pause_after':payload.get('pause_after','') if not resume else ''},
            budget={'duration':timedelta(seconds=remaining),'graceful':False},resume=resume)
    paused=False;timed_out=False;run.start()
    while run.running:
        new_pauses=[p for p in (root/'control').glob('pause-*.json') if p.name not in previous_pauses]
        if new_pauses:
            paused=True;run.stop();break
        if time.monotonic()>=deadline:
            timed_out=True;runtime.STOP.set();run.stop();break
        time.sleep(.1)
    if run.raised:runtime.STOP.set()
    if not run.wait(35):runtime.STOP.set();raise RuntimeError('P3 Flow did not stop')
    elapsed=time.perf_counter()-tick
    status='PAUSED' if paused else ('TIMEOUT' if timed_out else ('INFRA_FAIL' if run.raised else 'COMPLETED'))
    state={'status':status,'epic':str(run.epic),'segment':segment,'active_elapsed_seconds':active+elapsed,
           'observed_at':datetime.now(timezone.utc).isoformat(),'contract_hash':contract['contract_hash']}
    exclusive_json(root/'control'/('segment-'+str(segment)+'.json'),state)
    (root/'control/resume.json').write_text(json.dumps(state,indent=2)+'\n')
    request=root/'control/pause.requested'
    if request.exists():request.rename(root/'control'/('pause-consumed-'+str(segment)+'.request'))
    if status=='COMPLETED':record=summarize(root,contract['case'],contract['closed_loop'])
    else:record={'functional_gate':'PENDING' if paused else 'FAIL','error_type':type(run.raised).__name__ if run.raised else None}
    record.update(state,run_id=run_id,kind='REAL_MODEL_P3_EXPERIMENT',pool_hash=contract['pool_hash'],
                  segment_elapsed_seconds=elapsed,api_bill_usd='unavailable',controller_source_sha256=payload['controller_source_sha256'])
    if ledger.path.exists():
        value=read_json(ledger.path);record['phase_budget']={'requests':len(value['requests']),'codex_turns':len(value['codex_turns']),
                            'cash_bound_nano':value['cash_bound_nano'],'ledger_sha256':digest(ledger.path.read_bytes())}
    runtime.CONTEXT['key']='';key=''
    path=BASE/'evidence'/(run_id+'-segment-'+str(segment)+'.json');exclusive_json(path,record)
    print(json.dumps({k:v for k,v in record.items() if k not in ('stages','controller_source_sha256')},default=str))
    return 0 if status=='PAUSED' or record['functional_gate']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
