"""Freeze and launch the 112 missing Pi cells; never replay the original sixteen."""
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
from pi_full_protocol import PROTOCOL,TASKS,RETAINED_TASKS,cells,digest,exclusive,validate_plan

PLAN=ROOT/'benchmarks/pi-comparison/full-main-plan-v1.json'
INTAKE=ROOT/'.local-workbench/pi-comparison/intake'


def deploy():
    files=[Path(__file__).with_name(n) for n in ('pi_session.mjs','pi_formal_linux.py','events.py','pi_protocol.py',
           'pi_retry_policy.mjs','pi_recovery_policy.py','pi_overload_recovery_linux.py','pi_full_protocol.py','pi_full_main_linux.py')]
    files += [ROOT/'scripts'/n for n in ('p6_checkpoint_recovery.py','p6_gc_adjudication.py','p6_gc_dependencies.py',
              'p6_gc_grader.py','p6_gc_source_policy.py','p6_science_main_linux.py','p6_gc_worker.py','p6_network_recovery.py','p6_network_policy.py',
              'p6_pc_grader.py','p6_pc_validation.py','p6_pc_statistics.py','p6_egl_grader.py','p6_egl_worker.py',
              'p6_egl_replay.py','p6_science_contracts.py','p6_science_sandbox.py','p6_tms_grader.py','p6_output_data.py')]
    files += [ROOT/'benchmarks/pi-comparison/tasks/science-clarifications-v1.md']
    sources={p.name:p.read_text(encoding='utf-8') for p in files}
    hashes={n:hashlib.sha256(v.encode()).hexdigest() for n,v in sources.items()}
    folder='/opt/workbench/pi-comparison/controller-full-'+digest(hashes)[:16]
    code='''import sys,json;from pathlib import Path
d=json.load(sys.stdin);folder=Path(d['folder']);folder.mkdir(exist_ok=True)
for name,raw in d['sources'].items():
 p=folder/name
 if p.exists() and p.read_bytes()!=raw.encode():raise ValueError('Frozen content-addressed source changed')
 if not p.exists():p.write_bytes(raw.encode())
print(json.dumps({'status':'DEPLOYED_ZERO_MODELS'}))
'''
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps({'folder':folder,'sources':sources}).encode(),timeout=30)
    if r.returncode:raise RuntimeError('Isolated deployment failed')
    return folder,{folder+'/'+n:h for n,h in hashes.items()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','controls','compare'))
    parser.add_argument('--detach',action='store_true')
    parser.add_argument('--deepseek-network-retry10',action='store_true',help='Prospective frozen DeepSeek-only transport revision; never amend an existing run')
    parser.add_argument('--plan',default=PLAN.name,help='Immutable versioned full-main plan filename')
    parser.add_argument('--resume-run',help='Exact existing formal-full-compare run, completed steps reused; uncertain starts block')
    a=parser.parse_args();budget,budget_sha=authorization(ROOT/'configs/budget-p6-main-v6-cash200-approved.json')
    if not __import__('re').fullmatch(r'full-main-plan-v[1-9][0-9]*\.json',a.plan):raise ValueError('Versioned plan filename required')
    plan_path=PLAN.with_name(a.plan)
    folder,source=deploy();INTAKE.mkdir(parents=True,exist_ok=True)
    if a.mode=='prepare':
        from sys import path
        path.insert(0,str(ROOT/'src'))
        from workbench.benchmark import check_manifest
        manifest=json.loads((ROOT/'configs/benchmark-p6-v12-cash200.json').read_bytes());check_manifest(manifest)
        code='''import json,hashlib;from pathlib import Path
root=Path('/opt/workbench/benchmark/private/pi-comparison/formal-compare-20261014T071703Z')
paths=[root/'receipt.json',*sorted(root.glob('*/result.json')),
 Path('/opt/workbench/benchmark/private/pi-comparison/formal-overload-recover-20261014T085706Z/receipt.json'),
 Path('/opt/workbench/benchmark/private/pi-comparison/formal-source-review-20261014T113918Z/receipt.json')]
ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
archive=Path('/opt/workbench/pi-comparison/full-main-legacy-ledger-20261014.json')
if not archive.exists():
 with archive.open('xb') as f:f.write(ledger.read_bytes())
paths.append(archive)
print(json.dumps({'retained_original_root':str(root),'legacy_ledger':str(archive),
 'retained_evidence_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}))
'''
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],timeout=30)
        if r.returncode:raise RuntimeError('Original result registration failed')
        legacy=json.loads(r.stdout)
        if len(legacy['retained_evidence_sha256'])!=20:raise ValueError('Exactly16 rows/receipt/two supplements/ledger archive required')
        plan={'schema_version':1,'protocol':PROTOCOL,'main_manifest':manifest,'source_sha256':source,
              'entrypoint_sha256':hashlib.sha256(Path(__file__).read_text(encoding='utf-8').encode()).hexdigest(),
              'budget_authorization_sha256':budget_sha,'cumulative_caps':{'deepseek_requests':10000,'api_cash_usd':200},
              'cells':cells(t for t in TASKS if t not in RETAINED_TASKS),'retained_cells':cells(RETAINED_TASKS),
              'bulk_256_enabled':False,'external_release_authorized':False,
              'authorization':'Direct human request to complete all sixteen Pi tasks, Luna monitoring and Sol scientific/code review',
              'repetitions':1,'compute_policy':'LOCAL_ONLY_CPU_PROTOCOLS_PRESERVED_GPU_TASKS_SINGLE_LOCAL_GPU',
              'public_role_seconds':900,'scientific_role_seconds':1200,'request_seconds':600,'role_requests':1000,'deepseek_output_tokens':256000,
              'models':{'deepseek':'deepseek-flash','subscription':'gpt-6.1-sol'},
              'scientific_contract_revision':'Prospective clarified metadata and corrected EGL/PC evaluator; unchanged numeric thresholds. STROKE owner-public180s/4GiB resources.',
              'analysis_policy':'Retain original two-task cohort separately; no retrospective same-protocol or equal-budget causal claim',
              'recovery':'Durable completed substeps reused; uncertain started steps require reconciliation, no whole-task replay',
              'monitoring':'Luna read-only status; Sol science and implementation',**legacy}
        if a.deepseek_network_retry10:
            from p6_network_policy import RETRY10_POLICY
            plan['deepseek_transport_policy']=RETRY10_POLICY
        plan['plan_sha256']=digest(plan);validate_plan(plan)
        if plan_path.exists() and json.loads(plan_path.read_bytes())!=plan:raise ValueError('Plan immutable; use an explicitly versioned successor')
        if not plan_path.exists():exclusive(plan_path,plan)
        print(json.dumps({'status':'FROZEN_ZERO_MODELS','new_cells':112,'retained_cells':16,'plan_sha256':plan['plan_sha256']}));return 0
    plan=validate_plan(json.loads(plan_path.read_bytes()))
    if bool(plan.get('deepseek_transport_policy'))!=a.deepseek_network_retry10:
        raise ValueError('Exact transport flag must match frozen plan')
    if (plan['source_sha256']!=source or plan['budget_authorization_sha256']!=budget_sha
            or plan['entrypoint_sha256']!=hashlib.sha256(Path(__file__).read_text(encoding='utf-8').encode()).hexdigest()):
        raise ValueError('Frozen source/entrypoint/authorization changed')
    paid=a.mode=='compare'
    if paid and a.deepseek_network_retry10:
        raise ValueError('Retry10 must use a separately reconciled never-started continuation; direct matrix replay forbidden')
    if paid and subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).strip():raise RuntimeError('Commit exact source before paid launch')
    if a.resume_run and (not paid or not __import__('re').fullmatch(r'formal-full-compare-[0-9TZ]+',a.resume_run)):
        raise ValueError('Explicit exact compare run required')
    run_id=a.resume_run or 'formal-full-'+a.mode+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'mode':a.mode,'run_id':run_id,'plan':plan,'source_sha256':source,'budget':budget}
    contract=INTAKE/(run_id+'-contract.private.json')
    if contract.exists() and json.loads(contract.read_bytes())!=payload:raise ValueError('Existing launch contract differs')
    if not contract.exists():exclusive(contract,payload)
    if paid:
        gate="import sys,json;sys.path.insert(0,"+repr(folder)+");import pi_full_main_linux as f;v=json.load(sys.stdin);f.validate_bindings(v);f.require_controls(v);f.pi.quiet();print(json.dumps({'status':'PRESPEND_PASS'}))"
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',gate],input_bytes=json.dumps(payload).encode(),timeout=30)
        if r.returncode:raise RuntimeError('Exact pre-spend gate failed; no credential read')
        import yaml
        payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
    if a.detach:
        launcher='''import json,sys,subprocess,time,hashlib;from pathlib import Path
d=json.load(sys.stdin);p=d['payload'];base=Path('/opt/workbench/pi-comparison/formal-launches');base.mkdir(exist_ok=True)
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for path in base.glob('*.json'):
 row=json.loads(path.read_bytes());proc=Path('/proc')/str(row['pid'])
 if row.get('boot_id')==boot and (proc/'stat').exists():
  fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
  if fields[0]!='Z' and fields[19]==row['process_start_ticks']:raise RuntimeError('Another exact Pi owner remains active')
name=p['run_id']+'-'+str(time.time_ns());command=['/opt/workbench/.venv-linux/bin/python','-B',d['controller']+'/pi_full_main_linux.py']
with (base/(name+'.private.log')).open('xb') as log:
 child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 child.stdin.write(json.dumps(p).encode());child.stdin.close()
proc=Path('/proc')/str(child.pid)
value={'run_id':p['run_id'],'pid':child.pid,'boot_id':boot,'process_start_ticks':proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],
 'command_sha256':hashlib.sha256(proc.joinpath('cmdline').read_bytes()).hexdigest(),'controller':d['controller'],
 'plan_sha256':p['plan']['plan_sha256'],'source_sha256':p['source_sha256'],'started_unix':time.time(),
 'automatic_model_replay':False,'log':str(base/(name+'.private.log'))}
with (base/(name+'.json')).open('x') as f:json.dump(value,f,indent=2)
print(json.dumps(value))
'''
        r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',launcher],input_bytes=json.dumps({'payload':payload,'controller':folder}).encode(),timeout=30)
    else:
        r=run(['/opt/workbench/.venv-linux/bin/python','-B',folder+'/pi_full_main_linux.py'],input_bytes=json.dumps(payload).encode(),timeout=240)
    payload.pop('key',None)
    log=INTAKE/(run_id+'-launch-'+str(__import__('time').time_ns())+'.private.log');log.write_bytes(r.stdout+r.stderr)
    print(r.stdout.decode(errors='replace')[-3000:])
    if r.returncode:raise RuntimeError('Full-main execution failed; all evidence retained')
    return 0


if __name__=='__main__':
    original=subprocess.run
    def hidden(*args,**kwargs):
        if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
        return original(*args,**kwargs)
    subprocess.run=hidden
    raise SystemExit(main())
