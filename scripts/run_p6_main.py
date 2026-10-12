"""New main-phase entry; never opens or spends the closed smoke ledger."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from wsl_project import ROOT,run
from p6_main_budget import authorization


def deploy():
    from run_p6_smoke import SCRIPTS
    files=set(SCRIPTS)|{p.name for p in (ROOT/'scripts').glob('p6_*.py')}
    mapping={f'/opt/workbench/source/{name}':(ROOT/'scripts'/name).read_text(encoding='utf-8') for name in sorted(files)}
    for name in ('p0_coding_demo','sol_synthesis','sol_judge','benchmark_candidates'):
        mapping[f'/opt/workbench/source/flows/{name}/__init__.py']=(ROOT/'.hmz/flows'/name/'__init__.py').read_text(encoding='utf-8')
    for name in ('__init__.py','benchmark.py','science.py'):
        mapping['/opt/workbench/source/src/workbench/'+name]=(ROOT/'src/workbench'/name).read_text(encoding='utf-8')
    code=r'''import json,sys
from pathlib import Path
for receipt in Path('/opt/workbench/benchmark/private/main-launches').glob('*.json'):
 value=json.loads(receipt.read_text());stat=Path('/proc/'+str(value['pid'])+'/stat')
 if stat.exists():
  fields=stat.read_text().split()
  if fields[2]!='Z' and fields[21]==value['process_start_ticks']:
   raise RuntimeError('Refuse source deployment during an owned active main controller: '+value['run_id'])
for name,value in json.load(sys.stdin).items():
 p=Path(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
print('Main adapters deployed; no inference')'''
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps(mapping).encode())
    if r.returncode:raise RuntimeError('Main deployment failed')
    return {name:hashlib.sha256(value.encode()).hexdigest() for name,value in mapping.items()}


def preparation(task_id):
    if task_id.startswith('SCI-'):
        code="import json,sys;from pathlib import Path;p=Path('/opt/workbench/benchmark/science/private/main-science-preparation-v1')/(sys.argv[1]+'.json');v=json.loads(p.read_text());print(json.dumps({'science':v,'gold':None,'control_receipt_sha256':__import__('hashlib').sha256(p.read_bytes()).hexdigest()}))"
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code,task_id])
        if r.returncode:raise RuntimeError('Scientific baseline not prepared')
        return json.loads(r.stdout)
    code=r'''import json,sys,hashlib
from pathlib import Path
base=Path('/opt/workbench/benchmark')
v=json.loads((base/'science/private/public-main-controls-frozen-v2.json').read_text())
entry=next(r for r in v['tasks'] if r['task_id']==sys.argv[1]);p=Path(entry['receipt'])
if hashlib.sha256(p.read_bytes()).hexdigest()!=entry['receipt_sha256']:raise RuntimeError('Control changed')
r=json.loads(p.read_text());print(json.dumps({'gold':r['gold'],'control_receipt_sha256':entry['receipt_sha256']}))
'''
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code,task_id])
    if r.returncode:raise RuntimeError('Missing task controls')
    return json.loads(r.stdout)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('deploy','offline','execute','sensitivity'))
    p.add_argument('--reuse-run')
    p.add_argument('--detach',action='store_true',help='Finite owned Linux controller, independent of the chat command lifetime')
    p.add_argument('--task',default='BIP-black-2');p.add_argument('--manifest',default='configs/benchmark-p6-v3.json')
    args=p.parse_args();config,_=authorization(ROOT/'configs/budget-p6-main-approved.json')
    source=deploy()
    if args.mode=='deploy':print(json.dumps({'status':'DEPLOYED','model_requests':0}));return 0
    manifest_path=ROOT/args.manifest
    if args.mode=='offline' and not manifest_path.exists():
        # An offline control is not a frozen main model result.
        manifest=json.loads((ROOT/'configs/benchmark-p6-v2.json').read_text());manifest.pop('manifest_sha256')
        manifest.update(protocol_version=3,common_generation_timeout_seconds=115)
        sys.path.insert(0,str(ROOT/'src'));from workbench.benchmark import digest
        manifest['manifest_sha256']=digest(manifest)
    else:manifest=json.loads(manifest_path.read_text())
    task=next(t for t in manifest['tasks'] if t['task_id']==args.task)
    if args.mode in ('execute','sensitivity'):
        if manifest.get('runner_source_sha256')!=source or manifest.get('entrypoint_sha256')!=hashlib.sha256((ROOT/'scripts/run_p6_main.py').read_bytes()).hexdigest():
            raise RuntimeError('Executable source differs from the frozen main protocol')
        if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():
            raise RuntimeError('Commit and validate source before paid execution')
        gate=r'''import json
from pathlib import Path
p=Path('/opt/workbench/benchmark/science/private/pc-calibration-20261012-v1/status.json');v=json.loads(p.read_text())
if v['status']!='PASS_LOCAL_CALIBRATION' or not v['calibration']['tolerances_frozen_before_candidate_generation']:raise RuntimeError('PC local calibration gate not passed')
print('PC calibration PASS')'''
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',gate])
        if r.returncode:raise RuntimeError('User requested PC calibration before main execution')
    run_id='p6-main-'+args.mode+'-'+args.task+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    prep=preparation(args.task)
    if args.mode=='offline' and args.task.startswith('SCI-'):
        # The offline contract is provisional and cannot produce model results.
        task['base_commit']=prep['science']['base_commit']
        task.setdefault('gold_sha256',prep['control_receipt_sha256'])
        body=dict(manifest);body.pop('manifest_sha256');
        sys.path.insert(0,str(ROOT/'src'));from workbench.benchmark import digest
        manifest['manifest_sha256']=digest(body)
    entry=(ROOT/'scripts/run_p6_main.py').read_bytes()
    payload={'mode':args.mode,'phase':config['phase'],'budget':config,'manifest':manifest,'task':task,
             'entrypoint_sha256':hashlib.sha256(entry).hexdigest(),
             'development_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
             'run_id':run_id,'source_sha256':source,'gold':prep['gold'],'control_receipt_sha256':prep['control_receipt_sha256']}
    if args.mode=='sensitivity':payload['reuse_run']=args.reuse_run
    snapshot=ROOT/'.local-workbench/benchmark/source-snapshots'/run_id;snapshot.mkdir(parents=True)
    (snapshot/'scripts').mkdir();(snapshot/'scripts/run_p6_main.py').write_bytes(entry)
    for name,expected in source.items():
        if '/flows/' in name:relative=Path('.hmz/flows')/name.split('/flows/')[1]
        elif '/src/workbench/' in name:relative=Path('src/workbench')/name.split('/src/workbench/')[1]
        else:relative=Path('scripts')/Path(name).name
        data=(ROOT/relative).read_text(encoding='utf-8').encode()
        if hashlib.sha256(data).hexdigest()!=expected:raise RuntimeError('Source changed before execution')
        target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (snapshot/'contract.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    if args.mode in ('execute','sensitivity'):
        import yaml
        credential=Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml'
        payload['key']=yaml.safe_load(credential.read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
        if not isinstance(payload['key'],str) or not payload['key']:raise RuntimeError('Saved credential unavailable')
    else:payload['key']='offline-no-key'
    raw=json.dumps(payload).encode();payload['key']='';started=time.perf_counter()
    # Bounded public task: 1200 seconds of activity plus six independent 180s
    # acceptances and startup. Scientific entry has separate per-task deadlines.
    evaluation=config['scientific_evaluation_timeout_seconds'].get(args.task,180)
    total=1200+6*evaluation+120
    if args.detach:
        launcher=r'''import json,sys,os,subprocess,time
from pathlib import Path
sys.path.insert(0,'/opt/workbench/source');from p1_broker import protect_memory
protect_memory();payload=json.load(sys.stdin);name=payload['run_id']
folder=Path('/opt/workbench/benchmark/private/main-launches');folder.mkdir(parents=True,exist_ok=True)
receipt=folder/(name+'.json')
if receipt.exists():raise RuntimeError('Existing launch cannot be overwritten')
env=dict(os.environ);env['PYTHONPATH']='/opt/workbench/source:/opt/workbench/source/src'
with (folder/(name+'.private.log')).open('xb') as log:
 p=subprocess.Popen(['timeout','--signal=TERM','--kill-after=5s',sys.argv[1]+'s','/opt/workbench/.venv-linux/bin/python','-B','/opt/workbench/source/p6_main_runtime_linux.py'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
 p.stdin.write(json.dumps(payload).encode());p.stdin.close()
value={'run_id':name,'pid':p.pid,'process_start_ticks':Path('/proc/'+str(p.pid)+'/stat').read_text().split()[21],'timeout_seconds':int(sys.argv[1]),'started_unix':time.time(),'automatic_retry':False}
receipt.write_text(json.dumps(value,indent=2));print(json.dumps(value))
'''
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',launcher,str(total)],input_bytes=raw,timeout=30);raw=b''
        (ROOT/'.local-workbench/audits'/(run_id+'-launch.private.log')).write_bytes(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('Detached controller launch failed')
        print(r.stdout.decode(),flush=True);return 0
    r=run(['timeout','--signal=TERM','--kill-after=5s',str(total)+'s','/opt/workbench/.venv-linux/bin/python','-B',
           '/opt/workbench/source/p6_main_runtime_linux.py'],input_bytes=raw,timeout=total+30);raw=b''
    log=ROOT/'.local-workbench/audits'/(run_id+'.private.log');log.write_bytes(r.stdout+r.stderr)
    print(json.dumps({'run_id':run_id,'exit_code':r.returncode,'windows_elapsed_seconds':time.perf_counter()-started,'log':str(log)}),flush=True)
    if r.returncode:print(r.stderr.decode(errors='replace')[-2000:])
    else:print(r.stdout.decode(errors='replace')[-1500:])
    return r.returncode


if __name__=='__main__':raise SystemExit(main())
