# Freeze new-model runtime; paid dispatch remains a separate gate.
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts')]
import run_p6_guidance as old
from p6_main_budget import authorization
from p6_refresh_protocol import TASKS,MODELS,METHODS
from p2_candidates import digest
from wsl_project import run
BUDGET=ROOT/'configs/budget-p6-model-refresh-approved.json'
INTAKE=ROOT/'.local-workbench/model-refresh'


def native(code,payload,timeout=120):
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps(payload).encode(),timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-4000:])
    return json.loads(r.stdout)


def prepare():
    budget,budget_sha=authorization(BUDGET)
    folder,sources=old.deploy()
    run_id='refresh-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot=native(r'''import hashlib,json,sys
from pathlib import Path
base=Path('/opt/workbench/benchmark/private/guidance/guidance-20261016T155938Z')
p=json.loads((base/'plan.json').read_bytes());paths=set(p['source_sha256'])|set(p['retained_sha256'])
for root in ['/opt/workbench/benchmark/private/guidance','/opt/workbench/benchmark/private/pi-comparison','/opt/workbench/benchmark/private/main-runs']:
 for pattern in ['*/receipt*.json','*/progress.json','*/*/result.json','*/arm-*.json','*/frozen-selections.json']:
  for path in Path(root).glob(pattern):paths.add(str(path))
ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
assert hashlib.sha256(ledger.read_bytes()).hexdigest()=='878754e2d22171274ee88a94dafd80f587f3565b9b4c255b59c78021ba2fe07b'
print(json.dumps({'retained_sha256':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},'ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest()}))''',{},timeout=600)
    manifest=json.loads((ROOT/'configs/benchmark-p6-v12-final2.json').read_bytes())
    plan={'protocol':'MODEL_REFRESH_20261126_V1','run_id':run_id,'tasks':list(TASKS),'models':MODELS,'methods':list(METHODS),'budget':budget,
        'manifest':manifest,'budget_authorization_sha256':budget_sha,
        'source_sha256':sources,'retained_sha256':snapshot['retained_sha256'],
        'prior_ledger_sha256':snapshot['ledger_sha256'],
        'ledger_archive':'/opt/workbench/model-refresh-20261126/'+run_id+'-ledger-before.json',
        'controls_receipt':'/opt/workbench/benchmark/private/model-refresh/'+run_id+'-controls/receipt.json',
        'codex_binary_directory':'/opt/workbench/model-refresh-20261126/tools/codex-0.172.0',
        'codex_binary_sha256':'ad83b94c093f0cdd8176a6bc8005a461bdf23a759863e157d40f562b8a9d664d',
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'effort':'low','builder_pool_concurrency':3,'public_gpu_acceptance_concurrency':1,'request_output_tokens':256000,'request_timeout_seconds':600,
        'reviewer_and_judges':'fixed-gpt-6.1-sol','matched_control':'one official session six bounded turns; match total model-active-time ceiling, actual tokens/requests/costs reported separately',
        'resource_matching_axis':'TOTAL_MODEL_ACTIVE_SECONDS_CEILING',
        'openai_wire_request_counts':'unavailable unless official Harness telemetry exposes them; no exact equal-wire-count claim',
        'scientific_review_required':True,'old_result_replay':False,'external_release_authorized':False}
    plan['plan_sha256']=digest(plan)
    payload={'mode':'controls','run_id':run_id,'plan':plan,'budget':budget,'folder':folder}
    INTAKE.mkdir(parents=True,exist_ok=True);path=INTAKE/(run_id+'.private.json')
    with path.open('x',encoding='utf8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    return {'status':'PREPARED_ZERO_MODELS','contract':str(path),'folder':folder,'plan_sha256':plan['plan_sha256'],'retained_pins':len(plan['retained_sha256'])}


def controls(path):
    payload=json.loads(Path(path).read_bytes());payload['mode']='controls'
    result=native("import json,sys;v=json.load(sys.stdin);sys.path[:0]=[v['folder'],v['folder']+'/src'];from p6_refresh_linux import entry;print(json.dumps(entry(v)))",payload,timeout=2400)
    receipt=Path(path).with_name(Path(path).stem+'-controls.private.json')
    receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result


def verify_ci_and_source(payload):
    commit=payload['plan']['source_commit'];folder=payload['folder']
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=commit:
        raise ValueError('Freeze after committing the exact source')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT).strip():
        raise ValueError('Tracked working tree differs from committed source')
    for absolute,expected in payload['plan']['source_sha256'].items():
        name=absolute.removeprefix(folder+'/')
        if name.startswith('flows/'):repository='.hmz/'+name
        elif name=='pi_full_protocol.py':repository='benchmarks/pi-comparison/runners/'+name
        elif name=='science-clarifications-v1.md':repository='benchmarks/pi-comparison/tasks/'+name
        else:repository=name if name.startswith('src/') else 'scripts/'+name
        raw=subprocess.check_output(['git','show',commit+':'+repository],cwd=ROOT).decode('utf8').replace('\r\n','\n')
        if hashlib.sha256(raw.replace('/opt/workbench/source',folder).encode()).hexdigest()!=expected:
            raise ValueError('Frozen snapshot differs from exact CI commit: '+repository)
    env=os.environ|{'HTTPS_PROXY':'http://127.0.0.1:7897','HTTP_PROXY':'http://127.0.0.1:7897','GH_PROMPT_DISABLED':'1'}
    response=subprocess.run(['gh','api','repos/Du-YouLang/Enhanced_Humanizer/commits/'+commit+'/check-runs'],
        env=env,cwd=ROOT,capture_output=True,text=True,check=True)
    checks=json.loads(response.stdout)['check_runs'];required=('integrity','secrets','linux-budget')
    selected=[]
    for name in required:
        rows=[r for r in checks if r['name']==name and r['head_sha']==commit]
        if not rows:raise ValueError('Exact CI missing: '+name)
        row=max(rows,key=lambda r:r['id'])
        if row['status']!='completed' or row['conclusion']!='success':raise ValueError('Exact CI not successful: '+name)
        selected.append({'name':name,'id':row['id'],'conclusion':row['conclusion'],'html_url':row['html_url']})
    return {'functional_commit':commit,'all_three_success':True,'checks':selected,'plan_sha256':payload['plan']['plan_sha256']}


def launch(path):
    path=Path(path).resolve()
    if not path.is_relative_to(INTAKE.resolve()):raise ValueError('Exact local private contract required')
    payload=json.loads(path.read_bytes());ci=verify_ci_and_source(payload)
    payload['mode']='compare';payload['previous_budget']=authorization(ROOT/'configs/budget-p6-main-v10-guidance-approved.json')[0]
    folder=payload['folder']
    # Check frozen Linux controls and budget without reading any credential.
    native("import sys,json;v=json.load(sys.stdin);sys.path[:0]=[v['folder'],v['folder']+'/src'];from p6_refresh_linux import prelaunch;print(json.dumps(prelaunch(v)))",payload,timeout=600)
    import yaml
    payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf8'))['refs']['DEEPSEEK_API_KEY']
    code="""import sys;sys.path.insert(0,"""+repr(folder)+""");from p1_broker import protect_memory;protect_memory()
import json,subprocess,time,hashlib
from pathlib import Path
v=json.load(sys.stdin);folder=v['folder'];root=Path('/opt/workbench/model-refresh-20261126/launches');root.mkdir(parents=True,exist_ok=True)
marker=root/(v['run_id']+'.json')
if marker.exists():raise ValueError('Existing launch: reconcile owner/journal; never replay automatically')
command=['/opt/workbench/.venv-linux/bin/python','-B',folder+'/p6_refresh_linux.py']
with (root/(v['run_id']+'.private.log')).open('xb') as log:
 child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 child.stdin.write(json.dumps(v).encode());child.stdin.close()
 from p6_refresh_observer import owner_identity
 owner=owner_identity(child.pid)
 value={'status':'DISPATCHED_OWNER_HEARTBEAT_VERIFICATION_REQUIRED','owner':owner,'run_id':v['run_id'],'folder':folder,'plan_sha256':v['plan']['plan_sha256'],'started_unix':time.time(),'automatic_model_replay':False}
 with marker.open('x') as f:json.dump(value,f,indent=2)
 print(json.dumps(value))
"""
    try:receipt=native(code,payload)
    finally:payload.pop('key',None)
    receipt['exact_ci']=ci
    with path.with_name(path.stem+'-launch.private.json').open('x',encoding='utf8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','controls','launch']);p.add_argument('--contract');a=p.parse_args()
    result=prepare() if a.action=='prepare' else controls(a.contract) if a.action=='controls' else launch(a.contract)
    print(json.dumps(result,ensure_ascii=False))
