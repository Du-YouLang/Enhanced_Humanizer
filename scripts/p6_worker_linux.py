"""A P6 task adapter; upstream Humanize/DSH/Codex retain model and tool execution."""
import asyncio
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path,PurePosixPath
import subprocess
import sys
# The continuation worker reuses all dependencies from the immutable executor.
sys.path[:0]=['/opt/workbench/guidance/executor-fbf96ba9cf225ed7f235','/opt/workbench/guidance/executor-fbf96ba9cf225ed7f235/src']
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
        reads+=tuple(job.get('public_read_paths',()))
        if job.get('gpu_coding'):
            reads+=('/usr/lib/wsl',)
            writes+=('/dev/dxg',)
        reads+=('/opt/workbench/tools/bubblewrap/0.9.0-1build1',)
        if job['backend']=='codex':reads+=(str(auth),)
        hosts=fence.hosts
        if job.get('fixture_url'):
            from urllib.parse import urlsplit
            hosts+=(urlsplit(job['fixture_url']).netloc,)
            if job.get('phase')!='P6_MAIN_LOCAL_20261011':hosts+=('httpbin.org:443',)
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
authority_writes=[]
for p in j.get('write_denied',[]):
 try:
  with open(p,'ab'):pass
  authority_writes.append('ALLOWED_FAILURE')
 except PermissionError:authority_writes.append('DENIED')
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
print(json.dumps(dict(denied=denied,readonly=readonly,authority_writes=authority_writes,own_workspace=write,uid=os.getuid(),
cap_eff=next(l.split()[-1] for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('CapEff:')),
private_pid_namespace=os.readlink('/proc/self/ns/pid')!=j['parent_namespace'])))
'''
        spec={'denied':job['denied_paths'],'readonly':[job['input_file'],job['prefix']+'/conda-meta/history'],
              'parent_namespace':job['parent_namespace'],'write_denied':job.get('authority_write_denied_paths',[])}
        if job['backend']=='codex':spec['readonly'].append(str(auth))
        p=subprocess.run([*wrapper(fence),sys.executable,'-B','-c',code,json.dumps(spec)],
                         cwd=job['work'],capture_output=True,text=True,timeout=20)
        if p.returncode:
            exclusive_json(Path(job['root'])/'fence-probe-failed.private.json',{'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'spec':spec})
            raise RuntimeError('P6 actual runtime fence probe did not execute')
        row=json.loads(p.stdout)
        expected='WRITE_DENIED' if job['role']=='verifier' else 'WRITE_ALLOWED'
        row['verdict']='PASS' if row['uid']!=0 and row['cap_eff']=='0000000000000000' and row['private_pid_namespace'] and row['own_workspace']==expected and row['denied']==['DENIED']*len(spec['denied']) and row['readonly']==['DENIED']*len(spec['readonly']) and row['authority_writes']==['DENIED']*len(spec['write_denied']) else 'FAIL'
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
    main_phase=job.get('phase')=='P6_MAIN_LOCAL_20261011'
    if main_phase:
        from p6_main_budget import MainLedger
        ledger=MainLedger('/opt/workbench/state/p6-main-local-20261011/ledger.json',job['budget'])
        if job['backend']=='dsh' and job['budget'].get('output_budget_revision'):
            # Official profile configuration in this independent role's DSH
            # HOME. The outer broker enforces the same cap independently.
            home=Path(os.environ['DSH_HOME'])
            if not home.resolve().is_relative_to(Path(job['root']).resolve()):
                raise RuntimeError('Only this role DSH HOME may be configured')
            with (home/'settings.yaml').open('x',encoding='utf-8') as handle:
                json.dump({'llm-deepseek':{'maxTokens':ledger.max_output}},handle)
    else:
        ledger=Ledger('/opt/workbench/state/p6-budget/ledger.json',phase='P6',requests=200,codex_turns=32,cash_nano=5_000_000_000)
    label='verifier' if role=='verifier' else 'reviewer' if role=='reviewer' else 'builder'
    model='deepseek-flash' if job['backend']=='dsh' else 'gpt-6.1-sol'
    refresh=job.get('budget',{}).get('cash_budget_revision')=='USER_APPROVED_2026-11-26_MODEL_REFRESH_25000_USD500'
    if refresh:
        from p6_refresh_protocol import model_for_job
        model=model_for_job(job)
    transform=task_fence(job)
    driver=MeteredDriver(f'{label}={job["backend"]}/{model}:low',RoleLedger(ledger),job['scope'],turns,1,
                         job.get('refresh_per_turn_seconds',job['role_seconds']) if main_phase else (600 if job['backend']=='dsh' else 115),permission=permission,fence_transform=transform,
                         external_readonly=role=='verifier',turn_seconds_ceiling=job.get('refresh_per_turn_seconds',job['role_seconds']) if main_phase else 600)
    value={'kind':'REAL_MODEL_EXPERIMENT','status':'RUNNING','turns':turns,'scope':job['scope'],
           'role':role,'execution_mode':job['execution_mode'],'input_sha256':job['input_sha256'],
           'configured_role_seconds':job['role_seconds'],'effective_harness_turn_seconds':driver.turn_seconds}
    if main_phase:value['configured_request_output_tokens']=ledger.max_output if job['backend']=='dsh' else 'UNAVAILABLE_NATIVE_CODEX_LIMIT'
    try:
        if job.get('offline_control'):
            value['kind']='ZERO_MODEL_CONTROL'
            from hmz.coganchor.fence import Fence
            fence=Fence.of(local='read' if role=='verifier' else 'all',user='none',system='none',online=False,
                           workdir=job['work'],home=Path.home(),write=(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')),))
            fence=transform(fence)
            if refresh and job['backend']=='codex':
                import hashlib,shutil
                binary=shutil.which('codex')
                if not binary or hashlib.sha256(Path(binary).read_bytes()).hexdigest()!=job['refresh_cli_sha256']:
                    raise ValueError('Actual CLI selected by official Harness differs')
                from hmz.coganchor.fence import wrapper
                version=subprocess.run([*wrapper(fence),binary,'--version'],cwd=job['work'],capture_output=True,text=True,timeout=20)
                if version.returncode:raise ValueError('Pinned CLI failed inside actual OS fence')
                value['native_cli_control']={'binary':binary,'sha256':job['refresh_cli_sha256'],'version':version.stdout.strip(),'model_calls':0}
            if job.get('offline_public_command'):
                from hmz.coganchor.fence import wrapper
                p=subprocess.run([*wrapper(fence),*job['offline_public_command']],cwd=job['work'],
                                 capture_output=True,text=True,timeout=100)
                (Path(job['root'])/'public-check.private.log').write_text(p.stdout+p.stderr)
                if p.returncode!=job.get('offline_public_expected_exit',0):raise RuntimeError('Actual public scratch-copy check returned an unexpected baseline result')
            value.update(kind='ZERO_MODEL_CONTROL',status='COMPLETED')
            if job.get('refresh_matched_resume'):
                from p6_refresh_matched_resume import resume
                value['session_resume_probe']=asyncio.run(resume(driver,job,Sink(),probe=True))
            elif job.get('refresh_judge_resume'):
                from p6_refresh_session_resume import resume
                value['session_resume_probe']=asyncio.run(resume(driver,job,Sink(),probe=True))
            elif job.get('guidance_session_resume'):
                from p6_guidance_session_resume import resume
                value['session_resume_probe']=asyncio.run(resume(driver,job,Sink(),probe=True))
        elif job.get('refresh_matched_resume'):
            from p6_refresh_matched_resume import resume
            answer,slots=asyncio.run(resume(driver,job,Sink()))
            value.update(status='COMPLETED',answer=answer,matched_slot_receipts=slots,original_session_resumed=True)
        elif job.get('refresh_judge_resume'):
            from p6_refresh_session_resume import resume
            answer=asyncio.run(resume(driver,job,Sink()))
            value.update(status='COMPLETED',answer=answer,original_session_resumed=True)
        elif job.get('guidance_session_resume'):
            from p6_guidance_session_resume import resume
            answer=asyncio.run(resume(driver,job,Sink()))
            value.update(status='COMPLETED',answer=answer,original_session_resumed=True)
        elif refresh and job.get('refresh_slots')==6:
            from p6_refresh_sessions import run_matched
            answer,slots=asyncio.run(run_matched(driver,job))
            value.update(status='COMPLETED',answer=answer,matched_slot_receipts=slots)
        elif job['execution_mode']=='native_driver':
            answer=asyncio.run(native_turn(driver,job));value.update(status='COMPLETED',answer=answer)
        else:
            from hmz.sdk import Hmz
            flow={'verifier':'sol_judge','reviewer':'sol_synthesis','builder':'p0_coding_demo'}[role]
            if job.get('guidance_mentor'):
                from p6_guidance_protocol import allowed_scope
                if role!='verifier' or job['backend']!='codex' or not allowed_scope(job['scope'],'subscription'):
                    raise ValueError('Only a scoped read-only Sol mentor may run guidance')
                flow='sol_guidance'
            run=Hmz(workspace=job['work']).run('/opt/workbench/source/flows/'+flow,job['prompt'],agents={label:driver},
                budget={'duration':timedelta(seconds=job['role_seconds']),'graceful':False})
            value.update(epic=str(run.epic));value.update(answer=run.run(),status='COMPLETED')
        if not job.get('offline_control'):
            if job['backend']=='codex':
                usage=collect(Path(job['root']))
                if refresh:
                    from p6_refresh_protocol import verify_session
                    completed=verify_session(usage,turns,model)
                else:completed=completed_session(usage,turns)
                value.update(usage=usage,model_id=completed['model_id'],session_id=completed['session_id'])
                if job.get('refresh_matched_resume'):
                    from p6_guidance_shutdown import usage_segments
                    d=job['refresh_matched_resume'];before=d['prior_usage'];basis='MONOTONIC_SESSION_COUNTERS'
                    try:before,delta=usage_segments(before,completed['usage'])
                    except ValueError:delta='unavailable';basis='RESUMED_COUNTER_BASIS_UNRESOLVED'
                    value['usage']=[dict(completed,usage=before,usage_segment='BEFORE_USER_SHUTDOWN'),dict(completed,usage=delta,usage_segment='RESUMED_DELTA')]
                    value.update(session_usage_total=completed['usage'],prior_role_seconds_debited=d['prior_seconds'],original_interrupted_scope=d['original_scope'],usage_accounting_basis=basis)

                if job.get('refresh_judge_resume'):
                    from p6_guidance_shutdown import usage_segments
                    d=job['refresh_judge_resume'];before=d['prior_usage'];basis='MONOTONIC_SESSION_COUNTERS'
                    try:before,delta=usage_segments(before,completed['usage'])
                    except ValueError:delta='unavailable';basis='RESUMED_COUNTER_BASIS_UNRESOLVED'
                    value['usage']=[dict(completed,usage=before,usage_segment='BEFORE_USER_SHUTDOWN'),dict(completed,usage=delta,usage_segment='RESUMED_DELTA')]
                    value.update(session_usage_total=completed['usage'],prior_role_seconds_debited=d['prior_seconds'],original_interrupted_scope=d['original_scope'],usage_accounting_basis=basis)
                if job.get('guidance_session_resume'):
                    from p6_guidance_shutdown import usage_segments
                    previous=job['guidance_session_resume']['prior_usage']
                    try:
                        previous,delta=usage_segments(previous,completed['usage'])
                        basis='MONOTONIC_SESSION_COUNTERS'
                    except ValueError:
                        delta='unavailable';basis='RESUMED_COUNTER_BASIS_UNRESOLVED'
                    value['usage']=[dict(completed,usage=previous,usage_segment='BEFORE_USER_SHUTDOWN'),
                        dict(completed,usage=delta,usage_segment='RESUMED_DELTA')]
                    value['usage_accounting_basis']=basis
                    value['session_usage_total']=completed['usage']
                    value['prior_role_seconds_debited']=job['guidance_session_resume']['prior_seconds']
                    value['original_interrupted_scope']=job['guidance_session_resume']['original_scope']
                    value['additional_accounting_scopes']=[job['guidance_session_resume']['original_scope']]
            else:value.update(model_id='deepseek-flash',session_id=turns[0]['session_id'])
    except BaseException as error:
        status='TIMEOUT' if type(error).__name__ in ('DurationExceeded','TimeoutError') else 'INFRA_FAIL'
        value.update(status=status,error_type=type(error).__name__,error=str(error)[:800])
        if job['backend']=='codex':value['usage']=collect(Path(job['root']))
    value['elapsed_seconds']=time.perf_counter()-tick
    exclusive_json(Path(job['root'])/'worker.json',value)
    return 0 if value['status']=='COMPLETED' else 1


if __name__=='__main__':sys.exit(main())
