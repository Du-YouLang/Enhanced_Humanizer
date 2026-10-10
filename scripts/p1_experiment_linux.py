"""Frozen synthetic experiments with official SDK/Flow entry points and independent tests."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from p1_broker import Broker,protect_memory
from p1_budget import Ledger
from p1_acceptance import DESIGN_CHECK, verification_command
from export_codex_usage import collect

BASE=Path('/opt/workbench')
TASK='Fix weighted_mean in weighted_stats.py to compute sum(value * weight) / sum(weight). Handle any iterable of (value, weight), including generators; reject negative weights and zero total weight with ValueError. Read files, edit code, run python -m unittest -v, and make a Git commit. Do not edit test_weighted_stats.py or install dependencies or spawn subagents. Finish in one turn and report the commit/tests.'
SOURCE='def weighted_mean(pairs):\n    values = list(pairs)\n    return sum(value for value, weight in values) / len(values)\n'
TESTS='''import unittest
from weighted_stats import weighted_mean
class TestWeighted(unittest.TestCase):
    def test_weighting(self): self.assertAlmostEqual(weighted_mean([(2,1),(8,3)]),6.5)
    def test_generator(self): self.assertEqual(weighted_mean((p for p in [(2,1),(4,1)])),3)
    def test_negative(self):
        with self.assertRaises(ValueError): weighted_mean([(2,-1),(4,2)])
    def test_zero(self):
        with self.assertRaises(ValueError): weighted_mean([(1,0)])
    def test_empty(self):
        with self.assertRaises(ValueError): weighted_mean([])
'''


def git(root,*args,**kwargs):
    return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.STDOUT,**kwargs).decode().strip()


def fixture(root):
    frozen=BASE/'source/p1-frozen-fixture'
    if not frozen.exists():
        frozen.mkdir()
        git(frozen,'init','-b','fixture/base')
        git(frozen,'config','user.name','Workbench Fixture');git(frozen,'config','user.email','fixture@example.invalid')
        (frozen/'weighted_stats.py').write_text(SOURCE)
        (frozen/'test_weighted_stats.py').write_text(TESTS)
        (frozen/'.gitignore').write_text('__pycache__/\n.hmz/\n')
        git(frozen,'add','.')
        git(frozen,'commit','-m','Frozen weighted mean fixture',env=os.environ|{'GIT_AUTHOR_DATE':'2026-10-10T00:00:00Z','GIT_COMMITTER_DATE':'2026-10-10T00:00:00Z'})
    if (frozen/'weighted_stats.py').read_text()!=SOURCE or (frozen/'test_weighted_stats.py').read_text()!=TESTS:
        raise RuntimeError('Frozen fixture changed; create an explicit new version')
    root.mkdir()
    git(BASE,'clone','--no-local',str(frozen),str(root/'worktree'))
    work=root/'worktree'
    git(work,'config','user.name','Workbench Builder');git(work,'config','user.email','builder@example.invalid')
    git(work,'remote','remove','origin')
    git(work,'switch','-c','run/'+root.name)
    return work,git(work,'rev-parse','HEAD')


def native(work,broker,home):
    from deepseek_harness import DeepSeekHarness
    from deepseek_harness_runtime import resolve_bundled_launch_args
    from hmz.coganchor.fence import Fence,wrapper
    home.mkdir(parents=True)
    scratch=home/'tmp';scratch.mkdir()
    cache=home/'cache';cache.mkdir()
    fence=Fence.of(local='none',user='none',system='none',online=False,workdir=work,home=Path.home(),
                   read=(BASE/'.venv-linux',),write=(work,home),hosts=(broker.host_port,))
    from dataclasses import replace
    fence=replace(fence,tmp=str(scratch))
    launch=(*wrapper(fence),*resolve_bundled_launch_args(),'--profile','sdk')
    env={'DSH_HOME':str(home),'DSH_PERMISSION_MODE':'danger-full-access','DEEPSEEK_API_KEY':broker.capability,
         'DEEPSEEK_BASE_URL':broker.url,'PKG_NATIVE_CACHE_PATH':str(cache),'XDG_CACHE_HOME':str(cache),
         'TMPDIR':str(scratch),'HUMANIZE_SENTRY':'off'}
    with DeepSeekHarness(_launch_args=launch,dsh_home=str(home),cwd=str(work),env=env,
                         model='deepseek-flash',provider='deepseek-official',reasoning_effort='low',
                         max_tokens=4096,initialize_timeout_seconds=30,request_timeout_seconds=120) as harness:
        result=harness.run(TASK,session_id='native-'+work.parent.name)
        return {'session_id':result.session_id,'finish_reason':result.finish_reason,'answer':result.final_response}


def flow_run(mode,work,root,base,ledger,experiment,turns,deadline):
    from hmz.sdk import Hmz
    from p1_drivers import MeteredDriver
    if mode=='rlar':flow='rlar';roles={'actor':'dsh/deepseek-flash:low','reviewer':'codex/gpt-6.1-sol:low'}
    elif mode=='flame':flow='flame_chase';roles={'first_chaser':'dsh/deepseek-flash:low','second_chaser':'codex/gpt-6.1-sol:low'}
    elif mode=='humanize':flow='/opt/workbench/source/flows/p0_coding_demo';roles={'builder':'dsh/deepseek-flash:low'}
    else:flow='/opt/workbench/source/flows/basic_relay';roles={'ds_builder':'dsh/deepseek-flash:low','sol_builder':'codex/gpt-6.1-sol:low'}
    task=TASK
    if mode=='flame':
        task+=' If the weighted mean is already correct and committed, implement a new streaming WeightedMean class with add(value, weight), merge(other), result(); make weighted_mean delegate to it, add test_accumulator.py, run all tests and make another commit. Do not merely review.'
    def construct(resume=False):
        params={'base_commit':base,'pause_signal':str(root/'pause.ready'),'pause_at_boundary':not bool(resume),
                'workspace_path':str(work),'verification_scratch':str(root/'verify-tmp')} if mode=='relay' else None
        return Hmz(workspace=work).run(flow,task,
                agents={role:MeteredDriver(role+'='+spec,ledger,experiment,turns,2) for role,spec in roles.items()},
                params=params,budget={'duration':timedelta(seconds=max(1,deadline-time.monotonic())),'graceful':False},resume=resume)
    run=construct();run.start()
    paused=False
    while run.running:
        if mode=='relay' and (root/'pause.ready').exists():
            run.stop();paused=True;break
        if mode=='flame' and len(turns)==2 and all(t['status']=='COMPLETED' for t in turns):
            run.stop();break
        if time.monotonic()>=deadline:run.stop();break
        time.sleep(0.1)
    if not run.wait(35):raise RuntimeError('Flow failed to stop')
    first_epic=str(run.epic)
    if paused:
        checkpoint=git(work,'rev-parse','HEAD')
        before=len(turns)
        resumed=construct(resume=first_epic)
        result=resumed.run()
        if len(turns)!=before+1 or turns[-1]['harness']!='codex':raise RuntimeError('Resume replayed completed DS work')
        return {'paused':True,'resume_epic':str(resumed.epic),'pause_epic':first_epic,'checkpoint_commit':checkpoint,'result':result}
    if mode=='flame' and len(turns)==2 and all(t['status']=='COMPLETED' for t in turns):
        return {'controlled_stop_after_turns':2,'epic':first_epic,'flow_result':'EXPECTED_PAUSE_IN_UPSTREAM_LOOP'}
    if run.raised:raise run.raised
    return {'epic':first_epic,'result':run.result}


def main():
    payload=json.load(sys.stdin)
    key=payload.pop('key')
    if payload.get('phase')!='P1' or payload.get('p0_gate')!='PASS':raise RuntimeError('P0/P1 authorization missing')
    protect_memory()
    mode,experiment=payload['mode'],payload['run_id']
    started=time.perf_counter();deadline=time.monotonic()+min(payload['experiment_seconds'],900)
    root=BASE/'runs'/experiment
    work,base=fixture(root)
    ledger=Ledger(BASE/'state/p1-budget/ledger.json',requests=payload['requests'],codex_turns=payload['codex_turns'],cash_nano=payload['cash_nano'])
    broker=Broker(key,ledger,experiment,deadline);key='';broker.start()
    os.environ['DEEPSEEK_API_KEY']=broker.capability
    os.environ['DEEPSEEK_BASE_URL']=broker.url
    turns=[]
    record={'schema_version':1,'run_id':experiment,'mode':mode,'kind':'REAL_MODEL_EXPERIMENT','base_commit':base,
            'observed_at':datetime.now(timezone.utc).isoformat(),'prompt_sha256':hashlib.sha256(TASK.encode()).hexdigest(),
            'runtime_lock_sha256':payload['runtime_lock_sha256'],'turns':turns,'api_bill_usd':'unavailable'}
    tick=time.perf_counter()
    try:
        result=native(work,broker,BASE/'state'/experiment) if mode=='native' else flow_run(mode,work,root,base,ledger,experiment,turns,deadline)
        if mode=='native' and result['finish_reason']!='completed':raise RuntimeError('Official DSH turn did not complete; inspect retained runtime evidence')
        record['result']=result
        tested=subprocess.run(verification_command(work,[sys.executable,'-m','unittest','-v'],root/'verify-tmp'),
                              cwd=work,text=True,capture_output=True,timeout=15)
        record.update(test_exit_code=tested.returncode,test_log=tested.stderr,head_commit=git(work,'rev-parse','HEAD'),
                      frozen_test_unchanged=(work/'test_weighted_stats.py').read_text()==TESTS,working_tree=git(work,'status','--porcelain'))
        record['verdict']='PASS' if tested.returncode==0 and record['head_commit']!=base and record['frozen_test_unchanged'] and not record['working_tree'] else 'FAIL'
        if mode in ('flame','relay'):
            design=subprocess.run(verification_command(work,[sys.executable,'-c',DESIGN_CHECK],root/'verify-tmp'),
                                  cwd=work,text=True,capture_output=True,timeout=15)
            record['independent_redesign']={'exit_code':design.returncode,'stdout':design.stdout,'stderr':design.stderr}
            if design.returncode:record['verdict']='FAIL'
    except BaseException as error:
        record.update(verdict='INFRA_FAIL',error_type=type(error).__name__,error=str(error)[:3000])
    finally:
        broker.close()
        record['model_and_tools_seconds']=round(time.perf_counter()-tick,6)
        record['elapsed_seconds']=round(time.perf_counter()-started,6)
        usage=resource.getrusage(resource.RUSAGE_CHILDREN)
        record['child_resources']={'user_cpu_seconds':usage.ru_utime,'system_cpu_seconds':usage.ru_stime,'max_rss_kib':usage.ru_maxrss}
        ledger_value=json.loads(ledger.path.read_text()) if ledger.path.exists() else {'requests':[],'codex_turns':[],'cash_bound_nano':0}
        record['requests']=[r for r in ledger_value['requests'] if r['experiment']==experiment]
        record['p1_cash_bound_usd']=ledger_value['cash_bound_nano']/1e9
        record['p1_requests_reserved']=len(ledger_value['requests']);record['p1_codex_turns_reserved']=len(ledger_value['codex_turns'])
        record['codex_usage']=[row for epic in (BASE/'state/humanize/epics').glob('*'+experiment+'*') for row in collect(epic)]
        if any(row['model_id']!='gpt-6.1-sol' for row in record['codex_usage']):
            record.update(verdict='INFRA_FAIL',error='Observed Codex model identity mismatch')
        record['subscription_cost_usd']='unavailable'
        record['subscription_api_cash_usd']=0
        path=BASE/'evidence'/(experiment+'.json');path.write_text(json.dumps(record,default=str,indent=2)+'\n')
        print(json.dumps({k:v for k,v in record.items() if k not in ('result','requests','test_log')},default=str),flush=True)
    return 0 if record['verdict']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
