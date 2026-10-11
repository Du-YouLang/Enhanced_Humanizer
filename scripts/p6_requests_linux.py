"""Native Requests smoke setup and reference controls, separate from model execution."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from p6_prepare_linux import BASE,checkout,setup_env,seal_environment
from p6_evaluate_linux import evaluate

PREFIX=BASE/'envs/requests-py39-v2'
TASK='SWEL-psf__requests-1963'
SEAL_ID=TASK+'-v2'


@contextlib.contextmanager
def fixture():
    env=setup_env();logs=BASE/'private/httpbin';logs.mkdir(parents=True,exist_ok=True)
    with (logs/(str(time.time_ns())+'.private.log')).open('wb') as err:
        process=subprocess.Popen([str(PREFIX/'bin/python'),'-B','/opt/workbench/source/p6_httpbin_linux.py'],
                                 cwd=BASE,env=env,stdout=subprocess.PIPE,stderr=err)
        try:
            import selectors
            with selectors.DefaultSelector() as sel:
                sel.register(process.stdout,selectors.EVENT_READ)
                if not sel.select(20):raise RuntimeError('Local HTTPBIN did not start')
                row=json.loads(process.stdout.readline())
            yield row['fixture_url']
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()


def acceptance(source,row,url):
    tests=json.loads(row['FAIL_TO_PASS'])+json.loads(row['PASS_TO_PASS'])
    return evaluate(source,PREFIX,[str(PREFIX/'bin/python'),'-B','/opt/workbench/source/p6_requests_runner.py',
                    '-q','-o','addopts=','-p','no:cacheprovider',
                    '--junitxml={junit}',*tests],{},expected_tests=tests,test_patch=row['test_patch'],
                    timeout=120,fixture_url=url,tls_regressions=True)


def prepare(row):
    tick=time.perf_counter();env=setup_env()
    if row['instance_id']!='psf__requests-1963':raise ValueError('Not the frozen Requests smoke')
    source=BASE/'sources'/TASK;gold=BASE/'private/gold'/TASK
    checkout(row['repo'],row['base_commit'],source)
    log=BASE/'requests-preparation.private.log'
    with log.open('ab') as handle:
        if not (PREFIX/'bin/python').exists():
            subprocess.run([str(BASE/'conda/bin/conda'),'create','--yes','--prefix',str(PREFIX),
                            '--override-channels','--channel','conda-forge','python=3.9.23','pip=25.2',
                            '--no-default-packages'],env=env,stdout=handle,stderr=subprocess.STDOUT,check=True,timeout=600)
        if not (BASE/'private/environment-seals'/f'{SEAL_ID}.json').exists():
            packages=['pytest==7.4.4','httpbin==0.7.0','Flask==1.1.4','Werkzeug==1.0.1',
                      'Jinja2==2.11.3','itsdangerous==1.1.0','MarkupSafe==2.0.1','six==1.17.0']
            subprocess.run([str(PREFIX/'bin/python'),'-m','pip','install',*packages],env=env,
                           stdout=handle,stderr=subprocess.STDOUT,check=True,timeout=300)
            subprocess.run([str(PREFIX/'bin/python'),'-m','pip','install','--no-deps','--no-build-isolation',str(source)],
                           env=env,stdout=handle,stderr=subprocess.STDOUT,check=True,timeout=120)
    if not gold.exists():
        gold.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['git','clone','--no-local',str(source),str(gold)],env=env,capture_output=True,check=True,timeout=120)
        subprocess.run(['git','-C',str(gold),'remote','remove','origin'],env=env,capture_output=True,check=True)
        subprocess.run(['git','-C',str(gold),'apply','-'],input=row['patch'].encode(),env=env,capture_output=True,check=True)
    seal=seal_environment(PREFIX,SEAL_ID)
    with fixture() as url:
        controls={name:acceptance(path,row,url) for name,path in [('buggy',source),('gold',gold)]}
    failing=json.loads(row['FAIL_TO_PASS'])
    passes=controls['gold']['verdict']=='PASS'
    detected=controls['buggy']['verdict']=='FAIL' and any(controls['buggy']['test_statuses'].get(n)=='FAIL' for n in failing)
    receipt={'task_id':TASK,'status':'EVALUATOR_VALIDATED' if passes and detected else 'INFRA_FAIL',
             'environment':seal,'results':controls,'base_commit':row['base_commit'],
             'preparation_seconds':time.perf_counter()-tick,'model_requests':0,
             'protocol':'native Python3.9.23/pytest7.4.4/local pinned HTTPBIN0.7.0; two unchanged external HTTPS regressions'}
    output=BASE/'private/preparation-attempts'/(str(time.time_ns())+'-requests.json')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(receipt,indent=2)+'\n')
    return {k:receipt[k] for k in ('task_id','status','environment','preparation_seconds','model_requests','protocol')}


if __name__=='__main__':
    print(json.dumps(prepare(json.load(sys.stdin))))
