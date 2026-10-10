"""Local P3 authorization gate; independent phase ledger, no Jev or OpenRouter billing."""

import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from wsl_project import ROOT,run
from run_p2_experiment import deploy as deploy_p2,SOURCES as P2_SOURCES

SOURCES=['p3_contracts.py','p3_worker_linux.py','p3_runtime_linux.py','p3_experiment_linux.py','audit_p3_controls_linux.py','export_p3_evidence_linux.py','archive_p3_partial_linux.py','verify_p3_final_linux.py']
FLOWS=['sol_synthesis','synthesis_loop']


def source_map():
    paths=['scripts/'+name for name in P2_SOURCES+SOURCES]+['.hmz/flows/'+name+'/__init__.py' for name in ['p0_coding_demo','ds_candidates','sol_judge']+FLOWS]
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}


def deploy():
    deploy_p2()
    paths=[('scripts/'+name,'/opt/workbench/source/'+name) for name in SOURCES]
    paths += [('.hmz/flows/'+name+'/__init__.py','/opt/workbench/source/flows/'+name+'/__init__.py') for name in FLOWS]
    code='import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())'
    for source,target in paths:
        p=run(['/usr/bin/python3','-c',code,target],input_bytes=(ROOT/source).read_bytes())
        if p.returncode:raise RuntimeError('P3 deployment failed')


def authorize():
    config=json.loads((ROOT/'configs/budget-p3.json').read_text())
    approval=json.loads((ROOT/'.local-workbench/approvals/p3.json').read_text(encoding='utf-8-sig'))
    accepted=json.loads((ROOT/'.local-workbench/audits/p2-accepted.json').read_text())
    if accepted['verdict']!='PASS' or approval.get('approved_by')!='human_user' or approval.get('phase')!='P3' or not config['inference_enabled']:
        raise PermissionError('P2 acceptance/P3 human authorization missing')
    fields=('api_cash_usd','deepseek_inference_requests','codex_subscription_turns','per_request_timeout_seconds',
            'per_candidate_timeout_seconds','per_role_timeout_seconds','per_experiment_timeout_seconds')
    for name in fields:
        if not 0<config[name]<=approval[name]:raise PermissionError('P3 config exceeds specific human approval')
    if config['top_up_allowed'] or config['status']!='AUTHORIZED_P3_AFTER_P2_GATE' or config['judge_backend']!='Sol/J3':
        raise PermissionError('P3 policy/model identity mismatch')
    if (config['candidate_request_cap'],config['candidate_cash_cap_usd'],config['codex_role_turn_cap'],config['outer_infrastructure_retries'])!=(12,0.5,2,0):
        raise PermissionError('Implemented sublimits/retry policy differ from config')
    return {k:config[k] for k in fields}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['deploy','controls','run','resume','request-pause','export','archive-partials','verify'])
    parser.add_argument('--case',choices=['mixed','all-failed','impossible'],default='mixed')
    parser.add_argument('--run-id')
    parser.add_argument('--closed-loop',action='store_true')
    parser.add_argument('--pause-after',choices=['verifier_input','reviewer','verify_m','verifier_m','builder','ds_return'],default='')
    args=parser.parse_args();limits=authorize()
    if args.mode in ('resume','request-pause') and (not args.run_id or not args.run_id.startswith('p3-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-TZ' for c in args.run_id)):
        raise ValueError('Explicit safe P3 run ID required')
    if args.mode=='request-pause':
        p=run(['python','-c',"from pathlib import Path;import sys;p=Path('/opt/workbench/runs')/sys.argv[1]/'control/pause.requested';p.write_text('Human requested pause at next durable role boundary')",args.run_id])
        if p.returncode:raise RuntimeError('Pause request failed')
        print('Pause requested at next durable role boundary; current bounded request may finish');return 0
    deploy()
    if args.mode=='deploy':print('P3 deployed; zero model calls');return 0
    if args.mode=='verify':
        payload={'source_sha256':source_map(),'prior_ledgers':{
            'P1':'6f4d808ba13b259de0afb67e0d3f80c4c328125947c044801a7dcedcb0ed3643',
            'P2':'760385b37cd6246be664c0d33aae3eb9b351a5badfcdee02650241a111b74dea'}}
        p=run(['python','/opt/workbench/source/verify_p3_final_linux.py'],input_bytes=json.dumps(payload).encode(),timeout=120)
        print(p.stdout.decode(),end='')
        if p.returncode:print(p.stderr.decode(),file=sys.stderr)
        return p.returncode
    if args.mode in ('controls','export','archive-partials'):
        script={'controls':'audit_p3_controls_linux.py','export':'export_p3_evidence_linux.py','archive-partials':'archive_p3_partial_linux.py'}[args.mode]
        p=run(['python','/opt/workbench/source/'+script],timeout=120)
        print(p.stdout.decode(),end='')
        if p.returncode:print(p.stderr.decode(),file=sys.stderr)
        return p.returncode
    import yaml
    dsh=Path(os.environ.get('DSH_HOME',str(Path(os.environ['USERPROFILE'])/'.dsh')))
    key=yaml.safe_load((dsh/'.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
    if not isinstance(key,str) or not key:raise RuntimeError('Existing saved DS reference unavailable')
    run_id=args.run_id if args.mode=='resume' else 'p3-'+args.case+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'phase':'P3','p2_gate':'PASS','mode':args.mode,'run_id':run_id,'case':args.case,'closed_loop':args.closed_loop,
             'pause_after':args.pause_after,'limits':limits,'controller_source_sha256':source_map(),
             'runtime_lock_sha256':hashlib.sha256((ROOT/'configs/requirements-p1-linux.lock').read_bytes()).hexdigest(),'key':key}
    raw=json.dumps(payload).encode();payload['key']='';key='';tick=time.perf_counter()
    p=run(['timeout','--signal=TERM','--kill-after=5s',str(limits['per_experiment_timeout_seconds'])+'s','python','/opt/workbench/source/p3_experiment_linux.py'],
          input_bytes=raw,timeout=limits['per_experiment_timeout_seconds']+30);raw=b''
    audit=ROOT/'.local-workbench/audits'
    suffix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (audit/(run_id+'-'+suffix+'.private.log')).write_bytes(p.stdout+b'\nSTDERR\n'+p.stderr)
    for line in p.stdout.decode().splitlines():
        if line.startswith('{'):
            try:value=json.loads(line)
            except ValueError:continue
            print(json.dumps(value),flush=True)
    print(json.dumps({'run_id':run_id,'exit_code':p.returncode,'windows_wall_seconds':time.perf_counter()-tick}),flush=True)
    return p.returncode


if __name__=='__main__':sys.exit(main())
