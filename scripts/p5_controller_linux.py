"""Protected local execution controller; native Flow checkpoints and phase-specific ledger."""
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import time

from p1_broker import protect_memory
from p1_budget import Ledger
from p2_candidates import BASE,digest,exclusive_json,validate_pool
from p2_contract import validate_contract
from p3_contracts import read_json
import p3_runtime_linux as runtime
import p5_runtime_linux as stages


def main():
    payload=json.load(sys.stdin);key=payload.pop('key');protect_memory()
    if os.getuid()==0 or payload['phase']!='P5' or payload['p4_gate']!='PASS':raise RuntimeError('P5 prerequisites missing')
    root=BASE/'runs'/payload['run_id'];limits=payload['limits'];tick=time.perf_counter()
    if payload['mode']=='start':
        task=validate_contract(payload['task_contract'],payload['runtime_lock_sha256'])
        root.mkdir()
        for folder in ('control','inputs','results','roles'):(root/folder).mkdir()
        contract={'phase':'P5','run_id':root.name,'task_contract':task,'settings':payload['settings'],
                  'source_sha256':payload['source_sha256'],'limits':limits,'parent_node':payload.get('parent_node')}
        contract['contract_hash']=digest(contract);exclusive_json(root/'control/run-contract.json',contract)
        if payload.get('reuse_pool_path'):
            import re
            path=payload['reuse_pool_path']
            if not re.fullmatch('/opt/workbench/runs/p5-[a-z0-9-]+-pool/frozen-pool.json',path):raise ValueError('Unknown frozen pool path')
            pool=validate_pool(read_json(path))
            if pool['contract_manifest']!=task:raise ValueError('Reused candidate contract differs; no silent task change')
            cached={'stage':'candidates','status':'COMPLETED','kind':'REUSED_FROZEN_POOL_ZERO_NEW_GENERATION','pool_path':path,
                    'pool_hash':pool['pool_hash'],'n':len(pool['candidates']),'verdict':pool['failure_report']['status'],
                    'elapsed_stage_seconds':0,'actual_new_model_requests':0}
            cached['record_sha256']=digest(cached);exclusive_json(root/'results/candidates.json',cached)
        resume=False;active=0;segment=1;old_pauses=set()
    else:
        contract=read_json(root/'control/run-contract.json');body=dict(contract);claimed=body.pop('contract_hash')
        if digest(body)!=claimed or contract['source_sha256']!=payload['source_sha256']:raise ValueError('Frozen source/contract changed; preserve attempt and explicitly fork')
        saved=read_json(root/'control/resume.json')
        if saved['status']!='PAUSED':raise ValueError('Only durable PAUSED runs can resume')
        resume=saved['epic'];active=saved['active_elapsed_seconds'];segment=saved['segment']+1
        old_pauses={p.name for p in (root/'control').glob('pause-*.json')}
    remaining=contract['settings']['experiment_seconds']-active
    if remaining<=0:raise RuntimeError('Cumulative active wall-time exhausted')
    deadline=time.monotonic()+remaining
    os.environ['HUMANIZE_HOME']=str(BASE/'state'/root.name/'humanize')
    os.environ['TMPDIR']=str(BASE/'state'/root.name/'tmp');Path(os.environ['TMPDIR']).mkdir(parents=True,exist_ok=True)
    ledger=Ledger(BASE/'state/p5-budget/ledger.json',phase='P5',requests=limits['deepseek_inference_requests'],
                  codex_turns=limits['codex_subscription_turns'],cash_nano=int(limits['api_cash_usd']*1e9))
    runtime.STOP.clear();runtime.CONTEXT.update(key=key,ledger=ledger,deadline=deadline,limits=limits,phase='P5')
    stages.CONTEXT.update(key=key,ledger=ledger,deadline=deadline)
    from hmz.sdk import Hmz
    flow=Hmz(workspace=root).run('/opt/workbench/source/flows/workbench_loop','Work through the frozen task with independent roles',agents={},
         params={'run_root':str(root),'contract_hash':contract['contract_hash'],'pause_after':contract['settings'].get('pause_after','') if not resume else ''},
         budget={'duration':timedelta(seconds=remaining),'graceful':False},resume=resume)
    status=None;flow.start()
    while flow.running:
        if (root/'control/stop.requested').exists():status='CANCELLED';runtime.STOP.set();flow.stop();break
        if any(p.name not in old_pauses for p in (root/'control').glob('pause-*.json')):status='PAUSED';flow.stop();break
        if time.monotonic()>=deadline:status='TIMEOUT';runtime.STOP.set();flow.stop();break
        time.sleep(.1)
    if flow.raised and status!='PAUSED':runtime.STOP.set()
    if not flow.wait(40):raise RuntimeError('Native Flow did not terminate')
    status=status or ('INFRA_FAIL' if flow.raised else 'COMPLETED')
    result={'status':status,'epic':str(flow.epic),'segment':segment,'active_elapsed_seconds':active+time.perf_counter()-tick,
            'contract_hash':contract['contract_hash'],'error_type':type(flow.raised).__name__ if flow.raised else None}
    if status=='COMPLETED':
        result['task_verdict']=stages.load(root,'builder').get('verdict','FAIL');result['human_review_required']=True
    exclusive_json(root/'control'/('segment-'+str(segment)+'.json'),result)
    (root/'control/resume.json').write_text(json.dumps(result,indent=2)+'\n')
    request=root/'control/pause.requested'
    if request.exists():request.rename(root/'control'/('pause-consumed-'+str(segment)+'.request'))
    result['run_id']=root.name
    print(json.dumps(result),flush=True)
    stages.CONTEXT['key']='';runtime.CONTEXT['key']='';key=''
    return 0 if status in ('PAUSED','COMPLETED','CANCELLED') else 1


if __name__=='__main__':sys.exit(main())
