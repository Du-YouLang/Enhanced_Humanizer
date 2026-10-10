"""Reserve a P0 subscription turn before starting the real Linux Humanize demo."""

from datetime import datetime, timezone
import json
import os
import time

from wsl_project import ROOT, run


def main():
    approval=json.loads((ROOT/'configs/budget-proposal.json').read_text())
    if approval['status']!='AUTHORIZED_P0_ONLY' or not approval['inference_enabled']:
        raise PermissionError('P0 model execution not authorized')
    audit=json.loads((ROOT/'.local-workbench/audits/linux-fence.json').read_text())
    if audit['verdict']!='PASS':
        raise PermissionError('Real OS fence gate has not passed')
    for source,target in [('scripts/p0_coding_demo_linux.py','/opt/workbench/source/p0_coding_demo_linux.py'),
                          ('.hmz/flows/p0_coding_demo/__init__.py','/opt/workbench/source/flows/p0_coding_demo/__init__.py')]:
        code='import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(sys.stdin.buffer.read())'
        p=run(['/usr/bin/python3','-c',code,target],input_bytes=(ROOT/source).read_bytes())
        if p.returncode: raise RuntimeError('Public source deployment failed')
    ledger_path=ROOT/'.local-workbench/audits/p0-model-budget.json'
    lock_path=ledger_path.with_suffix('.json.lock')
    descriptor=os.open(lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    run_id='p0-codex-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    try:
        ledger=json.loads(ledger_path.read_text())
        if ledger['codex_turns_used']>=min(2,approval['authorized_p0_limits']['codex_subscription_turns']):
            raise PermissionError('P0 Codex turn budget exhausted')
        ledger['codex_turns_used']+=1
        ledger.setdefault('codex_turn_reservations',[]).append({'run_id':run_id,'observed_at':datetime.now(timezone.utc).isoformat(),'timeout_seconds':120})
        with ledger_path.open('w') as handle:
            handle.write(json.dumps(ledger,indent=2)+'\n');handle.flush();os.fsync(handle.fileno())
        tick=time.perf_counter()
        # GNU timeout owns the Linux process group. A Windows subprocess timeout alone would leave descendants.
        p=run(['timeout','--signal=TERM','--kill-after=5s','120s','python','/opt/workbench/source/p0_coding_demo_linux.py',run_id],timeout=140)
        (ROOT/'.local-workbench/audits'/(run_id+'.private.log')).write_bytes(p.stdout+b'\nSTDERR\n'+p.stderr)
        result=run(['cat','/opt/workbench/evidence/'+run_id+'.json'])
        if result.returncode==0:
            (ROOT/'.local-workbench/audits'/(run_id+'.json')).write_bytes(result.stdout)
            record=json.loads(result.stdout)
            print(json.dumps({k:v for k,v in record.items() if k not in ('result','test_stdout','test_stderr')},ensure_ascii=True))
        else:
            print(json.dumps({'run_id':run_id,'verdict':'TIMEOUT' if p.returncode in (124,137) else 'INFRA_FAIL','exit_code':p.returncode}))
        print(json.dumps({'wall_clock_seconds':round(time.perf_counter()-tick,6),'model_turn_reserved':True,'exit_code':p.returncode}))
    finally:
        os.close(descriptor);lock_path.unlink()


if __name__=='__main__':
    main()
