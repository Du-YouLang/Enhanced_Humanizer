"""Prepare/control/launch only the never-started suffix after a Pi infra stop."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'scripts'))
from wsl_project import run

ORIGINAL='formal-full-compare-20261014T161449Z'
PLAN=ROOT/'.local-workbench/pi-comparison/intake/full-unstarted-continuation-v1.private.json'


def native(code,value,timeout=30):
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps(value).encode(),timeout=timeout)
    if r.returncode:raise RuntimeError('Native continuation gate failed: '+r.stderr.decode(errors='replace')[-1600:])
    return json.loads(r.stdout)


def deploy():
    names=('pi_full_continue_policy.py','pi_full_continue_linux.py')
    texts={n:Path(__file__).with_name(n).read_text(encoding='utf8') for n in names}
    hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in texts.items()}
    folder='/opt/workbench/pi-comparison/continue-unstarted-'+hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:16]
    native('''import json,sys;from pathlib import Path
d=json.load(sys.stdin);root=Path(d['root']);root.mkdir(exist_ok=True)
for name,text in d['texts'].items():
 p=root/name
 if p.exists() and p.read_bytes()!=text.encode():raise ValueError('Frozen successor changed')
 if not p.exists():p.write_bytes(text.encode())
print(json.dumps({'status':'DEPLOYED_ZERO_MODELS'}))
''',{'root':folder,'texts':texts})
    return folder,{folder+'/'+n:h for n,h in hashes.items()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','controls','compare'))
    parser.add_argument('--parent-run',default=ORIGINAL);parser.add_argument('--version',type=int,default=1);a=parser.parse_args()
    if not __import__('re').fullmatch(r'formal-full-compare-[0-9TZ]+',a.parent_run) or not 1<=a.version<=99:
        raise ValueError('Exact parent run and finite plan version required')
    plan_path=PLAN.with_name('full-unstarted-continuation-v'+str(a.version)+'.private.json')
    folder,sources=deploy()
    if a.mode=='prepare':
        original=json.loads((ROOT/'.local-workbench/pi-comparison/intake'/(a.parent_run+'-contract.private.json')).read_bytes())
        code='''import hashlib,json,sys;from pathlib import Path
d=json.load(sys.stdin);sys.path.insert(0,d['folder']);from pi_full_continue_policy import remaining_cells,retained_results
parent=d['original'];prior=parent.get('continuation_plan');p=prior['original_payload'] if prior else parent
root=Path('/opt/workbench/benchmark/private/pi-comparison')/parent['run_id']
roots=[*(prior.get('retained_runs',[prior['original_root']]) if prior else []),str(root)]
if len(roots)!=len(set(roots)):raise ValueError('Receipt chain repeats a run')
receipts=[json.loads((Path(r)/'receipt.json').read_bytes()) for r in roots];results=retained_results(receipts)
todo=remaining_cells(p['plan'],results);files=[]
for previous,receipt in zip(roots,receipts):
 previous=Path(previous);files.extend([previous/'receipt.json',*sorted((previous/'control/stages').glob('*.completed.json'))])
 for row in receipt['results']:
  c=row['cell'];dest=previous/(c['task_id']+'-'+c['profile']+'-'+c['provider'])
  files.extend(dest/n for n in ('result.json','controller-outcome.json','candidate-private.json','frozen-program.json','events.private.jsonl'))
ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json');archive=Path('/opt/workbench/pi-comparison/full-unstarted-legacy-ledger-v'+str(d['version'])+'.private.json')
if not archive.exists():
 with archive.open('xb') as f:f.write(ledger.read_bytes())
files.append(archive);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
plan={'protocol':'PI_UNSTARTED_SUFFIX_20261015_V'+str(d['version']),'original_payload':p,'original_root':str(root),'retained_runs':roots,
 'original_controller':str(Path(next(iter(p['source_sha256']))).parent),'remaining_cells':todo,'retained_cells':len(results),
 'retained_results_sha256':digest(results),'retained_sha256':{str(f):sha(f) for f in files},'ledger_archive':str(archive),
 'successor_sources':d['sources'],'controls_receipt':'/opt/workbench/pi-comparison/unstarted-v'+str(d['version'])+'-controls.private.json',
 'authorization':'Existing direct full112 request, resume unstarted cells only; failed generic provider processing error retained, not claimed overload',
 'failed_cell_retry_authorized_by_this_plan':False,'cumulative_caps':{'deepseek_requests':10000,'api_cash_usd':200},
 'external_release_authorized':False}
plan['continuation_sha256']=digest(plan);print(json.dumps(plan))
'''
        plan=native(code,{'folder':folder,'sources':sources,'original':original,'version':a.version})
        if plan_path.exists() and json.loads(plan_path.read_bytes())!=plan:raise ValueError('Existing continuation plan immutable')
        if not plan_path.exists():
            with plan_path.open('x',encoding='utf8') as f:json.dump(plan,f,indent=2)
        print(json.dumps({'status':'PREPARED_ZERO_MODELS','retained':plan['retained_cells'],'unstarted':len(plan['remaining_cells']),
                          'continuation_sha256':plan['continuation_sha256']}));return
    plan=json.loads(plan_path.read_bytes())
    if plan['successor_sources']!=sources:raise ValueError('Frozen successor source changed')
    payload={'mode':a.mode,'continuation_plan':plan}
    if a.mode=='controls':
        r=run(['/opt/workbench/.venv-linux/bin/python','-B',folder+'/pi_full_continue_linux.py'],input_bytes=json.dumps(payload).encode(),timeout=60)
        if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-1800:])
        print(r.stdout.decode());return
    if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).strip():raise ValueError('Commit exact successor before paid launch')
    gate="import sys,json;sys.path.insert(0,"+repr(folder)+");import pi_full_continue_linux as c;p=json.load(sys.stdin);core,_=c.bind(p);core.pi.quiet();g=c.read(p['continuation_plan']['controls_receipt']);assert g['status']=='PASS_UNSTARTED_ONLY_CONTINUATION_CONTROLS';print(json.dumps({'status':'PRESPEND_PASS'}))"
    native(gate,payload)
    payload['run_id']='formal-full-compare-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    public=dict(payload)
    with (PLAN.parent/(payload['run_id']+'-contract.private.json')).open('x',encoding='utf8') as f:json.dump(public,f,indent=2)
    import yaml
    payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf8'))['refs']['DEEPSEEK_API_KEY']
    launcher='''import json,sys,subprocess,time,hashlib;from pathlib import Path
d=json.load(sys.stdin);p=d['payload'];boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
base=Path('/opt/workbench/pi-comparison/formal-launches')
for f in base.glob('*.json'):
 row=json.loads(f.read_bytes());proc=Path('/proc')/str(row['pid'])
 if row.get('boot_id')==boot and (proc/'stat').exists():
  s=(proc/'stat').read_text().rsplit(')',1)[1].split()
  if s[0]!='Z' and s[19]==row['process_start_ticks']:raise RuntimeError('Other exact Pi owner active')
name=p['run_id']+'-'+str(time.time_ns());log=base/(name+'.private.log')
with log.open('xb') as out:
 child=subprocess.Popen(['/opt/workbench/.venv-linux/bin/python','-B',d['folder']+'/pi_full_continue_linux.py'],stdin=subprocess.PIPE,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 child.stdin.write(json.dumps(p).encode());child.stdin.close()
proc=Path('/proc')/str(child.pid)
v={'run_id':p['run_id'],'pid':child.pid,'boot_id':boot,'process_start_ticks':(proc/'stat').read_text().rsplit(')',1)[1].split()[19],
 'command_sha256':hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest(),'log':str(log),'started_unix':time.time(),
 'continuation_sha256':p['continuation_plan']['continuation_sha256'],'controller':d['folder'],'automatic_replay':False}
with (base/(name+'.json')).open('x') as f:json.dump(v,f,indent=2)
print(json.dumps(v))
'''
    value=native(launcher,{'payload':payload,'folder':folder})
    with (PLAN.parent/(payload['run_id']+'-owner.private.json')).open('x',encoding='utf8') as f:json.dump(value,f,indent=2)
    print(json.dumps(value))


if __name__=='__main__':
    original=subprocess.run
    def hidden(*args,**kwargs):
        if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
        return original(*args,**kwargs)
    subprocess.run=hidden;main()
