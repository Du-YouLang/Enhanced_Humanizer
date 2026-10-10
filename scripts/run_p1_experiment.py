"""Windows authorization gate and Linux process-group watchdog for a single P1 experiment."""

import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time

import yaml

from wsl_project import ROOT,run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['native','humanize','rlar','flame','relay'])
    mode=parser.parse_args().mode
    config=json.loads((ROOT/'configs/budget-p1.json').read_text())
    p0=json.loads((ROOT/'.local-workbench/audits/p0-accepted.json').read_text())
    approval=json.loads((ROOT/'.local-workbench/approvals/p1.json').read_text(encoding='utf-8-sig'))
    if p0['verdict']!='PASS' or config['status']!='AUTHORIZED_P1_AFTER_P0_GATE' or not config['inference_enabled'] or approval['approved_by']!='human_user':
        raise PermissionError('P1 execution gates are not satisfied')
    files=['scripts/p1_budget.py','scripts/p1_broker.py','scripts/p1_drivers.py','scripts/p1_experiment_linux.py',
           'scripts/p1_acceptance.py','scripts/export_codex_usage.py',
           '.hmz/flows/p0_coding_demo/__init__.py','.hmz/flows/basic_relay/__init__.py']
    for source in files:
        target='/opt/workbench/source/'+(source.removeprefix('.hmz/') if source.startswith('.hmz/') else Path(source).name)
        code='import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())'
        p=run(['/usr/bin/python3','-c',code,target],input_bytes=(ROOT/source).read_bytes());
        if p.returncode:raise RuntimeError('Public source deployment failed')
    # Existing saved ref read in memory only. Never use the key pasted into chat or copy auth directories.
    dsh_home=Path(os.environ.get('DSH_HOME',str(Path(os.environ['USERPROFILE'])/'.dsh')))
    key=yaml.safe_load((dsh_home/'.credentials.yaml').read_text(encoding='utf-8'))['refs']['DEEPSEEK_API_KEY']
    if not isinstance(key,str) or not key:raise RuntimeError('Existing local DeepSeek credential unavailable')
    run_id='p1-'+mode+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    limits=config['authorized_p1_limits']
    payload={'phase':'P1','p0_gate':'PASS','mode':mode,'run_id':run_id,'key':key,
             'requests':min(40,limits['deepseek_inference_requests']),'codex_turns':min(6,limits['codex_subscription_turns']),
             'cash_nano':min(1_000_000_000,int(limits['api_cash_usd']*1e9)),
             'experiment_seconds':min(900,limits['per_experiment_timeout_seconds']),
             'runtime_lock_sha256':hashlib.sha256((ROOT/'configs/requirements-p1-linux.lock').read_bytes()).hexdigest()}
    tick=time.perf_counter()
    raw=json.dumps(payload).encode();payload['key']='';key=''
    p=run(['timeout','--signal=TERM','--kill-after=5s',str(payload['experiment_seconds'])+'s','python','/opt/workbench/source/p1_experiment_linux.py'],input_bytes=raw,timeout=payload['experiment_seconds']+30)
    raw=b''
    destination=ROOT/'.local-workbench/audits'
    (destination/(run_id+'.private.log')).write_bytes(p.stdout+b'\nSTDERR\n'+p.stderr)
    result=run(['cat','/opt/workbench/evidence/'+run_id+'.json'])
    if result.returncode==0:
        (destination/(run_id+'.json')).write_bytes(result.stdout)
        record=json.loads(result.stdout)
        print(json.dumps({k:v for k,v in record.items() if k not in ('result','requests','test_log')},default=str),flush=True)
    else:print(json.dumps({'run_id':run_id,'verdict':'TIMEOUT_OR_INFRA_FAIL','exit_code':p.returncode}))
    print(json.dumps({'wall_clock_seconds':round(time.perf_counter()-tick,6),'exit_code':p.returncode}),flush=True)


if __name__=='__main__':main()
