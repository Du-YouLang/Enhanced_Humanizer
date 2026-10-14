"""Content-addressed, project-local Pi controls and explicitly authorized comparison."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from wsl_project import run
from p6_main_budget import authorization


def deploy():
    paths=[Path(__file__).with_name(n) for n in ('pi_session.mjs','pi_formal_linux.py','events.py','pi_protocol.py')]
    paths += [ROOT/'scripts'/n for n in ('p6_checkpoint_recovery.py','p6_gc_adjudication.py','p6_gc_dependencies.py',
              'p6_gc_grader.py','p6_gc_source_policy.py','p6_science_main_linux.py','p6_gc_worker.py')]
    sources={p.name:p.read_text(encoding='utf-8') for p in paths}
    hashes={name:hashlib.sha256(raw.encode()).hexdigest() for name,raw in sources.items()}
    tag=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:16]
    folder='/opt/workbench/pi-comparison/controller-formal-'+tag
    code="""import json,sys;from pathlib import Path
d=json.load(sys.stdin);folder=Path(d['folder']);folder.mkdir(exist_ok=True)
for name,content in d['sources'].items():
 p=folder/name
 if p.exists() and p.read_bytes()!=content.encode():raise ValueError('Content-addressed source changed')
 if not p.exists():p.write_bytes(content.encode())
