"""Windows P2 authorization gate. Secrets are read in memory and sent only to a protected controller."""

import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from wsl_project import ROOT,run


SOURCES=['p1_fixture.py','p1_budget.py','p1_broker.py','p1_drivers.py','p1_experiment_linux.py','p1_acceptance.py',
         'export_codex_usage.py','p2_candidates.py','p2_judges.py','p2_worker_linux.py','p2_isolation.py','p2_experiment_linux.py',
         'verify_p2_results_linux.py','p2_contract.py','audit_p2_custom_contract_linux.py','export_p2_evidence_linux.py',
         'audit_p2_experiment_cap_linux.py']


def deploy():
    files=[('scripts/'+name,'/opt/workbench/source/'+name) for name in SOURCES]
    files += [('.hmz/flows/'+name+'/__init__.py','/opt/workbench/source/flows/'+name+'/__init__.py')
              for name in ('p0_coding_demo','ds_candidates','sol_judge')]
    upstream=ROOT/'.local-workbench/upstreams/llm-as-a-verifier-ds4p1'
    import subprocess
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream).decode().strip()
    if sha!='90e8fc215606447d6d31e9e24bff7200fb0c0994' or subprocess.check_output(['git','status','--porcelain'],cwd=upstream):
        raise RuntimeError('LAV fixed source changed')
    files += [(str(path),'/opt/workbench/upstreams/lav/llm_verifier/'+path.name) for path in (upstream/'llm_verifier').glob('*.py')]
    files += [(str(upstream/'LICENSE'),'/opt/workbench/upstreams/lav/LICENSE')]
    code='import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())'
    for source,target in files:
        p=run(['/usr/bin/python3','-c',code,target],input_bytes=(ROOT/source).read_bytes())
        if p.returncode:raise RuntimeError('P2 public source deployment failed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['pool','judge','deploy'])
    parser.add_argument('--n',type=int,choices=[1,3,4,5],default=3)
    parser.add_argument('--concurrency',type=int,choices=range(1,6),default=3)
    parser.add_argument('--pool-path')
    parser.add_argument('--judge-kind',choices=['all','J1'],default='all')
    parser.add_argument('--task-contract',type=Path,help='Explicit frozen local JSON contract; custom task outputs are private')
    args=parser.parse_args()
    config=json.loads((ROOT/'configs/budget-p2.json').read_text())
    approval=json.loads((ROOT/'.local-workbench/approvals/p2.json').read_text(encoding='utf-8-sig'))
    accepted=json.loads((ROOT/'.local-workbench/audits/p1-accepted.json').read_text())
    if accepted['verdict']!='PASS' or approval.get('approved_by')!='human_user' or approval.get('phase')!='P2' or not config['inference_enabled']:
        raise PermissionError('P1 acceptance / P2 human authorization missing')
    for field in ('api_cash_usd','deepseek_inference_requests','codex_subscription_turns','per_request_timeout_seconds',
                  'per_candidate_timeout_seconds','per_experiment_timeout_seconds'):
        if not 0<config[field]<=approval[field]:raise PermissionError('P2 config exceeds specific human approval')
    if config['top_up_allowed'] or config['status']!='AUTHORIZED_P2_AFTER_P1_GATE':raise PermissionError('P2 policy mismatch')
    deploy()
    if args.mode=='deploy':print('P2 source deployed; no models called');return 0
    if args.mode=='judge' and (not args.pool_path or not args.pool_path.startswith('/opt/workbench/runs/p2-') or not args.pool_path.endswith('/frozen-pool.json') or '..' in args.pool_path):
        raise ValueError('Only a frozen P2 pool may be judged')
    import yaml
    dsh_home=Path(os.environ.get('DSH_HOME',str(Path(os.environ['USERPROFILE'])/'.dsh')))
    key=yaml.safe_load((dsh_home/'.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
    if not isinstance(key,str) or not key:raise RuntimeError('Existing saved DeepSeek reference unavailable')
    run_id='p2-'+(f'n{args.n}' if args.mode=='pool' else 'judge')+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'phase':'P2','p1_gate':'PASS','mode':args.mode,'run_id':run_id,'n':args.n,'concurrency':args.concurrency,'pool_path':args.pool_path,'judge_kind':args.judge_kind,
             'key':key,'requests':min(100,config['deepseek_inference_requests']),'codex_turns':min(6,config['codex_subscription_turns']),
             'cash_nano':min(2_000_000_000,int(config['api_cash_usd']*1e9)),
             'experiment_seconds':min(1200,config['per_experiment_timeout_seconds']),
             'runtime_lock_sha256':hashlib.sha256((ROOT/'configs/requirements-p1-linux.lock').read_bytes()).hexdigest()}
    source_paths=['scripts/'+name for name in SOURCES]+['.hmz/flows/'+name+'/__init__.py' for name in ('p0_coding_demo','ds_candidates','sol_judge')]
    payload['controller_source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_paths}
    if args.task_contract:
        from p2_contract import validate_contract
        payload['task_contract']=validate_contract(json.loads(args.task_contract.read_text(encoding='utf-8-sig')),payload['runtime_lock_sha256'])
    tick=time.perf_counter();raw=json.dumps(payload).encode();payload['key']='';key=''
    p=run(['timeout','--signal=TERM','--kill-after=5s',str(payload['experiment_seconds'])+'s','python','/opt/workbench/source/p2_experiment_linux.py'],
          input_bytes=raw,timeout=payload['experiment_seconds']+30);raw=b''
    target=ROOT/'.local-workbench/audits'
    (target/(run_id+'.private.log')).write_bytes(p.stdout+b'\nSTDERR\n'+p.stderr)
    record=run(['cat','/opt/workbench/evidence/'+run_id+'.json'])
    if record.returncode:
        print(json.dumps({'run_id':run_id,'verdict':'TIMEOUT_OR_INFRA_FAIL','exit_code':p.returncode}));return 1
    (target/(run_id+'.json')).write_bytes(record.stdout)
    value=json.loads(record.stdout)
    print(json.dumps({k:v for k,v in value.items() if k!='judges'},default=str),flush=True)
    print(json.dumps({'windows_wall_seconds':time.perf_counter()-tick,'exit_code':p.returncode}),flush=True)
    return 0 if p.returncode==0 and value['verdict']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
