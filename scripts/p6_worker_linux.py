"""A P6 task adapter; upstream Humanize/DSH/Codex retain model and tool execution."""
import asyncio
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path,PurePosixPath
import subprocess
import sys
import time

from p1_broker import protect_memory
from p1_budget import Ledger
from p1_drivers import MeteredDriver
from p2_candidates import exclusive_json
from p3_worker_linux import completed_session,RoleLedger
from export_codex_usage import collect


def task_fence(job):
    checked=False
    def narrow(fence):
        nonlocal checked
        from hmz.coganchor.fence import wrapper
        auth=Path('/opt/workbench/state/codex/auth.json')
        def contains_auth(path):return auth.is_relative_to(Path(path).resolve())
        reads=tuple(p for p in fence.read if not contains_auth(p))
        writes=tuple(p for p in fence.write if not contains_auth(p))
        reads+=(job['prefix'],job['input_file'],'/etc/mime.types')
        if job['backend']=='codex':reads+=(str(auth),)
        hosts=fence.hosts
        if job.get('fixture_url'):
            from urllib.parse import urlsplit
            hosts+=(urlsplit(job['fixture_url']).netloc,'httpbin.org:443')
            reads+=('/etc/ssl/certs/ca-certificates.crt','/opt/workbench/source/p6_requests_runner.py')
        fence=replace(fence,read=reads,write=writes,hosts=hosts)
        if checked:return fence
        code='''import json,os,sys
from pathlib import Path
j=json.loads(sys.argv[1]);denied=[]
for p in j['denied']:
 try:Path(p).read_bytes();state='ALLOWED_FAILURE'
 except PermissionError:state='DENIED'
 except FileNotFoundError:state='MISSING_NOT_PROOF'
 denied.append(state)
readonly=[]
for p in j['readonly']:
 with open(p,'rb') as f:f.read(1)
 try:
  with open(p,'ab'):pass
  readonly.append('ALLOWED_FAILURE')
 except PermissionError:readonly.append('DENIED')
p=Path('.p6-probe')
try:p.write_text('probe');p.unlink();write='WRITE_ALLOWED'
except PermissionError:write='WRITE_DENIED'
print(json.dumps(dict(denied=denied,readonly=readonly,own_workspace=write,uid=os.getuid(),
cap_eff=next(l.split()[-1] for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('CapEff:')),
private_pid_namespace=os.readlink('/proc/self/ns/pid')!=j['parent_namespace'])))
'''
        spec={'denied':job['denied_paths'],'readonly':[job['input_file'],job['prefix']+'/conda-meta/history'],
              'parent_namespace':job['parent_namespace']}
        if job['backend']=='codex':spec['readonly'].append(str(auth))
        p=subprocess.run([*wrapper(fence),sys.executable,'-B','-c',code,json.dumps(spec)],
                         cwd=job['work'],capture_output=True,text=True,timeout=20)
        if p.returncode:raise RuntimeError('P6 actual runtime fence probe did not execute')
        row=json.loads(p.stdout)
        expected='WRITE_DENIED' if job['role']=='verifier' else 'WRITE_ALLOWED'
        row['verdict']='PASS' if row['uid']!=0 and row['cap_eff']=='0000000000000000' and row['private_pid_namespace'] and row['own_workspace']==expected and row['denied']==['DENIED']*len(spec['denied']) and row['readonly']==['DENIED']*len(spec['readonly']) else 'FAIL'
        exclusive_json(Path(job['root'])/'isolation.json',row)
        if row['verdict']!='PASS':raise RuntimeError('P6 task isolation failed closed')
        checked=True
        return fence
    return narrow


class Sink:
    def add(self,**values):pass  # Actual usage comes from the broker ledger/native trace, not driver prices.


async def native_turn(driver,job):
    from hmz.runtime.flowing.spi import Placement,TurnRequest,Limits,HookTable
    from hmz.flows import EnvBackendKind
    session=await driver.open(Placement(EnvBackendKind.LOCAL,'',PurePosixPath(job['work'])),
                              permission=driver.permission,skills=(),hooks=HookTable())
    try:return await session.turn(TurnRequest(job['prompt'],limits=Limits(deadline=time.monotonic()+job['role_seconds'],graceful=False)),Sink())
    finally:
        await session.close()
        await driver.inner.close()


def main():
    job=json.load(sys.stdin);protect_memory()
    if os.getuid()==0:raise RuntimeError('No root agents')
    if job['backend']=='dsh':
        os.environ['DEEPSEEK_API_KEY']=job.pop('capability')
        os.environ['DEEPSEEK_BASE_URL']=job.pop('broker_url')
    from hmz.flows import Permission
    role=job['role'];turns=[];tick=time.perf_counter()
    permission=Permission(local='read' if role=='verifier' else 'all',user='none',system='none',online='none')
    ledger=Ledger('/opt/workbench/state/p6-budget/ledger.json',phase='P6',requests=200,codex_turns=32,cash_nano=5_000_000_000)
    label='verifier' if role=='verifier' else 'reviewer' if role=='reviewer' else 'builder'
    model='deepseek-flash' if job['backend']=='dsh' else 'gpt-6.1-sol'
    driver=MeteredDriver(f'{label}={job["backend"]}/{model}:low',RoleLedger(ledger),job['scope'],turns,1,
                         600 if job['backend']=='dsh' else 115,permission=permission,fence_transform=task_fence(job))
    value={'kind':'REAL_MODEL_EXPERIMENT','status':'RUNNING','turns':turns,'scope':job['scope'],
           'role':role,'execution_mode':job['execution_mode'],'input_sha256':job['input_sha256']}
    try:
        if job.get('offline_control'):
            from hmz.coganchor.fence import Fence
            fence=Fence.of(local='read' if role=='verifier' else 'all',user='none',system='none',online=False,
                           workdir=job['work'],home=Path.home(),write=(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')),))
            task_fence(job)(fence)
            value.update(kind='ZERO_MODEL_CONTROL',status='COMPLETED')
        elif job['execution_mode']=='native_driver':
            answer=asyncio.run(native_turn(driver,job));value.update(status='COMPLETED',answer=answer)
        else:
            from hmz.sdk import Hmz
            flow={'verifier':'sol_judge','reviewer':'sol_synthesis','builder':'p0_coding_demo'}[role]
            run=Hmz(workspace=job['work']).run('/opt/workbench/source/flows/'+flow,job['prompt'],agents={label:driver},
                budget={'duration':timedelta(seconds=job['role_seconds']),'graceful':False})
            value.update(epic=str(run.epic));value.update(answer=run.run(),status='COMPLETED')
        if not job.get('offline_control'):
            if job['backend']=='codex':
                usage=collect(Path(job['root']));completed=completed_session(usage,turns)
                value.update(usage=usage,model_id=completed['model_id'],session_id=completed['session_id'])
            else:value.update(model_id='deepseek-flash',session_id=turns[0]['session_id'])
    except BaseException as error:
        value.update(status='INFRA_FAIL',error_type=type(error).__name__,error=str(error)[:800])
        if job['backend']=='codex':value['usage']=collect(Path(job['root']))
    value['elapsed_seconds']=time.perf_counter()-tick
    exclusive_json(Path(job['root'])/'worker.json',value)
    return 0 if value['status']=='COMPLETED' else 1


if __name__=='__main__':sys.exit(main())
