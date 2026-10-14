"""Prepare or launch only the explicitly authorized Black-5 continuation.

Never deploys over frozen /opt/workbench/source, resets the shared ledger, or
dispatches completed DS0/Pool-B/Pool-C. Detached work is finite and non-root.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from wsl_project import ROOT,run
from p6_main_budget import authorization
sys.path.insert(0,str(ROOT/'src'))
from workbench.benchmark import freeze_manifest,digest,check_manifest

FOLDER='/opt/workbench/recovery/black5-continuation-v1'
NAMES=('p6_checkpoint_recovery.py','resume_p6_pool_linux.py')
MANIFEST=ROOT/'configs/benchmark-p6-black5-continuation-v1.json'
ORIGINAL='p6-main-execute-BIP-black-5-20261012T151835Z'


def call(code, data=None, timeout=60):
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],
          input_bytes=json.dumps(data).encode() if data is not None else None,timeout=timeout)
    if r.returncode:
        raise RuntimeError('Native continuation operation failed: '+r.stderr.decode(errors='replace')[-1800:])
    return json.loads(r.stdout)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','offline','execute'))
    args=parser.parse_args()
    mapping={FOLDER+'/'+name:(ROOT/'scripts'/name).read_text(encoding='utf-8') for name in NAMES}
    meta=call(r'''import json,sys,hashlib,math
from pathlib import Path
data=json.load(sys.stdin);folder=Path(data['folder'])
folder.mkdir(parents=True,exist_ok=True)
for name,content in data['mapping'].items():
 p=Path(name)
 if p.exists() and p.read_bytes()!=content.encode():raise ValueError('Existing continuation source is immutable')
 if not p.exists():p.write_bytes(content.encode())
sys.path[:0]=[str(folder),'/opt/workbench/source','/opt/workbench/source/src']
from p6_checkpoint_recovery import inventory,remaining_limits,sha
from p2_candidates import digest
root=Path('/opt/workbench/benchmark/private/main-runs')/data['original']
old=json.loads((root/'control/run-contract.json').read_bytes())
current=json.loads((root.parent/'p6-main-execute-SCI-GRANGER-GPU-20261013T060508Z/control/run-contract.json').read_bytes())
for path,expected in current['source_sha256'].items():
 if sha(path)!=expected:raise ValueError('Native source59 changed')
worker=json.loads((root/'pool-A/controller-outcome.json').read_bytes())
ledger=json.loads(Path('/opt/workbench/state/p6-main-local-20261011/ledger.json').read_bytes())
launch=json.loads((root.parent.parent/'main-launches'/(root.name+'.json')).read_bytes())
debit=math.ceil((root/'failure.json').stat().st_mtime-launch['started_unix'])
bounds=remaining_limits(worker,ledger['requests'],root.name+'/pool-A',900,1000,debit,7200)
print(json.dumps({'source_sha256':{**current['source_sha256'],**{name:sha(name) for name in data['mapping']}},
 'task':old['task'],'gold':old['gold'],'control_receipt_sha256':old['control_receipt_sha256'],
 'original_manifest_sha256':old['manifest']['manifest_sha256'],
 'original_inventory_sha256':digest(inventory(root)),'continuation_limits':bounds,
 'ledger_sha256':sha('/opt/workbench/state/p6-main-local-20261011/ledger.json')}))
''',{'folder':FOLDER,'mapping':mapping,'original':ORIGINAL})
    budget,budget_sha=authorization(ROOT/'configs/budget-p6-main-v6-cash200-approved.json')
    entry_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if args.mode=='prepare':
        body=json.loads((ROOT/'configs/benchmark-p6-v12-cash200.json').read_bytes())
        body.pop('manifest_sha256')
        body.update(runner_source_sha256=meta['source_sha256'],entrypoint_sha256=entry_sha,
            continuation={'original_run':ORIGINAL,'original_manifest_sha256':meta['original_manifest_sha256'],
                          'original_inventory_sha256':meta['original_inventory_sha256'],
                          'limits':meta['continuation_limits'],'kind':'WORKSPACE_CHECKPOINT_NEW_DSH_SESSION',
                          'explicit_human_authorization':'2026-10-14 Resume Pool-A only, preserve completed results; then Pi and P7; same budget, GitHub deferred'})
        value=freeze_manifest(body,MANIFEST)
        print(json.dumps({'status':'FROZEN_NO_MODELS','manifest_sha256':value['manifest_sha256'],'bounds':meta['continuation_limits']}))
        return 0
    body=check_manifest(json.loads(MANIFEST.read_bytes()))
    if (body['runner_source_sha256']!=meta['source_sha256'] or body['entrypoint_sha256']!=entry_sha
            or body['budget_authorization_sha256']!=budget_sha
            or body['continuation']['original_inventory_sha256']!=meta['original_inventory_sha256']
            or body['continuation']['limits']!=meta['continuation_limits']):
        raise ValueError('Frozen source/checkpoint/allowance changed')
    if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).strip():
        raise ValueError('Commit tracked implementation before launching')
    network=None
    if args.mode=='execute':
        network=call("import sys,json;sys.path.insert(0,'/opt/workbench/source');from p6_connection_probe import reconnect_probe;print(json.dumps(reconnect_probe()))",timeout=120)
        if network['verdict']!='PASS':raise RuntimeError('Zero-model network gate failed; no paid launch')
    name='p6-main-'+('execute' if args.mode=='execute' else 'offline')+'-BIP-black-5-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'mode':args.mode,'run_id':name,'original_run':ORIGINAL,'budget':budget,'manifest':body,
             **meta,'entrypoint_sha256':entry_sha,'network_preflight':network,
             'development_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    # This private snapshot intentionally precedes credential access.
    snapshot=ROOT/'.local-workbench/benchmark/source-snapshots'/name
    snapshot.mkdir(parents=True)
    (snapshot/'contract.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    for source in (Path(__file__),*(ROOT/'scripts'/n for n in NAMES)):
        (snapshot/source.name).write_bytes(source.read_bytes())
    if args.mode=='execute':
        import yaml
        credential=Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml'
        payload['key']=yaml.safe_load(credential.read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
        if not isinstance(payload['key'],str) or not payload['key']:raise RuntimeError('Saved credential unavailable')
    else:payload['key']='offline-no-provider'
    total=meta['continuation_limits']['activity_seconds_remaining']+8*180+120
    value=call(r'''import sys,json,subprocess,os,time,hashlib
from pathlib import Path
sys.path[:0]=['/opt/workbench/source','/opt/workbench/source/src']
from p1_broker import protect_memory
protect_memory();data=json.load(sys.stdin);payload=data['payload'];folder=Path('/opt/workbench/benchmark/private/main-launches')
for f in folder.glob('*.json'):
 v=json.loads(f.read_bytes());p=Path('/proc/'+str(v.get('pid',0))+'/stat')
 if p.exists():
  fields=p.read_text().split()
  if fields[2]!='Z' and fields[21]==v.get('process_start_ticks'):raise ValueError('Another owned controller is active')
name=payload['run_id'];receipt=folder/(name+'.json')
if receipt.exists():raise FileExistsError('Prior launch retained')
env=dict(os.environ);env['PYTHONPATH']=data['folder']+':/opt/workbench/source:/opt/workbench/source/src'
command=['timeout','--signal=TERM','--kill-after=5s',str(data['total'])+'s','/opt/workbench/.venv-linux/bin/python','-B',data['folder']+'/resume_p6_pool_linux.py']
with (folder/(name+'.private.log')).open('xb') as log:
 p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
 p.stdin.write(json.dumps(payload).encode());p.stdin.close()
value={'run_id':name,'pid':p.pid,'process_start_ticks':Path('/proc/'+str(p.pid)+'/stat').read_text().split()[21],
 'started_unix':time.time(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'command_sha256':hashlib.sha256(Path('/proc/'+str(p.pid)+'/cmdline').read_bytes()).hexdigest(),
 'timeout_seconds':data['total'],'original_run':payload['original_run'],'automatic_retry':False}
with receipt.open('x') as f:json.dump(value,f,indent=2)
print(json.dumps(value))
''',{'payload':payload,'total':total,'folder':FOLDER},timeout=30)
    payload['key']=''
    with (ROOT/'.local-workbench/audits'/(name+'-launch.private.json')).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2)
    print(json.dumps(value))
    return 0


if __name__=='__main__':
    original=subprocess.run
    def hidden(*args,**kwargs):
        if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
        return original(*args,**kwargs)
    subprocess.run=hidden
    raise SystemExit(main())
