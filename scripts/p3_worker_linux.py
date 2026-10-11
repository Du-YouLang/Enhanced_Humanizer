"""One fresh Sol role through official Humanize/Codex, inside a non-root PID namespace."""

from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from p1_broker import protect_memory
from p1_budget import Ledger
from p2_candidates import exclusive_json
from export_codex_usage import collect


class RoleLedger:
    def __init__(self,ledger):self.ledger=ledger
    def reserve_codex_turn(self,scope,model):
        return self.ledger.reserve_codex_turn(scope,model,scope_turns=2)


def completed_session(usage,turns):
    """Match the completed Harness turn to its trace, preserving failed retries."""
    completed=[t for t in turns if t.get('status')=='COMPLETED']
    if len(completed)!=1:raise RuntimeError('Exactly one completed independent Sol turn required')
    turn=completed[0];session=turn.get('session_id')
    matched=[row for row in usage if row.get('session_id')==session]
    if not session or len(matched)!=1:raise RuntimeError('Completed Sol session trace not uniquely verified')
    row=matched[0];tokens=row.get('usage')
    if turn.get('model_requested')!='gpt-6.1-sol' or row.get('model_id')!='gpt-6.1-sol' or not isinstance(tokens,dict):
        raise RuntimeError('Completed Sol model/usage not verified')
    if any(type(tokens.get(k)) is not int or tokens[k]<0 for k in ('input_tokens','output_tokens','cached_input_tokens')):
        raise RuntimeError('Completed Sol token evidence missing or invalid')
    if tokens['cached_input_tokens']>tokens['input_tokens']:raise RuntimeError('Invalid cached Sol usage')
    return row


def role_fence(job):
    checked=False
    def narrow(fence):
        nonlocal checked
        from hmz.coganchor.fence import wrapper
        auth=Path('/opt/workbench/state/codex/auth.json')
        def grants_auth(path):return auth.is_relative_to(Path(path).resolve())
        fence=replace(fence,read=tuple(p for p in fence.read if not grants_auth(p))+(str(auth),job['input_file']),
                      write=tuple(p for p in fence.write if not grants_auth(p)))
        if checked:return fence
        code='''import json,os,sys
from pathlib import Path
spec=json.loads(sys.argv[1]);out=[]
for name in spec['denied']:
 row={'path':name}
 try:Path(name).read_bytes();row['read']='ALLOWED_FAILURE'
 except PermissionError:row['read']='DENIED'
 except FileNotFoundError:row['read']='MISSING_NOT_PROOF'
 try:
  with open(name,'ab'):pass
  row['write']='ALLOWED_FAILURE'
 except PermissionError:row['write']='DENIED'
 except FileNotFoundError:row['write']='MISSING_NOT_PROOF'
 out.append(row)
readonly=[]
for name in spec['readonly']:
 # Never print file content; auth is runtime input, not isolated from its own Harness.
 with open(name,'rb') as f:f.read(1)
 try:
  with open(name,'ab'):pass
  readonly.append({'path':name,'write':'ALLOWED_FAILURE'})
 except PermissionError:readonly.append({'path':name,'write':'DENIED'})
own=Path('.p3-permission-probe')
try:
 own.write_text('harmless probe');own.unlink();own_status='WRITE_ALLOWED'
except PermissionError:own_status='WRITE_DENIED'
print(json.dumps({'paths':out,'readonly':readonly,'own_workspace':own_status,'uid':os.getuid(),
 'private_pid_namespace':os.readlink('/proc/self/ns/pid')!=spec['parent_namespace']}))
'''
        spec={'denied':job['denied_paths'],'readonly':[job['input_file'],str(auth)],'parent_namespace':job['parent_namespace']}
        p=subprocess.run([*wrapper(fence),sys.executable,'-B','-c',code,json.dumps(spec)],cwd=job['work'],
                         capture_output=True,text=True,timeout=20)
        if p.returncode:raise RuntimeError('P3 actual runtime fence probe failed')
        value=json.loads(p.stdout)
        expected='WRITE_DENIED' if job['role']=='verifier' else 'WRITE_ALLOWED'
        value['verdict']='PASS' if value['uid']!=0 and value['private_pid_namespace'] and value['own_workspace']==expected and all(
            r['read']==r['write']=='DENIED' for r in value['paths']) and all(r['write']=='DENIED' for r in value['readonly']) else 'FAIL'
        exclusive_json(Path(job['root'])/'isolation.json',value)
        if value['verdict']!='PASS':raise RuntimeError('P3 role isolation failed closed')
        checked=True
        return fence
    return narrow


