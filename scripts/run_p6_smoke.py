"""Approved two-task P6 entry; credentials stay in memory, never in source or logs."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import subprocess

from wsl_project import ROOT,run

SCRIPTS=['p1_budget.py','p1_drivers.py','p1_broker.py','p2_candidates.py','p2_experiment_linux.py',
         'p2_judges.py','p3_worker_linux.py','export_codex_usage.py','p6_prepare_linux.py','p6_evaluate_linux.py',
         'p6_httpbin_linux.py','p6_requests_linux.py','p6_requests_runner.py','p6_worker_linux.py','p6_runtime_linux.py']


def deploy():
    mapping={f'/opt/workbench/source/{n}':(ROOT/'scripts'/n).read_text(encoding='utf-8') for n in SCRIPTS}
    mapping.update({f'/opt/workbench/source/flows/{n}/__init__.py':(ROOT/'.hmz/flows'/n/'__init__.py').read_text(encoding='utf-8')
                    for n in ['p0_coding_demo','sol_synthesis','sol_judge','benchmark_candidates']})
    mapping['/opt/workbench/source/src/workbench/benchmark.py']=(ROOT/'src/workbench/benchmark.py').read_text()
    mapping['/opt/workbench/source/src/workbench/__init__.py']=(ROOT/'src/workbench/__init__.py').read_text()
    code='import sys,json;from pathlib import Path\nfor p,t in json.load(sys.stdin).items():\n f=Path(p);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(t)\nprint("P6 public adapters deployed")'
    p=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],input_bytes=json.dumps(mapping).encode())
    if p.returncode:raise RuntimeError('Source deployment failed')
    return {p:hashlib.sha256(t.encode()).hexdigest() for p,t in mapping.items()}


def preparation(tid):
    code='''import json,hashlib,platform,os
from pathlib import Path
tid=__import__('sys').argv[1];suffix='-black.json' if tid=='BIP-black-2' else '-requests.json'
r=json.loads(sorted(Path('/opt/workbench/benchmark/private/preparation-attempts').glob('*'+suffix))[-1].read_text())
if r['task_id']!=tid or r['status']!='EVALUATOR_VALIDATED':raise RuntimeError('Reference controls not validated')
h={'kernel':platform.release(),'machine':platform.machine(),'cpu_model':next(l for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),'memory':next(l for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemTotal:')),'threads':os.cpu_count()}
def sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
permissions={'version':1,'non_root':True,'private_pid_mount_user_namespaces':True,'local':'per-role write/read','user':'none','system':'none','network':'model API only plus exact HTTPBIN fixture and two HTTPS regressions for Requests','task_env':'sealed read-only','hidden_material':'excluded from handoff'}
print(json.dumps({'status':'READY','task_id':tid,'env_sha256':r['environment']['env_sha256'],'base_commit':r['base_commit'],'hardware_sha256':sha(h),'permissions_sha256':sha(permissions),'hidden_suite_sha256':r['results']['gold']['hidden_suite_sha256'],'control_receipt_sha256':sha(r),'hardware':h,'protocol':r.get('protocol','native Black/Python3.8.3 with complete regression fixture')}))
'''
    p=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code,tid])
    if p.returncode:raise RuntimeError('Task environment not ready')
    return json.loads(p.stdout)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['offline','execute','lav-only','deploy'])
    parser.add_argument('--task',choices=['BIP-black-2','SWEL-psf__requests-1963'],default='BIP-black-2')
    parser.add_argument('--reuse-run',help='Explicit interrupted-controller continuation; retained candidates are not regenerated')
    args=parser.parse_args()
    config=json.loads((ROOT/'configs/budget-p6-smoke-approved.json').read_text())
    if config['authorization_status']!='APPROVED_BY_USER_2026-10-11' or not config['model_execution_enabled'] or args.task not in config['task_ids']:
        raise PermissionError('Specific human P6 smoke authorization missing')
    source=deploy()
    if args.mode=='deploy':print('Deployed; no model requests');return 0
    manifest=json.loads((ROOT/'configs/benchmark-p6-v2.json').read_text())
    sys.path.insert(0,str(ROOT/'src'))
    from workbench.benchmark import check_manifest
    check_manifest(manifest)
    prep=preparation(args.task)
    payload={'phase':'P6','mode':args.mode,'budget':config,'manifest':manifest,'preparation':prep,
             'task':next(t for t in manifest['tasks'] if t['task_id']==args.task),
             'source_sha256':source,'run_id':'p6-'+args.mode+'-'+args.task+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}
    snapshot=ROOT/'.local-workbench/benchmark/source-snapshots'/payload['run_id'];snapshot.mkdir(parents=True)
    for dest,wanted in source.items():
        if '/flows/' in dest:relative=Path('.hmz/flows')/dest.split('/flows/')[1]
        elif '/src/workbench/' in dest:relative=Path('src/workbench')/dest.split('/src/workbench/')[1]
        else:relative=Path('scripts')/Path(dest).name
        data=(ROOT/relative).read_text(encoding='utf8').encode()
        if hashlib.sha256(data).hexdigest()!=wanted:raise RuntimeError('Source changed after deployment')
        target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (snapshot/'receipt.json').write_text(json.dumps({'run_id':payload['run_id'],'source_sha256':source,
        'development_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()},indent=2))
    if args.reuse_run:
        if args.mode not in ('execute','lav-only'):raise ValueError('Continuation is only for explicit execution')
        payload['reuse_run']=args.reuse_run
    if args.task.startswith('SWEL-'):
        rows=json.loads((ROOT/'.local-workbench/benchmark/sources/swe-selected.private.json').read_text())
        payload['swe_row']=next(r for r in rows if r['instance_id']=='psf__requests-1963')
    if args.mode in ('execute','lav-only'):
        import yaml
        home=Path(os.environ['USERPROFILE'])/'.dsh'
        key=yaml.safe_load((home/'.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
        if not isinstance(key,str) or not key:raise RuntimeError('Existing saved DeepSeek credential unavailable')
        payload['key']=key
    else:payload['key']='offline-no-key'
    raw=json.dumps(payload).encode();payload['key']='';tick=time.perf_counter()
    p=run(['timeout','--signal=TERM','--kill-after=5s','1200s','/opt/workbench/.venv-linux/bin/python','-B',
           '/opt/workbench/source/p6_runtime_linux.py'],input_bytes=raw,timeout=1230);raw=b''
    target=ROOT/'.local-workbench/audits';target.mkdir(exist_ok=True)
    (target/(payload['run_id']+'.private.log')).write_bytes(p.stdout+p.stderr)
    print(p.stdout.decode().encode('ascii','backslashreplace').decode()[-2500:])
    print(json.dumps({'run_id':payload['run_id'],'exit_code':p.returncode,'windows_elapsed_seconds':time.perf_counter()-tick}),flush=True)
    return p.returncode


if __name__=='__main__':sys.exit(main())
