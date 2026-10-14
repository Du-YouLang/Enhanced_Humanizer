"""Zero-model, crash-reconcilable cash-only handover at an idle boundary."""
import hashlib
import json
import os
from pathlib import Path
import sys

def sha(raw):return hashlib.sha256(raw).hexdigest()

def idle(proc=Path('/proc')):
    """No source/ledger replacement while either old controller still runs."""
    for folder in proc.iterdir():
        if not folder.name.isdigit():continue
        try:
            args=(folder/'cmdline').read_bytes().split(b'\0')
            if any(a.endswith((b'/p6_main_runtime_linux.py',b'/continue_p6_acceptance_linux.py')) for a in args):
                raise ValueError('Active benchmark or acceptance blocks cash amendment')
        except OSError:pass

def verify_old_completion(boundaries):
    for entry in boundaries:
        root=Path(entry['root'])
        if root.parent!=Path('/opt/workbench/benchmark/private/main-runs'):
            raise ValueError('Unexpected completion root')
        raw=(root/'receipt.json').read_bytes();value=json.loads(raw)
        if sha(raw)!=entry['sha256'] or value['status']!=entry['status']:
            raise ValueError('Old completion receipt changed')

def amend_or_reconcile(path,old,new,archive):
    from p6_main_budget import MainLedger,CASH_REVISION
    previous=MainLedger(path,old);current=MainLedger(path,new)
    value=json.loads(Path(path).read_bytes());archive=Path(archive)
    if value['authorization_sha256']==previous.authorization_sha256:
        # A power failure after archive fsync but before ledger replacement is
        # inspection-worthy. Do not silently replace that original archive.
        if archive.exists():raise ValueError('Archive exists but ledger is still old; inspect handover')
        return current.amend_authorization(old,archive)
    current.validate(value)
    before=archive.read_bytes();original=json.loads(before);previous.validate(original)
    history=value.get('authorization_history',[])
    if not history or history[-1]['amendment_kind']!=CASH_REVISION or history[-1]['before_ledger_sha256']!=sha(before):
        raise ValueError('No exact archived amendment to reconcile')
    for key in ('requests','codex_turns','cash_bound_nano'):
        if value[key]!=original[key]:raise ValueError('Usage changed before handover receipt; inspect')
    return dict(status='AMENDED_WITHOUT_RESET_RECONCILED',before_ledger_sha256=sha(before),
                authorization_sha256=current.authorization_sha256,aggregate_caps=current.caps(),
                requests_retained=len(value['requests']),subscription_turns_retained=len(value['codex_turns']),
                cash_bound_nano_retained=value['cash_bound_nano'])

def main():
    if os.getuid()==0:raise ValueError('Non-root project runtime required')
    payload=json.load(sys.stdin);idle();verify_old_completion(payload['boundaries'])
    folder=Path('/opt/workbench/recovery/p6-cash200-20261013/code');folder.mkdir(parents=True,exist_ok=True)
    for name,entry in payload['modules'].items():
        if name not in {'p6_main_budget.py','p1_budget.py','p6_output_policy.py','p6_network_policy.py'} or sha(entry['code'].encode())!=entry['sha256']:
            raise ValueError('Unbound amendment module')
        file=folder/name
        if file.exists():
            if file.read_bytes()!=entry['code'].encode():raise ValueError('Preserved amendment source differs')
        else:
            with file.open('xb') as f:f.write(entry['code'].encode());f.flush();os.fsync(f.fileno())
    sys.path.insert(0,str(folder))
    ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
    archive=ledger.parent/'amendments/20261013-cash200-before.private.json'
    result=amend_or_reconcile(ledger,payload['old'],payload['new'],archive)
    result.update(model_calls=0,after_ledger_sha256=sha(ledger.read_bytes()),original_boundary_receipts=payload['boundaries'])
    print(json.dumps(result))

if __name__=='__main__':main()
