"""Genuine Humanize checkpoints/fences with explicitly mocked stage transport; zero models."""
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import time
from p1_broker import protect_memory
from p2_candidates import BASE,digest,exclusive_json
from p3_contracts import read_json
import p3_runtime_linux as runtime
import p5_runtime_linux as stages

def main():
    protect_memory();tick=time.perf_counter();stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+secrets.token_hex(3)
    ledger=BASE/'state/p5-budget/ledger.json';before=digest(ledger.read_bytes())
    original=stages.stage;reports=[]
    try:
        for case in ('auto_resume','human_boundary','tamper'):
            root=BASE/'runs'/('p5-controls-'+stamp+'-'+case)
            for name in ('control','results','inputs','roles'):(root/name).mkdir(parents=True,exist_ok=True)
            os.environ['HUMANIZE_HOME']=str(BASE/'state'/root.name/'humanize')
            calls=[];contract_hash=digest({'kind':'MOCK_STAGE_TRANSPORT_ONLY','case':case})
            def fake(target,name):
                calls.append(name)
                value={'stage':name,'kind':'MOCK_STAGE_TRANSPORT_ONLY','model_requests':0,'status':'COMPLETED'}
                value['record_sha256']=digest(value);exclusive_json(Path(target)/'results'/(name+'.json'),value)
                return value
            stages.stage=fake
            if case=='human_boundary':(root/'control/pause.requested').write_text('OFFLINE fixture boundary request')
            def build(resume=False):
                return Hmz(workspace=root).run('/opt/workbench/source/flows/workbench_loop','Explicitly mocked stage transport; never model evidence',agents={},
                    params={'run_root':str(root),'contract_hash':contract_hash,'pause_after':'candidates' if not resume and case!='human_boundary' else ''},
                    budget={'duration':timedelta(seconds=25),'graceful':False},resume=resume)
            from hmz.sdk import Hmz
            run=build();run.start();deadline=time.monotonic()+10
            while run.running and not list((root/'control').glob('pause-*.json')):
                if time.monotonic()>deadline:raise RuntimeError('Native pause did not checkpoint')
                time.sleep(.03)
            assert run.running and calls==['candidates'];run.stop();assert run.wait(10)
            if case=='human_boundary':(root/'control/pause.requested').rename(root/'control/pause.consumed')
            if case=='tamper':
                file=root/'results/candidates.json';value=read_json(file);value['record_sha256']='f'*64;file.write_text(json.dumps(value))
            resumed=build(str(run.epic));resumed.start();assert resumed.wait(15)
            if case=='tamper':assert resumed.raised and calls==['candidates']
            else:assert not resumed.raised and calls==list(stages.STAGES) and resumed.result['resumed']
            reports.append({'case':case,'stage_calls':calls,'completed_stages_replayed':0,'tamper_denied':bool(resumed.raised),
                            'pause_epic':str(run.epic),'resume_epic':str(resumed.epic),'kind':'MOCK_STAGE_TRANSPORT_ONLY'})
    finally:stages.stage=original
    root=BASE/'runs'/('p5-controls-'+stamp+'-roles')
    for name in ('control','results','inputs','roles'):(root/name).mkdir(parents=True,exist_ok=True)
    exclusive_json(root/'control/run-contract.json',{'kind':'ZERO_MODEL_FENCE_FIXTURE','hidden_answer':'Harmless canary, not task gold data'})
    runtime.CONTEXT.update(deadline=time.monotonic()+20,phase='P5',pool_path=str(BASE/'runs/p5-20261010155100-13a14339-pool/frozen-pool.json'))
    from p3_contracts import judge_pool,with_initial_judgment
    from p2_judges import J0
    first=stages.frozen_handoff(root,runtime.CONTEXT['pool_path']);judgment=J0().judge(judge_pool(first))
    resumed_view=stages.frozen_handoff(root,runtime.CONTEXT['pool_path'])
    assert digest(first)==digest(resumed_view)
    assert with_initial_judgment(resumed_view,judgment)['judgments']==[judgment]
    runtime.STOP.clear();fences=[]
    for role in ('verifier','reviewer','builder'):
        tested=runtime.role_run(root,'fence-'+role,role,{'kind':'ZERO_MODEL_FENCE_CONTROL'},'No model call',offline_control='fence')
        assert tested['status']=='COMPLETED';fences.append(read_json(Path(tested['root'])/'isolation.json'))
    runtime.STOP.set()
    cancelled=runtime.role_run(root,'cancelled','reviewer',{'kind':'ZERO_MODEL_WATCHDOG'},'No model call',offline_control='sleep')
    runtime.STOP.clear();assert cancelled['status']=='CANCELLED' and cancelled['wall_seconds']<8
    import threading
    from p1_budget import Ledger
    from p2_experiment_linux import pool_run
    pool=read_json(runtime.CONTEXT['pool_path']);timer=threading.Timer(1,runtime.STOP.set);timer.start()
    try:
        cancelled_pool=pool_run({'run_id':'p5-controls-'+stamp+'-candidate-cancel','n':1,'concurrency':1,
            'task_contract':pool['contract_manifest'],'runtime_lock_sha256':pool['env_hash'],'offline_control':'sleep',
            'cancel_event':runtime.STOP},'',Ledger(ledger,phase='P5',requests=160,codex_turns=16,cash_nano=5_000_000_000),time.monotonic()+20)
        assert cancelled_pool['flow_stop']['state']=='CANCELLED' and cancelled_pool['verdict']=='CANCELLED'
    finally:timer.cancel();runtime.STOP.clear()
    after=digest(ledger.read_bytes());assert before==after
    value={'verdict':'PASS','kind':'ZERO_MODEL_NATIVE_CONTROLS_NOT_MODEL_RESULTS','native_checkpoints':reports,
           'frozen_public_view_reuse':'PASS_REAL_POOL_J0_ZERO_INFERENCE',
           'fence_regression':fences,'cancellation':cancelled,'candidate_cancellation':cancelled_pool,'ledger_before':before,'ledger_after':after,
           'new_model_requests':0,'new_subscription_turns':0,'api_cash_usd':0,'elapsed_seconds':time.perf_counter()-tick}
    exclusive_json(BASE/'evidence'/('p5-controls-'+stamp+'.json'),value);print(json.dumps(value))

if __name__=='__main__':main()