print(json.dumps({'status':'DEPLOYED_ZERO_MODELS'}))
"""
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps({'folder':folder,'sources':sources}).encode(),timeout=30)
    if r.returncode:raise RuntimeError('Independent comparator deployment failed')
    return folder,{folder+'/'+name:h for name,h in hashes.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('controls','prepare','tools','compare'));p.add_argument('--detach',action='store_true');a=p.parse_args()
    budget,budget_sha=authorization(ROOT/'configs/budget-p6-main-v6-cash200-approved.json')
    folder,source=deploy()
    plan_path=ROOT/'benchmarks/pi-comparison/formal-plan-v2.json'
    if a.mode=='prepare':
        sys.path.insert(0,str(ROOT/'src'))
        from workbench.benchmark import digest,check_manifest
        manifest=json.loads((ROOT/'configs/benchmark-p6-v12-cash200.json').read_bytes());check_manifest(manifest)
        plan={'schema_version':1,'protocol':'PI_FORMAL_20261014_V1','source_sha256':source,
              'entrypoint_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'budget_authorization_sha256':budget_sha,'cash_aggregation':'Original cumulative USD200/10000 requests; no new allowance',
              'main_manifest':manifest,'bulk_256_enabled':False,'external_release_authorized':False,
              'cells':[{'task_id':tid,'profile':profile,'provider':provider,'repetition':0}
                       for tid in ('BIP-black-2','SCI-GRANGER-GPU') for provider in ('deepseek','subscription') for profile in ('P0','P1','P2','P3')],
              'independent_acceptance':'Original P6 oracle plus explicit GC source review; numerical thresholds unchanged',
              'subscription_measurement_limit':'SDK dispatches verified, provider-internal wire count unavailable',
              'reasoning':'Requested low on both models; DeepSeek wire enabled/low matches actual zero-model DSH control',
              'recovery':'Preserve completed rows and started uncertain stages, no automatic model replay'}
        plan['plan_sha256']=digest(plan)
        if plan_path.exists() and json.loads(plan_path.read_bytes())!=plan:raise ValueError('Existing Pi plan is immutable')
        if not plan_path.exists():plan_path.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':'FROZEN_NO_MODELS','plan_sha256':plan['plan_sha256'],'cells':16}));return 0
    paid=a.mode in ('tools','compare')
    if paid:
        # Caller scopes are already explicitly authorized; still bind clean code
        # and exact quiet native ownership before reading even one credential.
        if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).strip():raise RuntimeError('Commit comparator implementation before paid launch')
        code="import sys,json;sys.path.insert(0,"+repr(folder)+");from pi_formal_linux import quiet;quiet();print(json.dumps({'status':'QUIET'}))"
        q=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],timeout=30)
        if q.returncode:raise RuntimeError('Active main work; Pi paid execution remains serial')
    name={'controls':'formal-controls-','tools':'formal-live-tools-','compare':'formal-compare-'}[a.mode]+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'mode':a.mode,'run_id':name,'budget':budget,'source_sha256':source}
    dest=ROOT/'.local-workbench/pi-comparison/intake';dest.mkdir(exist_ok=True)
    if paid:
        sys.path.insert(0,str(ROOT/'src'))
        from workbench.benchmark import digest
        plan=json.loads(plan_path.read_bytes());body=dict(plan);expected=body.pop('plan_sha256')
        if (digest(body)!=expected or plan['source_sha256']!=source or plan['budget_authorization_sha256']!=budget_sha
                or plan['entrypoint_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
            raise ValueError('Frozen Pi plan/source/authorization differs')
        payload['plan']=plan
        probe="import json,sys;sys.path.insert(0,'/opt/workbench/source');from p6_connection_probe import reconnect_probe;print(json.dumps(reconnect_probe()))"
        q=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',probe],timeout=120)
        if q.returncode or json.loads(q.stdout)['verdict']!='PASS':raise RuntimeError('Pre-spend network gate failed')
        (dest/(name+'-contract.private.json')).write_text(json.dumps(payload,indent=2),encoding='utf-8')
        import yaml
        payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
    if a.detach:
        launcher=r'''import json,sys,os,subprocess,time,hashlib
from pathlib import Path
d=json.load(sys.stdin);p=d['payload'];folder=Path('/opt/workbench/pi-comparison/formal-launches');folder.mkdir(exist_ok=True)
sys.path.insert(0,d['controller']);from pi_formal_linux import quiet
quiet()
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for f in folder.glob('*.json'):
 v=json.loads(f.read_bytes());proc=Path('/proc')/str(v['pid'])
 if v.get('boot_id')==boot and (proc/'stat').exists():
  fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
  if fields[0]!='Z' and fields[19]==v['process_start_ticks']:raise RuntimeError('Another Pi owner is active')
name=p['run_id'];command=['timeout','--signal=TERM','--kill-after=5s',str(d['total'])+'s','/opt/workbench/.venv-linux/bin/python','-B',d['controller']+'/pi_formal_linux.py']
with (folder/(name+'.private.log')).open('xb') as log:
 child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 child.stdin.write(json.dumps(p).encode());child.stdin.close()
value={'run_id':name,'pid':child.pid,'process_start_ticks':Path('/proc/'+str(child.pid)+'/stat').read_text().split()[21],
 'boot_id':boot,'command_sha256':hashlib.sha256(Path('/proc/'+str(child.pid)+'/cmdline').read_bytes()).hexdigest(),
 'started_unix':time.time(),'timeout_seconds':d['total'],'controller':d['controller'],'automatic_replay':False,
 'plan_sha256':p.get('plan',{}).get('plan_sha256'),'source_sha256':p['source_sha256']}
with (folder/(name+'.json')).open('x') as f:json.dump(value,f,indent=2)
print(json.dumps(value))
'''
        total=2400 if a.mode=='tools' else 21600 if a.mode=='compare' else 180
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',launcher],input_bytes=json.dumps({'payload':payload,'controller':folder,'total':total}).encode(),timeout=30)
    else:
        r=run(['/opt/workbench/.venv-linux/bin/python','-B',folder+'/pi_formal_linux.py'],
              input_bytes=json.dumps(payload).encode(),timeout=2400 if paid else 180)
    payload.pop('key',None)
    (dest/(name+'.private.log')).write_bytes(r.stdout+r.stderr)
    print(r.stdout.decode(errors='replace')[-2500:])
    if r.returncode:raise RuntimeError('Formal controls failed; evidence retained')
    result=json.loads(r.stdout)
    if not a.detach:
        required={'controls':'PASS_FORMAL_SDK_CONTROLS','tools':'PASS_REAL_PROVIDER_TOOLS','compare':'FORMAL_COMPARISON_COMPLETED'}[a.mode]
        if result.get('status')!=required:raise RuntimeError('Gate or comparison did not complete; evidence retained without automatic replay')
    return 0


if __name__=='__main__':
    original=subprocess.run
    def hidden(*args,**kwargs):
        if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
        return original(*args,**kwargs)
    subprocess.run=hidden
    raise SystemExit(main())
