"""Zero-model P3 controls: real namespace watchdog and native Humanize pause/resume, labelled mocks."""

from datetime import timedelta
import json
import os
from pathlib import Path
import time

from p1_broker import protect_memory
from p2_candidates import BASE,digest,exclusive_json
from p3_contracts import read_json
import p3_runtime_linux as runtime


def main():
    protect_memory();started=time.perf_counter();stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    ledger=BASE/'state/p3-budget/ledger.json';before=digest(ledger.read_bytes()) if ledger.exists() else 'ABSENT'
    root=BASE/'runs'/('p3-control-watchdog-'+stamp)
    for name in ('control','inputs','results','roles'):(root/name).mkdir(parents=True,exist_ok=True)
    exclusive_json(root/'control/run-contract.json',{'kind':'OFFLINE_CONTROL'})
    runtime.CONTEXT.update(deadline=time.monotonic()+2,pool_path=str(BASE/'runs/p2-control-mixed-20261010T124617Z/frozen-pool.json'))
    runtime.STOP.clear()
    timed=runtime.role_run(root,'sleep','reviewer',{'kind':'ZERO_MODEL_CONTROL'},'No model call',
                           offline_control='sleep',role_seconds=1)
    assert timed['status']=='TIMEOUT' and timed['wall_seconds']<8
    repeated=runtime.role_run(root,'sleep','reviewer',{'kind':'ZERO_MODEL_CONTROL'},'No replay',offline_control='sleep')
    assert repeated['status']=='TIMEOUT'
    runtime.CONTEXT['deadline']=time.monotonic()+30
    probes=[]
    for role in ('verifier','reviewer','builder'):
        tested=runtime.role_run(root,'fence-'+role,role,{'kind':'ZERO_MODEL_FENCE_CONTROL'},'No model call',offline_control='fence')
        assert tested['status']=='COMPLETED'
        probes.append(read_json(Path(tested['root'])/'isolation.json'))
    # Exercise the genuine Humanize resumable Flow with a clearly mocked stage transport.
    root2=BASE/'runs'/('p3-control-resume-'+stamp)
    for name in ('control','inputs','results','roles'):(root2/name).mkdir(parents=True,exist_ok=True)
    contract_hash=digest({'kind':'MOCK_STAGE_TRANSPORT_ONLY'})
    os.environ['HUMANIZE_HOME']=str(BASE/'state'/root2.name/'humanize')
    calls=[];original=runtime.stage
    def fake_stage(target,name):
        calls.append(name)
        value={'kind':'MOCK_STAGE_TRANSPORT_ONLY','stage':name,'model_requests':0}
        value['record_sha256']=digest(value);exclusive_json(Path(target)/'results'/(name+'.json'),value)
        return value
    runtime.stage=fake_stage
    from hmz.sdk import Hmz
    try:
        def build(resume=False):
            return Hmz(workspace=root2).run('/opt/workbench/source/flows/synthesis_loop','Native pause/resume with mock stage transport',agents={},
                params={'run_root':str(root2),'contract_hash':contract_hash,'pause_after':'reviewer' if not resume else ''},
                budget={'duration':timedelta(seconds=30),'graceful':False},resume=resume)
        run=build();run.start();deadline=time.monotonic()+20
        while run.running and not list((root2/'control').glob('pause-*.json')):
            if time.monotonic()>deadline:raise RuntimeError('Native pause not reached')
            time.sleep(.05)
        assert run.running;run.stop();assert run.wait(10)
        before_resume=list(calls);assert before_resume==['verifier_input','reviewer']
        resumed=build(str(run.epic));out=resumed.run()
        assert calls==list(runtime.STAGES) and out['resumed'] and out['next_step']==7
        native={'pause_epic':str(run.epic),'resume_epic':str(resumed.epic),'before_resume':before_resume,
                'all_mock_stage_calls':calls,'completed_stages_replayed':0,'kind':'MOCK_STAGE_TRANSPORT_ONLY'}
    finally:runtime.stage=original
    after=digest(ledger.read_bytes()) if ledger.exists() else 'ABSENT';assert before==after
    record={'verdict':'PASS','kind':'ZERO_MODEL_P3_CONTROLS','model_requests_added':0,'watchdog':timed,
            'native_humanize_pause_resume':native,'fence_regression':probes,'real_ledger_before':before,'real_ledger_after':after,
            'elapsed_seconds':time.perf_counter()-started}
    exclusive_json(BASE/'evidence'/('p3-controls-'+stamp+'.json'),record)
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
