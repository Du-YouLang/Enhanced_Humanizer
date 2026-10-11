"""Prepare all frozen public tasks and controls before any main model call."""
import ast
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

from p6_prepare_linux import BASE,checkout,seal_environment,setup_env
from p6_evaluate_linux import evaluate


def gold_patch(source,gold,patch):
    env=setup_env()
    if gold.exists():raise ValueError('Preserve prior gold and choose a new attempt')
    subprocess.run(['git','-c','core.hooksPath=/dev/null','clone','--no-local',str(source),str(gold)],
                   env=env,capture_output=True,check=True,timeout=120)
    subprocess.run(['git','-C',str(gold),'remote','remove','origin'],env=env,capture_output=True,check=True)
    subprocess.run(['git','-C',str(gold),'apply','-'],input=patch.encode(),env=env,capture_output=True,check=True)


def environment(kind,source,log):
    prefixes={'black':'black-py383','requests':'requests-py39-v2','pytest':'pytest-py39-main-v2','sympy':'sympy-py39-main-v1'}
    prefix=BASE/'envs'/prefixes[kind]
    if kind in ('black','requests'):
        if not (prefix/'bin/python').exists():raise ValueError('Validated historical task environment absent')
        return prefix
    env=setup_env();marker=prefix/'main-environment-installed.json'
    if kind=='pytest':env['SETUPTOOLS_SCM_PRETEND_VERSION']='8.0.0.dev0'
    with log.open('ab') as out:
        def run(args):subprocess.run(args,env=env,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=600)
        if not (prefix/'bin/python').exists():
            run([str(BASE/'conda/bin/conda'),'create','--yes','--prefix',str(prefix),'--override-channels',
                 '--channel','conda-forge','python=3.9.23','pip=25.2','--no-default-packages'])
        if not marker.exists():
            packages={'pytest':['iniconfig==2.0.0','packaging==23.1','pluggy==1.3.0','exceptiongroup==1.1.3',
                                'tomli==2.0.1','setuptools==68.2.2','setuptools-scm==8.0.4','wheel==0.45.1'],
                      'sympy':['mpmath==1.3.0','flake8==7.3.0','flake8-comprehensions==3.17.0','setuptools==68.2.2','wheel==0.45.1']}[kind]
            run([str(prefix/'bin/python'),'-m','pip','install',*packages])
            run([str(prefix/'bin/python'),'-m','pip','install','--no-deps','--no-build-isolation',str(source)])
            marker.write_text(json.dumps({'kind':kind,'initial_source':str(source),'packages':packages,'model_requests':0}))
    return prefix


