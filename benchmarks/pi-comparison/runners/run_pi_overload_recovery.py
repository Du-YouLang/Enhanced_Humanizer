"""Prepare/control/dispatch only the user's provider-overload continuations."""
import argparse,hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from run_pi_formal import ROOT,deploy
sys.path.insert(0,str(ROOT/'scripts'))
from wsl_project import run
from p6_main_budget import authorization

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('controls','prepare','recover'));p.add_argument('--detach',action='store_true');a=p.parse_args()
    budget,budget_sha=authorization(ROOT/'configs/budget-p6-main-v6-cash200-approved.json')
    folder,sources=deploy();dest=ROOT/'.local-workbench/pi-comparison/intake';dest.mkdir(exist_ok=True)
    name='formal-overload-'+a.mode+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'mode':'intake' if a.mode=='prepare' else a.mode,'run_id':name,'budget':budget,'source_sha256':sources}
    plan_path=ROOT/'benchmarks/pi-comparison/overload-recovery-v1.json'
    if a.mode=='prepare':
        r=run(['/opt/workbench/.venv-linux/bin/python','-B',folder+'/pi_overload_recovery_linux.py'],input_bytes=json.dumps(payload).encode(),timeout=45)
        if r.returncode:raise RuntimeError('Cannot verify overload checkpoints')
        intake=json.loads(r.stdout)
        if not intake['original_finished']:raise RuntimeError('Original finite matrix still running; no preparation overwrites it')
        if not intake['targets']:raise RuntimeError('No confirmed provider overloads to recover')
        control_candidates=sorted(dest.glob('formal-overload-controls-*.private.log'))
        if not control_candidates:raise RuntimeError('Actual zero-provider controls required')
        control=json.loads(control_candidates[-1].read_bytes())
        if control.get('status')!='PASS_OVERLOAD_RECOVERY_CONTROLS':raise RuntimeError('Latest controls did not pass')
        if control.get('source_sha256')!=sources:raise RuntimeError('Control source differs')
        from workbench.benchmark import digest
        old=json.loads((ROOT/'benchmarks/pi-comparison/formal-plan-v3.json').read_bytes())
        plan={**intake,'authorization':'USER_PROVIDER_OVERLOAD_RETRY_20261014','source_sha256':sources,
              'entrypoint_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'budget_authorization_sha256':budget_sha,'main_manifest':old['main_manifest'],
              'controls_root':control['root'],'no_completed_cell_replay':True,'original_scope_time_and_requests_preserved':True,
              'original_error_and_results_preserved':True,'consecutive_failure_limit':5,'external_release_authorized':False}
        plan['recovery_plan_sha256']=digest(plan)
        if plan_path.exists():raise FileExistsError('Prepared recovery plan is immutable')
        plan_path.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':'FROZEN_OVERLOAD_CONTINUATIONS','targets':[t['cell'] for t in plan['targets']],'sha256':plan['recovery_plan_sha256']}));return
    if a.mode=='recover':
        if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).strip():raise RuntimeError('Commit implementation and frozen recovery plan first')
        plan=json.loads(plan_path.read_bytes())
        if plan['source_sha256']!=sources or plan['entrypoint_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or plan['budget_authorization_sha256']!=budget_sha:
            raise ValueError('Frozen recovery source/authorization changed')
        payload['plan']=plan
        probe="import sys,json;sys.path.insert(0,'/opt/workbench/source');from p6_connection_probe import reconnect_probe;print(json.dumps(reconnect_probe()))"
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',probe],timeout=120)
        if r.returncode or json.loads(r.stdout)['verdict']!='PASS':raise RuntimeError('Fenced zero-model network probe failed')
        if any(t['cell_descriptor']['provider']=='deepseek' for t in plan['targets']):
            import yaml
            payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
    if a.detach:
        if a.mode!='recover':raise ValueError('Only paid bounded continuation detaches')
        launcher=r'''import json,sys,os,subprocess,time,hashlib
from pathlib import Path
d=json.load(sys.stdin);p=d['payload'];sys.path.insert(0,d['folder']);from pi_formal_linux import quiet
quiet();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();launches=Path('/opt/workbench/pi-comparison/formal-launches')
for f in launches.glob('*.json'):
 v=json.loads(f.read_bytes());proc=Path('/proc')/str(v['pid'])
 if v.get('boot_id')==boot and (proc/'stat').exists():
  fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
  if fields[0]!='Z' and fields[19]==v['process_start_ticks']:raise RuntimeError('Another exact Pi owner is active')
name=p['run_id'];command=['timeout','--signal=TERM','--kill-after=5s','3600s','/opt/workbench/.venv-linux/bin/python','-B',d['folder']+'/pi_overload_recovery_linux.py']
with (launches/(name+'.private.log')).open('xb') as log:
 child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 child.stdin.write(json.dumps(p).encode());child.stdin.close()
v={'run_id':name,'pid':child.pid,'boot_id':boot,'process_start_ticks':Path('/proc/'+str(child.pid)+'/stat').read_text().rsplit(')',1)[1].split()[19],
 'command_sha256':hashlib.sha256(Path('/proc/'+str(child.pid)+'/cmdline').read_bytes()).hexdigest(),'started_unix':time.time(),
 'source_sha256':p['source_sha256'],'recovery_plan_sha256':p['plan']['recovery_plan_sha256'],'automatic_whole_cell_replay':False}
with (launches/(name+'.json')).open('x') as f:json.dump(v,f,indent=2)
print(json.dumps(v))
'''
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',launcher],input_bytes=json.dumps({'folder':folder,'payload':payload}).encode(),timeout=30)
    else:r=run(['/opt/workbench/.venv-linux/bin/python','-B',folder+'/pi_overload_recovery_linux.py'],input_bytes=json.dumps(payload).encode(),timeout=240)
    (dest/(name+'.private.log')).write_bytes(r.stdout+r.stderr)
    if r.returncode:raise RuntimeError('Scoped recovery/control failed; exact output retained privately')
    result=json.loads(r.stdout)
    if a.mode=='controls':
        result['source_sha256']=sources
        (dest/(name+'.private.log')).write_text(json.dumps(result),encoding='utf-8')
    print(json.dumps(result))
    if a.mode=='controls' and result['status']!='PASS_OVERLOAD_RECOVERY_CONTROLS':raise RuntimeError('Zero-provider controls did not pass')

if __name__=='__main__':
    sys.path.insert(0,str(ROOT/'src'))
    original=subprocess.run
    def hidden(*a,**kw):
        if os.name=='nt':kw['creationflags']=subprocess.CREATE_NO_WINDOW
        return original(*a,**kw)
    subprocess.run=hidden
    main()