def main():
    job=json.load(sys.stdin);protect_memory()
    if os.getuid()==0:raise RuntimeError('Agents must not run as root')
    cap=next(line.split()[-1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('CapEff:'))
    if cap!='0000000000000000':raise RuntimeError('Role retained effective capabilities')
    if job.get('offline_control')=='sleep':time.sleep(60);return 1
    if job.get('offline_control')=='fence':
        from hmz.coganchor.fence import Fence
        fence=Fence.of(local='read' if job['role']=='verifier' else 'all',user='none',system='none',online=False,
             workdir=job['work'],home=Path.home(),write=(os.environ['CODEX_HOME'],'/opt/workbench/state/codex','/opt/workbench/state/codex/auth.json'))
        role_fence(job)(fence)
        exclusive_json(Path(job['root'])/'worker.json',{'kind':'ZERO_MODEL_FENCE_CONTROL','status':'COMPLETED','input_sha256':job['input_sha256']})
        return 0
    from hmz.sdk import Hmz
    from hmz.flows import Permission
    from p1_drivers import MeteredDriver
    role=job['role'];turns=[];tick=time.perf_counter()
    limits=job['limits']
    phase=job.get('phase','P3')
    if phase not in ('P3','P5'):raise RuntimeError('Unauthorized role phase')
    ledger=Ledger('/opt/workbench/state/'+phase.lower()+'-budget/ledger.json',phase=phase,requests=limits['deepseek_inference_requests'],
                  codex_turns=limits['codex_subscription_turns'],cash_nano=int(limits['api_cash_usd']*1e9))
    spec='verifier' if role=='verifier' else ('reviewer' if role=='reviewer' else 'builder')
    permission=Permission(local='read' if role=='verifier' else 'all',user='none',system='none',online='none')
    driver=MeteredDriver(spec+'=codex/gpt-6.1-sol:low',RoleLedger(ledger),job['scope'],turns,1,min(115,limits['per_request_timeout_seconds']),
                         permission=permission,fence_transform=role_fence(job))
    flow={'verifier':'sol_judge','reviewer':'sol_synthesis','builder':'p0_coding_demo'}[role]
    run=Hmz(workspace=job['work']).run('/opt/workbench/source/flows/'+flow,job['prompt'],agents={spec:driver},
                                    budget={'duration':timedelta(seconds=min(600,job['role_seconds'])),'graceful':False})
    value={'kind':'REAL_MODEL_EXPERIMENT','role':role,'scope':job['scope'],'status':'RUNNING','turns':turns,
           'uid':os.getuid(),'cap_eff':cap,'input_sha256':job['input_sha256'],'parent_namespace':job['parent_namespace'],'epic':str(run.epic)}
    try:
        answer=run.run();usage=collect(Path(run.epic))
        completed=completed_session(usage,turns)
        value.update(status='COMPLETED',answer=answer,session_id=completed['session_id'],usage=usage,
                     model_id=completed['model_id'],epic=str(run.epic))
    except BaseException as error:
        value.update(status='INFRA_FAIL',error_type=type(error).__name__,error=str(error)[:800],usage=collect(Path(run.epic)))
    value['elapsed_seconds']=time.perf_counter()-tick
    exclusive_json(Path(job['root'])/'worker.json',value)
    return 0 if value['status']=='COMPLETED' else 1


if __name__=='__main__':sys.exit(main())