def prepare(task,bip=None,swe=None,attempt=None):
    tid=task['task_id'];tick=time.perf_counter();env=setup_env()
    source=BASE/'sources'/tid;checkout(task['repository'],task['base_commit'],source)
    gold=attempt/(tid+'-gold');hidden={};test_patch=None;expected=None;framework='pytest'
    if bip:
        info=dict(re.findall(r'(\w+)="([^"]*)"',bip['bug.info']))
        checkout(task['repository'],info['fixed_commit_id'],gold)
        for file in (gold/'tests').rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:hidden[str(file.relative_to(gold))]=file.read_bytes()
        hidden.setdefault('tests/__init__.py',b'')
        commands=[shlex.split(line) for line in bip['run_test.sh'].strip().splitlines() if line.strip()]
        if any(words[:3]!=['python','-m','unittest'] or any(w.startswith('-') and w not in ('-q','-v') for w in words[3:]) for words in commands):
            raise ValueError('Frozen BugsInPy command needs explicit review')
        prefix=environment('black',source,attempt/'install.log')
        argv=[str(prefix/'bin/python'),'-B','-m','unittest','-q',*[w for words in commands for w in words[3:] if not w.startswith('-')]]
        methods=sorted({n.name for n in ast.walk(ast.parse((source/'tests/test_black.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')})
        visible_names=[n for n in methods if n in ('test_empty','test_simple','test_string_quotes','test_numeric_literals')][:3]
        visible=[str(prefix/'bin/python'),'-B','-m','unittest','-q',*['tests.test_black.BlackTestCase.'+n for n in visible_names]]
        message=subprocess.check_output(['git','-C',str(gold),'show','-s','--format=%s','HEAD'],env=env,text=True).strip()
        prompt='Fix this frozen Black regression: '+message+'. Inspect the existing implementation and add a regression test.'
        context=None
    else:
        kind='requests' if swe['repo']=='psf/requests' else 'pytest' if swe['repo']=='pytest-dev/pytest' else 'sympy'
        gold_patch(source,gold,swe['patch']);prefix=environment(kind,source,attempt/'install.log')
        pp=json.loads(swe['PASS_TO_PASS']);expected=json.loads(swe['FAIL_TO_PASS'])+pp;test_patch=swe['test_patch']
        if kind=='requests':
            from p6_requests_main_fixture import fixture
            argv=[str(prefix/'bin/python'),'-B','/opt/workbench/source/p6_requests_runner.py','--frozen-selection',json.dumps(expected),'-q','-o','addopts=',
                  '-p','no:cacheprovider','--junitxml={junit}']
            visible=[*argv];visible[4]=json.dumps(pp);context=fixture()
        elif kind=='pytest':
            # setuptools-scm emits this ignored source file when installing.
            # Provide the exact public build artifact to both visible and hidden runs.
            hidden['src/_pytest/_version.py']=(prefix/'lib/python3.9/site-packages/_pytest/_version.py').read_bytes()
            argv=[str(prefix/'bin/python'),'-B','/opt/workbench/source/p6_pytest_runner.py',json.dumps(expected),
                  '-q','-o','addopts=','-p','pytester','-p','no:cacheprovider','--junitxml={junit}']
            visible=[*argv];visible[3]=json.dumps(pp);context=None
        else:
            framework='sympy'
            paths=sorted(set(re.findall(r'^\+\+\+ b/(\S+)',swe['test_patch'],re.MULTILINE)))
            if not paths or any(not re.fullmatch(r'sympy/(?:[A-Za-z0-9_]+/)*tests/test_[A-Za-z0-9_]+\.py',p) for p in paths):
                raise ValueError('Unexpected SymPy native test target')
            argv=[str(prefix/'bin/python'),'-B','/opt/workbench/source/p6_sympy_runner.py',json.dumps(expected),json.dumps(paths)]
            visible=[*argv];visible[3]=json.dumps(pp);context=None
        prompt=swe['problem_statement']
    from contextlib import nullcontext
    with context or nullcontext(None) as url:
        writable=['tests/data/python37.py'] if tid=='BIP-black-6' else []
        kwargs={'expected_tests':expected,'test_patch':test_patch,'test_framework':framework,'writable_fixture_paths':writable}
        if url:
            from p6_requests_main_fixture import CA
            kwargs.update(fixture_url=url,tls_regressions=True,fixture_ca=CA)
            # Session.send in Requests 2.3 does not merge REQUESTS_CA_BUNDLE.
            # Its bundled trust data needs the same scoped fixture certificate.
            # Apply this public data overlay equally to buggy/gold/candidate copies.
            hidden['requests/cacert.pem']=CA.read_bytes()
        controls={name:evaluate(path,prefix,argv,hidden,timeout=180,**kwargs) for name,path in [('buggy',source),('gold',gold)]}
    passed=controls['gold']['verdict']=='PASS' and controls['buggy']['verdict']=='FAIL'
    result={'task_id':tid,'status':'EVALUATOR_VALIDATED' if passed else 'INFRA_FAIL',
            'base_commit':task['base_commit'],'prefix':str(prefix),'gold':str(gold),'test_framework':framework,
            'argv':argv,'visible':visible,'visible_expected':json.loads(swe['PASS_TO_PASS']) if swe else None,
            'hidden_files':list(hidden),'test_patch':test_patch,'expected':expected,'prompt':prompt,
            'writable_fixture_paths':writable,
            'results':controls,'model_requests':0,'elapsed_seconds':time.perf_counter()-tick}
    if passed:result['environment']=seal_environment(prefix,tid+'-main-v1')
    return result


def main():
    payload=json.load(sys.stdin);root=BASE/'private/public-main-preparation'/str(time.time_ns());root.mkdir(parents=True)
    (root/'input.private.json').write_text(json.dumps(payload))
    for task in payload['tasks']:
        tid=task['task_id']
        if not tid.startswith(('BIP-','SWEL-')):continue
        attempt=root/tid;attempt.mkdir()
        try:result=prepare(task,payload['bip'].get(tid),payload['swe'].get(tid),attempt)
        except Exception as error:
            import traceback
            (attempt/'error.private.log').write_text(traceback.format_exc())
            result={'task_id':tid,'status':'INFRA_FAIL','error_type':type(error).__name__,'model_requests':0}
        (attempt/'receipt.private.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:result[k] for k in ('task_id','status','model_requests')}),flush=True)


if __name__=='__main__':main()
