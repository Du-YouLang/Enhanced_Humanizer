"""Humanize schedules complete official-Harness candidate processes; never per-response samples."""

import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from hmz.flows import AgentCollection, EnvCollection, FlowContext, FlowParams, flow
from p2_candidates import namespace_command, candidate_env, run_tests, digest, SOURCE


class Agents(AgentCollection):pass
class Envs(EnvCollection):pass


class Params(FlowParams):
    descriptor_path: str
    concurrency: int=3
    candidate_seconds: int=600


@flow(agents=Agents,envs=Envs,params=Params)
async def ds_candidates(task: str, *, agents: Agents, envs: Envs, params: Params, ctx: FlowContext):
    """N isolated full tasks. Each worker uses the existing Humanize Builder + official DSH."""
    jobs=json.loads(Path(params.descriptor_path).read_text())
    semaphore=asyncio.Semaphore(min(5,max(1,params.concurrency)))
    queued=time.perf_counter()
    async def launch(job):
        async with semaphore:
            tick=time.perf_counter()
            timeline={'started_at_seconds':tick-queued,'time_to_first_patch':'unavailable',
                      'time_to_first_test_pass':'unavailable','observation_interval_seconds':0.5}
            env=candidate_env(job['root'])
            command=namespace_command([sys.executable,'/opt/workbench/source/p2_worker_linux.py'])
            p=await asyncio.create_subprocess_exec(*command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                                  env=env,cwd=job['work'],start_new_session=True)
            communicate=asyncio.create_task(p.communicate(json.dumps(job).encode()))
            reason=None
            record=None
            try:
                while not communicate.done():
                    elapsed=time.perf_counter()-tick
                    if elapsed>min(600,params.candidate_seconds):reason='TIMEOUT';break
                    try:
                        source_file=job.get('task_contract',{}).get('source_file','weighted_stats.py')
                        fd=os.open(Path(job['work'])/source_file,os.O_RDONLY|os.O_NOFOLLOW)
                        with os.fdopen(fd,'rb') as handle:changed=digest(handle.read(100_001))!=job.get('initial_source_sha256',digest(SOURCE.encode()))
                        if changed and timeline['time_to_first_patch']=='unavailable':timeline['time_to_first_patch']=elapsed
                        if changed and timeline['time_to_first_test_pass']=='unavailable':
                            tested=await asyncio.to_thread(run_tests,job['work'],contract=job.get('task_contract'))
                            if tested['verdict']=='PASS':timeline['time_to_first_test_pass']=time.perf_counter()-tick
                    except OSError:pass
                    await asyncio.sleep(0.5)
                if reason:
                    os.killpg(p.pid,signal.SIGTERM)
                    try:await asyncio.wait_for(asyncio.shield(communicate),5)
                    except asyncio.TimeoutError:os.killpg(p.pid,signal.SIGKILL)
                out,err=await communicate
                root=Path(job['root']);(root/'worker.stdout.private.log').write_bytes(out);(root/'worker.stderr.private.log').write_bytes(err)
                record=json.loads((root/'worker.json').read_text()) if (root/'worker.json').exists() else {'status':reason or 'INFRA_FAIL'}
                if reason:record['status']=reason
            finally:
                if p.returncode is None:
                    os.killpg(p.pid,signal.SIGKILL);await p.wait()
                timeline['completed_at_seconds']=time.perf_counter()-queued
                timeline['candidate_wall_seconds']=time.perf_counter()-tick
                row={'id':job['id'],'worker':record or {'status':'TIMEOUT' if isinstance(sys.exc_info()[1],asyncio.CancelledError) else 'INFRA_FAIL'},
                     'timeline':timeline,'queue_seconds':tick-queued}
                (Path(job['root'])/'scheduler-outcome.json').write_text(json.dumps(row,indent=2)+'\n')
            return row
    return {'candidates':await asyncio.gather(*(launch(job) for job in jobs)),'outer_retries':0}
