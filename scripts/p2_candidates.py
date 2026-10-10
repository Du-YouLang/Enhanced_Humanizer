"""Task-level candidate records, independent clones, frozen acceptance and process isolation."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from p1_fixture import TASK, TESTS, SOURCE

def git(root,*args):
    return subprocess.check_output(["git",*args],cwd=root,stderr=subprocess.STDOUT).decode().strip()
from p1_acceptance import verification_command

BASE=Path('/opt/workbench')
RUBRIC={'version':'p2-smoke-v1','dimensions':['correctness','robustness','maintainability'],
        'rule':'Cite frozen tests or code evidence. Scores never override failed hard acceptance.'}
EXTRA='''
class TestIndependent(unittest.TestCase):
    def test_zero_weight(self): self.assertEqual(weighted_mean([(999,0),(7,2)]),7)
    def test_fractional(self): self.assertAlmostEqual(weighted_mean([(1,.5),(5,1.5)]),4)
'''


def digest(value):
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()


def exclusive_json(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())


def namespace_command(argv):
    # Mount proc while unshare holds namespace setup capabilities; exec at uid 1000
    # drops effective capabilities. Never map the agent to root, even inside the namespace.
    return ['unshare','--user','--map-current-user','--mount','--pid','--fork','--mount-proc',
            '--kill-child=KILL','setpriv','--no-new-privs',*argv]


def candidate_env(root):
    root=Path(root)
    homes={key:root/name for key,name in {'HOME':'home','HUMANIZE_HOME':'humanize','DSH_HOME':'dsh',
          'XDG_CACHE_HOME':'cache','PKG_NATIVE_CACHE_PATH':'cache/pkg','TMPDIR':'tmp'}.items()}
    for path in homes.values():path.mkdir(parents=True,exist_ok=True)
    env={k:v for k,v in os.environ.items() if k not in ('CODEX_HOME','DEEPSEEK_API_KEY','DEEPSEEK_BASE_URL')}
    env.update({k:str(v) for k,v in homes.items()})
    env.update(HUMANIZE_SENTRY='off',PYTHONDONTWRITEBYTECODE='1',GIT_TERMINAL_PROMPT='0')
    return env


def prepare(root,n,contract=None):
    if n not in (1,3,4,5):raise ValueError('N must be 1, 3, 4 or 5')
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    frozen=Path(contract['base_repository']) if contract else BASE/'source/p1-frozen-fixture'
    if not frozen.is_dir() or (contract is None and ((frozen/'weighted_stats.py').read_text()!=SOURCE or (frozen/'test_weighted_stats.py').read_text()!=TESTS)):
        raise RuntimeError('Frozen fixture missing or changed')
    base=git(frozen,'rev-parse','HEAD')
    if contract and (base!=contract['base_commit'] or git(frozen,'status','--porcelain')):
        raise RuntimeError('Prepared base commit is not the frozen clean contract base')
    descriptors=[]
    for index in range(n):
        cid=chr(ord('A')+index)
        attempt=root/cid;attempt.mkdir()
        work=attempt/'worktree'
        git(BASE,'clone','--no-local',str(frozen),str(work))
        git(work,'remote','remove','origin')
        git(work,'config','user.name','Workbench Candidate')
        git(work,'config','user.email','candidate@example.invalid')
        branch='run/p2/'+root.name+'/'+cid
        git(work,'switch','-c',branch)
        if (work/'.git/objects/info/alternates').exists():raise RuntimeError('Shared Git object stores forbidden')
        if contract and any(digest(safe_source(work,name).encode())!=sha for name,sha in contract['protected_files'].items()):
            raise RuntimeError('Protected base files do not match the frozen contract')
        job={'id':cid,'root':str(attempt),'work':str(work),'branch':branch,'base_commit':base}
        if contract:job['task_contract']=contract
        descriptors.append(job)
    return base,descriptors


def safe_git(work,*args):
    argv=['git','--no-optional-locks','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',
          '-c','core.pager=cat',*args]
    p=subprocess.run(namespace_command(verification_command(work,argv,Path(work).parent/'verify-tmp')),cwd=work,
                     capture_output=True,text=True,timeout=15)
    if p.returncode:raise RuntimeError('Fenced Git evidence unavailable')
    return p.stdout.strip()


def run_tests(work,*,independent=False,timeout=15,contract=None):
    code=contract['acceptance_test_program' if independent else 'visible_test_program'] if contract else TESTS+(EXTRA if independent else '')+'\nunittest.main(verbosity=2)\n'
    tick=time.perf_counter()
    try:
        p=subprocess.run(namespace_command(verification_command(work,[sys.executable,'-B','-c',code],Path(work).parent/'verify-tmp')),
                         cwd=work,capture_output=True,text=True,timeout=timeout)
        return {'verdict':'PASS' if p.returncode==0 else 'FAIL','exit_code':p.returncode,
                'elapsed_seconds':round(time.perf_counter()-tick,6),'log':p.stderr+p.stdout,
                'suite_sha256':digest(code.encode()),'tests_expected':'contract-defined' if contract else (7 if independent else 5)}
    except subprocess.TimeoutExpired:
        return {'verdict':'TIMEOUT','exit_code':'unavailable','elapsed_seconds':round(time.perf_counter()-tick,6),
                'suite_sha256':digest(code.encode()),'tests_expected':7 if independent else 5,'log':'Frozen tester timed out'}


def safe_source(work,name='weighted_stats.py'):
    path=Path(work)/name
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(Path(work).resolve()):
        raise RuntimeError('Candidate source is not a local regular file')
    if path.stat().st_size>100_000:raise RuntimeError('Candidate source exceeds evidence limit')
    return path.read_bytes().decode('utf-8')


def finalize(job,worker,timeline,queued_seconds,lock_hash):
    work=Path(job['work']);tick=time.perf_counter()
    contract=job.get('task_contract')
    manifest={k:job[k] for k in ('id','branch','base_commit')}
    manifest.update(schema_version=1,kind=worker.get('kind','INFRASTRUCTURE_ATTEMPT'),
                    model_id='deepseek-flash',harness='official DSH 0.1.5rc1 via Humanize 0.1.0b2',
                    env_hash=lock_hash,prompt_hash=digest((contract['prompt'] if contract else TASK).encode()),timeline=timeline,
                    queue_seconds=queued_seconds,session_id=worker.get('session_id','unavailable'),
                    tool_trace=worker.get('tool_trace','unavailable'),worker_status=worker.get('status','INFRA_FAIL'),
                    known_failures=[],tokens='unavailable',api_bill_usd='unavailable')
    try:
        manifest['head_commit']=safe_git(work,'rev-parse','HEAD')
        manifest['patch']=safe_git(work,'diff','--no-ext-diff','--no-textconv',job['base_commit'],manifest['head_commit'])
        manifest['working_tree']=safe_git(work,'status','--porcelain')
        source_file=contract['source_file'] if contract else 'weighted_stats.py'
        missing_source=not (work/source_file).exists()
        manifest['source']='unavailable' if missing_source else safe_source(work,source_file)
        unchanged=all(digest(safe_source(work,name).encode())==sha for name,sha in contract['protected_files'].items()) if contract else safe_source(work,'test_weighted_stats.py')==TESTS
        no_alternates=not (work/'.git/objects/info/alternates').exists()
        manifest['test_report']=run_tests(work,independent=True,contract=contract)
        status=worker.get('status','INFRA_FAIL')
        if status!='COMPLETED':manifest['verdict']=status
        elif missing_source or not unchanged or not no_alternates:manifest['verdict']='FAIL'
        elif manifest['test_report']['verdict']!='PASS':manifest['verdict']=manifest['test_report']['verdict']
        elif manifest['head_commit']==job['base_commit'] or not manifest['patch'] or manifest['working_tree']:
            manifest['verdict']='FAIL'
        else:manifest['verdict']='PASS'
        manifest['frozen_test_unchanged']=unchanged
        manifest['independent_object_store']=no_alternates
        manifest['turns']=worker.get('turns',[])
        if manifest['verdict']!='PASS':manifest['known_failures'].append('Inspect worker status and frozen test report')
    except Exception as error:
        manifest.update(verdict='INFRA_FAIL',error_type=type(error).__name__)
        manifest['known_failures'].append('Candidate evidence failed closed')
    manifest['verification_seconds']=round(time.perf_counter()-tick,6)
    return manifest


def failure_report(candidates):
    from collections import Counter
    passed=[c['id'] for c in candidates if c['verdict']=='PASS']
    infra=[c['id'] for c in candidates if c['verdict'] in ('INFRA_FAIL','BUDGET_EXHAUSTED')]
    verdicts={c['verdict'] for c in candidates}
    status='PASS' if passed else ('TIMEOUT' if verdicts=={'TIMEOUT'} else
           ('BUDGET_EXHAUSTED' if verdicts=={'BUDGET_EXHAUSTED'} else ('INDETERMINATE' if infra else 'FAIL')))
    return {'status':status,'successful_candidates':passed,'all_failed':not passed,
            'infrastructure_failures':infra,
            'failures':[{'id':c['id'],'verdict':c['verdict'],'known_failures':c.get('known_failures',[]),
                         'head_commit':c.get('head_commit','unavailable'),
                         'reproduce':'Replay the frozen suite at the archived commit in the same locked environment',
                         'partial_results':{'patch_available':bool(c.get('patch')),'test_report':c.get('test_report',{})}}
                        for c in candidates if c['verdict']!='PASS'],
            'failure_categories':dict(Counter(c['verdict'] for c in candidates if c['verdict']!='PASS')),
            'common_test_failures':dict(Counter(line for c in candidates for line in c.get('test_report',{}).get('log','').splitlines()
                                               if line.startswith(('FAIL:','ERROR:')))),
            'common_defects':'Program-observed frozen-test signatures only; no model diagnosis inferred',
            'next_action':'Independent Reviewer may attempt M in P3; failed candidates remain archived' if not passed else 'Review passing candidates',
            'best_failure_is_success':False}


def freeze(root,candidates,base,lock_hash,contract=None):
    prompt=contract['prompt'] if contract else TASK
    pool={'schema_version':1,'task_contract':prompt,'task_hash':digest(prompt.encode()),'base_commit':base,
          'env_hash':lock_hash,'rubric':RUBRIC,'rubric_hash':digest(RUBRIC),'candidates':candidates,
          'failure_report':failure_report(candidates)}
    if contract:pool['contract_manifest']=contract
    pool['pool_hash']=digest(pool)
    exclusive_json(Path(root)/'frozen-pool.json',pool)
    return pool


def validate_pool(pool):
    value=dict(pool);claimed=value.pop('pool_hash')
    if digest(value)!=claimed or digest(pool['rubric'])!=pool['rubric_hash']:
        raise ValueError('Frozen pool or rubric changed')
    ids=[c['id'] for c in pool['candidates']]
    if len(set(ids))!=len(ids) or len(ids) not in (1,3,4,5):raise ValueError('Invalid candidate pool')
    for c in pool['candidates']:
        if c['base_commit']!=pool['base_commit'] or c['env_hash']!=pool['env_hash'] or c['prompt_hash']!=pool['task_hash']:
            raise ValueError('Candidate contract/base/environment mismatch')
    return pool
