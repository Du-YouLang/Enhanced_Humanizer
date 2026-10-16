"""Freeze, validate and launch the authorized sixteen-task guidance experiment."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from p6_guidance_protocol import TASKS,BRANCHES,PROTOCOL,digest,validate_plan
from p6_main_budget import authorization
from wsl_project import run

INTAKE=ROOT/'.local-workbench/guidance'
BUDGET=ROOT/'configs/budget-p6-main-v10-guidance-approved.json'
OLD=ROOT/'configs/budget-p6-main-v9-cash500-four-redo-approved.json'


def native(code,value,timeout=90):
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps(value).encode(),timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-4000:])
    return json.loads(r.stdout)


def deploy():
    # A new content-addressed snapshot. Old source trees are never overwritten.
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    tracked += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'scripts').glob('*guidance*.py')]
    files={}
    for name in set(tracked):
        if ((name.startswith('scripts/') or name.startswith('src/workbench/')) and name.endswith('.py')):
            relative=name[8:] if name.startswith('scripts/') else name
            files[relative]=(ROOT/name).read_text(encoding='utf8')
    for flow in (ROOT/'.hmz/flows').glob('*/__init__.py'):
        files['flows/'+flow.parent.name+'/__init__.py']=flow.read_text(encoding='utf8')
    files['pi_full_protocol.py']=(ROOT/'benchmarks/pi-comparison/runners/pi_full_protocol.py').read_text(encoding='utf8')
    files['science-clarifications-v1.md']=(ROOT/'benchmarks/pi-comparison/tasks/science-clarifications-v1.md').read_text(encoding='utf8')
    identity=digest({n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()})
    folder='/opt/workbench/guidance/executor-'+identity[:20]
    files={n:raw.replace('/opt/workbench/source',folder) for n,raw in files.items()}
    native('''import json,sys;from pathlib import Path
d=json.load(sys.stdin);root=Path(d['folder']);root.mkdir(parents=True,exist_ok=True)
for n,raw in d['files'].items():
 p=root/n;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and p.read_bytes()!=raw.encode():raise ValueError('Frozen executor changed')
 if not p.exists():p.write_bytes(raw.encode())
print(json.dumps({'status':'DEPLOYED_ZERO_MODELS'}))''',{'folder':folder,'files':files})
    return folder,{folder+'/'+n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()}


def prepare():
    budget,budget_sha=authorization(BUDGET);folder,sources=deploy()
    manifest=json.loads((ROOT/'configs/benchmark-p6-v12-cash200.json').read_bytes())
    run_id='guidance-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive='/opt/workbench/guidance/'+run_id+'-ledger-before.json'
    pins=native('''import hashlib,json,sys;from pathlib import Path
d=json.load(sys.stdin);ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
if hashlib.sha256(ledger.read_bytes()).hexdigest()!='b4b7acaf62b784e4f8879efb6278bbc803a14ae123cfa1cb50ec372b47392421':raise ValueError('Prior ledger changed; reconcile')
paths=[]
for n in ('/opt/workbench/benchmark/private/main-runs','/opt/workbench/benchmark/private/pi-comparison'):
 root=Path(n)
 for p in root.rglob('*.json'):
  if p.name in ('receipt.json','frozen-program.json','frozen-public-pool.json','frozen-expanded-public-pool.json','result.json'):
   paths.append(p)
print(json.dumps({'retained_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
 'ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest()}))''',{})
    plan={'protocol':PROTOCOL,'tasks':list(TASKS),'branches':list(BRANCHES),'effort':'low',
        'shared_initial_ds':True,'mentor_writes_code':False,'hidden_after_both_branches_frozen':True,
        'cumulative_requests':15000,'cumulative_usd':500,'external_release_authorized':False,
        'source_sha256':sources,'retained_sha256':pins['retained_sha256'],'budget':budget,
        'budget_authorization_sha256':budget_sha,'ledger_archive':archive,'manifest':manifest,
        'controls_receipt':'/opt/workbench/benchmark/private/guidance/'+run_id+'-controls/receipt.json',
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'analysis':'Paired one-seed pilot; report initial and both branches, repair/regression counts and provider-separated tokens. Shared-first projections are not additive bills; no equal-token or universal claim.',
        'scientific_acceptance':'Frozen current numeric thresholds plus independent Sol source/report/figure review; no old-result replacement.',
        'recovery':'Completed journal substeps reused, started-without-completion blocked; never automatic model replay.'}
    plan['plan_sha256']=digest(plan);validate_plan(plan)
    payload={'mode':'controls','run_id':run_id,'plan':plan,'budget':budget,'folder':folder}
    INTAKE.mkdir(parents=True,exist_ok=True);path=INTAKE/(run_id+'.private.json')
    with path.open('x',encoding='utf8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    return {'status':'PREPARED_ZERO_MODELS','contract':str(path),'folder':folder,'plan_sha256':plan['plan_sha256'],
            'retained_files':len(pins['retained_sha256'])}


def prepare_recovery(original_path):
    import copy
    old_path=Path(original_path).resolve()
    if not old_path.is_relative_to(INTAKE.resolve()):raise ValueError('Exact private original contract required')
    old=json.loads(old_path.read_bytes());budget,budget_sha=authorization(BUDGET)
    folder,sources=deploy();run_id='guidance-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot=native('''import fcntl,json,sys,hashlib;from pathlib import Path
d=json.load(sys.stdin);sys.path[:0]=[d['folder'],d['folder']+'/src']
from p6_guidance_continuation import ORIGINAL_RUN,PARTIAL_TASK,RETAINED_TASKS,NEW_TASKS,role_order,remaining_partial_roles
from p6_guidance_protocol import digest
from p6_main_budget import MainLedger
import p6_runtime_linux as shared
root=Path('/opt/workbench/benchmark/private/guidance')/ORIGINAL_RUN
boundary=Path('/opt/workbench/guidance')/(ORIGINAL_RUN+'-boundary-stop-20261016.json')
assert json.loads(boundary.read_bytes())['status']=='BOUNDARY_INTERRUPTED_OWNER_EXITED'
with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 ledger=MainLedger('/opt/workbench/state/p6-main-local-20261011/ledger.json',d['budget']);value=json.loads(ledger.path.read_bytes());ledger.validate(value)
 assert {p.name.removesuffix('.completed.json') for p in (root/'stages').glob('*.completed.json')}==set(RETAINED_TASKS)
 stages=root/PARTIAL_TASK/'control/stages';roles=[]
 for role in role_order(PARTIAL_TASK):
  stage='initial' if role=='initial-ds' else role
  if (stages/(stage+'-model.completed.json')).exists():roles.append(role)
 remaining=remaining_partial_roles(roles)
 assert not (stages/'code-tests-ds-model.started.json').exists()
 scope='GUIDANCE/'+ORIGINAL_RUN+'/'+PARTIAL_TASK+'/code-tests-ds'
 assert not any(r['experiment']==scope for r in value['requests']+value['codex_turns'])
 pins={str(boundary):hashlib.sha256(boundary.read_bytes()).hexdigest()}
 paths=[root/'progress.json',*root.glob('receipt-*.json'),*root.glob('*/control/stages/*.json'),
        *root.glob('*/initial-ds/candidate-private.json'),*root.glob('*/*/controller-outcome.json'),*root.glob('*/*/candidate-private.json')]
 for p in paths:pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 programs=[]
 bases={t['task_id']:t['base_commit'] for t in d['original']['plan']['manifest']['tasks']}
 for p in root.glob('*/*/controller-outcome.json'):
  w=json.loads(p.read_bytes());work=Path(w['work']);tid=p.parents[1].name
  patch,source=shared.program_evidence(work,bases[tid])
  programs.append({'work':str(work),'base_commit':bases[tid],'program_sha256':digest({'patch':patch,'source':source}),'scope':w['scope']})
 assert len(programs)==49
 archive=Path('/opt/workbench/guidance')/(d['run_id']+'-ledger-prefix.json')
 with archive.open('xb') as f:f.write(ledger.path.read_bytes())
 pins[str(archive)]=hashlib.sha256(archive.read_bytes()).hexdigest()
 print(json.dumps({'checkpoint_sha256':pins,'model_programs':programs,'ledger_archive':str(archive),
  'retained_sha256':{**d['original']['plan']['retained_sha256'],**d['original']['plan']['source_sha256'],**pins},
  'remaining_partial_roles':remaining,'completed_model_roles':49,'budget_requests':len(value['requests']),
  'budget_subscriptions':len(value['codex_turns']),'budget_bound_usd':value['cash_bound_nano']/1e9,'ledger_sha256':hashlib.sha256(ledger.path.read_bytes()).hexdigest()}))
''',{'folder':folder,'original':old,'run_id':run_id,'budget':budget},timeout=180)
    from p6_guidance_continuation import ORIGINAL_RUN,PARTIAL_TASK,RETAINED_TASKS,NEW_TASKS
    plan=copy.deepcopy(old['plan']);plan.update(source_sha256=sources,retained_sha256=snapshot['retained_sha256'],
        ledger_archive=snapshot['ledger_archive'],budget=budget,budget_authorization_sha256=budget_sha,
        controls_receipt='/opt/workbench/benchmark/private/guidance/'+run_id+'-controls/receipt.json',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        recovery={'revision':'GUIDANCE_HELPER_RECOVERY_20261016','original_run':ORIGINAL_RUN,'original_payload':old,
            'retained_tasks':list(RETAINED_TASKS),'partial_task':PARTIAL_TASK,'new_tasks':list(NEW_TASKS),
            'checkpoint_sha256':snapshot['checkpoint_sha256'],'model_programs':snapshot['model_programs'],
            'remaining_partial_roles':snapshot['remaining_partial_roles'],
            'scientific_claim':'Four SWEL tasks have infrastructure-affected process evidence. Corrected final-code quality is separate, never an equivalent-guidance causal claim.'})
    plan.pop('plan_sha256',None);plan['plan_sha256']=digest(plan);validate_plan(plan)
    payload={'mode':'controls','run_id':run_id,'plan':plan,'budget':budget,'folder':folder}
    path=INTAKE/(run_id+'.private.json')
    with path.open('x',encoding='utf8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    return {'status':'RECOVERY_PREPARED_ZERO_MODELS','contract':str(path),'folder':folder,'plan_sha256':plan['plan_sha256'],
        'retained_models':49,'remaining_original_models':1,'new_task_count':6,'budget':{k:v for k,v in snapshot.items() if k.startswith('budget_')}}


def operate(mode,path):
    payload=json.loads(Path(path).read_bytes());payload['mode']=mode
    folder=payload['folder']
    if mode=='controls':
        return native("import sys,json;sys.path.insert(0,"+repr(folder)+");from p6_guidance_linux import entry;print(json.dumps(entry(json.load(sys.stdin))))",payload,timeout=600)
    # Human budget approval is recorded above; exact successful development CI
    # is a separate prerequisite. The receipt binds this exact functional tree.
    evidence=json.loads((INTAKE/(payload['run_id']+'-ci.private.json')).read_bytes())
    if evidence.get('all_three_success') is not True or evidence.get('plan_sha256')!=payload['plan']['plan_sha256']:
        raise ValueError('Actual exact-source CI receipt required')
    commit=evidence.get('functional_commit','')
    if not __import__('re').fullmatch('[0-9a-f]{40}',commit):raise ValueError('Exact tested functional commit required')
    subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=ROOT,check=True)
    for absolute,expected in payload['plan']['source_sha256'].items():
        name=absolute.removeprefix(folder+'/')
        if name.startswith('flows/'):repository='.hmz/'+name
        elif name=='pi_full_protocol.py':repository='benchmarks/pi-comparison/runners/'+name
        elif name=='science-clarifications-v1.md':repository='benchmarks/pi-comparison/tasks/'+name
        else:repository=name if name.startswith('src/') else 'scripts/'+name
        raw=subprocess.check_output(['git','show',commit+':'+repository],cwd=ROOT).decode('utf8').replace('\r\n','\n')
        if hashlib.sha256(raw.replace('/opt/workbench/source',folder).encode()).hexdigest()!=expected:
            raise ValueError('Native snapshot differs from exact CI source: '+repository)
    source_changed=subprocess.check_output(['git','diff','--name-only','HEAD','--','scripts','.hmz','configs'],cwd=ROOT).strip()
    if source_changed:raise ValueError('Commit exact implementation before launch')
    old=authorization(OLD)[0]
    gate=native('''import sys,json,fcntl,hashlib;from pathlib import Path
d=json.load(sys.stdin);sys.path.insert(0,d['folder']);from p6_main_budget import MainLedger
from p6_guidance_linux import bind
p=d['payload'];bind(p,ledger=False)
control=json.loads(Path(p['plan']['controls_receipt']).read_bytes())
if control['status']!='PASS_GUIDANCE_ZERO_MODEL_CONTROLS' or control['plan_sha256']!=p['plan']['plan_sha256']:raise ValueError('Controls differ')
with Path('/opt/workbench/pi-comparison/full-main-owner.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 ledger=MainLedger('/opt/workbench/state/p6-main-local-20261011/ledger.json',p['budget'])
 archive=Path(p['plan']['ledger_archive'])
 if archive.exists():
  bind(p);result={'status':'EXISTING_AMENDMENT_VERIFIED_NO_RESET'}
 else:result=ledger.amend_authorization(d['old'],archive)
 print(json.dumps({'status':'PRESPEND_PASS','amendment':result,'ledger_sha256':hashlib.sha256(ledger.path.read_bytes()).hexdigest()}))''',{'folder':folder,'payload':payload,'old':old})
    # Only the existing private credential is read, after exact offline gates.
    import yaml
    payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf8'))['refs']['DEEPSEEK_API_KEY']
    launch=native('''import json,sys,subprocess,hashlib,time;from pathlib import Path
d=json.load(sys.stdin);p=d['payload'];folder=d['folder'];root=Path('/opt/workbench/guidance/launches');root.mkdir(parents=True,exist_ok=True)
marker=root/(p['run_id']+'.json')
if marker.exists():raise ValueError('Existing launch; reconcile exact owner/stages before any resume')
controller=('p6_guidance_shutdown_linux.py' if p['plan'].get('shutdown_continuation') else
 'p6_guidance_recover_linux.py' if p['plan'].get('recovery') else 'p6_guidance_linux.py')
command=['/opt/workbench/.venv-linux/bin/python','-B',folder+'/'+controller]
with (root/(p['run_id']+'.private.log')).open('xb') as log:
 child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 child.stdin.write(json.dumps(p).encode());child.stdin.close()
 proc=Path('/proc')/str(child.pid)
 value={'run_id':p['run_id'],'pid':child.pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'process_start_ticks':proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],
 'command_sha256':hashlib.sha256(proc.joinpath('cmdline').read_bytes()).hexdigest(),'folder':folder,
 'plan_sha256':p['plan']['plan_sha256'],'started_unix':time.time(),'automatic_model_replay':False}
 with marker.open('x') as f:json.dump(value,f,indent=2)
 print(json.dumps(value))''',{'folder':folder,'payload':payload})
    payload.pop('key',None)
    result={'status':'ACTUALLY_LAUNCHED','gate':gate,'owner':launch}
    with (INTAKE/(payload['run_id']+'-launch.private.json')).open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    return result


def prepare_shutdown(original_path):
    import copy
    old_path=Path(original_path).resolve()
    if not old_path.is_relative_to(INTAKE.resolve()):raise ValueError('Private original recovery contract required')
    old=json.loads(old_path.read_bytes());budget,budget_sha=authorization(BUDGET)
    folder,sources=deploy();run_id='guidance-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    saved=native('''import json,sys;d=json.load(sys.stdin);sys.path[:0]=[d['folder'],d['folder']+'/src']
from p6_guidance_shutdown_linux import snapshot
print(json.dumps(snapshot(d)))''',{'folder':folder,'run_id':run_id,'original':old,'budget':budget},timeout=180)
    plan=copy.deepcopy(old['plan']);plan.pop('recovery',None)
    retained=saved.pop('retained_sha256')
    plan.update(source_sha256=sources,retained_sha256=retained,budget=budget,budget_authorization_sha256=budget_sha,
        ledger_archive=saved['ledger_archive'],controls_receipt='/opt/workbench/benchmark/private/guidance/'+run_id+'-controls/receipt.json',
        shutdown_continuation=saved,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    plan.pop('plan_sha256',None);plan['plan_sha256']=digest(plan);validate_plan(plan)
    payload={'mode':'controls','run_id':run_id,'plan':plan,'budget':budget,'folder':folder}
    path=INTAKE/(run_id+'.private.json')
    with path.open('x',encoding='utf8') as stream:json.dump(payload,stream,indent=2)
    return {'status':'SHUTDOWN_CONTINUATION_PREPARED_ZERO_MODELS','contract':str(path),'folder':folder,
        'plan_sha256':plan['plan_sha256'],'retained_completed_model_roles':56,'remaining_interrupted_role_seconds':saved['remaining_role_seconds'],
        'new_scientific_tasks':4,'budget':{'requests':saved['old_ledger_requests'],'cash_bound_usd':saved['old_cash_bound_usd']}}


if __name__=='__main__':
    original=subprocess.run
    def hidden(*args,**kwargs):
        if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
        return original(*args,**kwargs)
    subprocess.run=hidden
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','controls','compare'))
    parser.add_argument('--contract');parser.add_argument('--recover-helper-stop',action='store_true')
    parser.add_argument('--resume-user-shutdown',action='store_true');args=parser.parse_args()
    if args.recover_helper_stop and args.mode!='prepare':raise ValueError('Recovery preparation flag only')
    if args.resume_user_shutdown and (args.mode!='prepare' or args.recover_helper_stop):raise ValueError('Exact shutdown preparation flag only')
    print(json.dumps((prepare_shutdown(args.contract) if args.resume_user_shutdown else prepare_recovery(args.contract) if args.recover_helper_stop else prepare()) if args.mode=='prepare' else operate(args.mode,args.contract),ensure_ascii=False))
