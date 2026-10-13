"""Read-only native evidence inventory. No credentials, imports of candidate code or models."""
import hashlib
import json
from pathlib import Path
import re

BASE = Path('/opt/workbench/benchmark/private')
LEDGER = Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
PROC = Path('/proc')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def acceptance_inventory(config):
    guard = config.get('acceptance_continuation')
    if not guard:
        return None
    folder = Path(guard['folder']); script = Path(guard['script'])
    if (not folder.resolve().is_relative_to(Path('/opt/workbench/recovery')) or
            sha((folder / 'plan.json').read_bytes()) != guard['plan_sha256'] or
            sha(script.read_bytes()) != guard['script_sha256']):
        raise ValueError('Acceptance continuation binding changed')
    for name, expected in guard.get('support_sha256', {}).items():
        if sha((script.parent / name).read_bytes()) != expected:
            raise ValueError('Acceptance support source changed')
    plan = json.loads((folder / 'plan.json').read_bytes())
    root = Path(plan['source_run'])
    if root.parent != BASE / 'main-runs' or plan['manifest_sha256'] != config['manifest_sha256']:
        raise ValueError('Acceptance continuation changed frozen task')
    boot = (PROC / 'sys/kernel/random/boot_id').read_text().strip()
    active = []
    launched = [p for p in (folder / 'launches').glob('*.json') if '.' not in p.stem]
    for file in launched:
        value = json.loads(file.read_bytes()); stat = PROC / str(value['pid']) / 'stat'
        if value['native_boot_id'] != boot or not stat.exists():
            continue
        fields = stat.read_text().rsplit(')', 1)[1].split()
        if fields[0] != 'Z' and fields[19] == value['process_start_ticks']:
            argv = (stat.parent / 'cmdline').read_bytes().split(b'\0')
            if str(script).encode() not in argv or str(folder).encode() not in argv:
                raise ValueError('Acceptance controller command mismatch')
            active.append(value)
    if len(active) > 1:
        raise ValueError('Concurrent acceptance controllers')
    known = {v['pid'] for v in active}
    for proc in PROC.iterdir():
        if not proc.name.isdigit(): continue
        try:
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
            if str(script).encode() not in argv or str(folder).encode() not in argv: continue
            ancestor = int(proc.name)
            for _ in range(8):
                if ancestor in known: break
                ancestor = int((PROC / str(ancestor) / 'stat').read_text().rsplit(')', 1)[1].split()[1])
                if ancestor in (0, 1): raise ValueError('Unowned acceptance process blocks all launches')
            else: raise ValueError('Unowned acceptance process blocks all launches')
        except OSError: pass
    # A receipt is insufficient to resume paid work until its controller exits.
    complete = (root / 'receipt.json').exists()
    status = 'ACTIVE' if active else 'COMPLETE' if complete else 'READY'
    if not active and not complete:
        # An ordinary evaluation/controller failure cannot be silently retried.
        for file in launched:
            launch = json.loads(file.read_bytes())
            if launch['native_boot_id'] == boot and launch['started_unix'] >= config.get('manual_continuation_unix', 0):
                status = 'FAILED_REQUIRES_INSPECTION'
        for intent in (folder / 'launches').glob('*.intent.json'):
            if not intent.with_name(intent.name.replace('.intent.json', '.json')).exists():
                if json.loads(intent.read_bytes())['native_boot_id'] == boot:
                    status = 'FAILED_REQUIRES_INSPECTION'
    return {'status': status, 'run_id': root.name, 'active': active,
            'folder': str(folder), 'completed_acceptances': sorted(p.name for p in root.glob('private-acceptance-*.json'))}


def inventory(config):
    boot = (PROC / 'sys/kernel/random/boot_id').read_text().strip()
    ledger_bytes = LEDGER.read_bytes()
    ledger = json.loads(ledger_bytes)
    requests = ledger['requests']; turns = ledger['codex_turns']
    if (ledger['phase'] != 'P6_MAIN_LOCAL_20261011' or
        ledger['authorization_sha256'] != config['authorization_sha256'] or
        ledger['cash_bound_nano'] != sum(r['charge_bound_nano'] for r in requests) or
        any(r['index'] != i for i, r in enumerate(requests, 1))):
        raise ValueError('Cumulative native ledger validation failed')
    prefixes = config.get('ledger_floor', {})
    request_ids = [(r['index'], r['experiment'], r['observed_at']) for r in requests]
    for name, rows in [('requests', request_ids), ('turns', turns)]:
        old = prefixes.get(name)
        if old and (len(rows) < old['count'] or
                    sha(json.dumps(rows[:old['count']], sort_keys=True).encode()) != old['identity_sha256']):
            raise ValueError('Historical ledger entries changed or were removed')
    ledger_view = {'requests': len(requests), 'subscription_turns': len(turns),
                   'cash_bound_nano': ledger['cash_bound_nano'], 'sha256': sha(ledger_bytes),
                   'floor': {name: {'count': len(rows), 'identity_sha256': sha(json.dumps(rows, sort_keys=True).encode())}
                             for name, rows in [('requests', request_ids), ('turns', turns)]}}
    runs = []; active = []
    folder = BASE / 'main-launches'
    for file in sorted(folder.glob('*.json')):
        launch = json.loads(file.read_bytes()); name = launch['run_id']
        if not re.fullmatch(r'p6-main-(execute|sensitivity|offline)-[A-Za-z0-9_.-]+-[0-9]{8}T[0-9]{6}Z', name):
            raise ValueError('Unexpected native main launch identity')
        stat = PROC / str(launch['pid']) / 'stat'
        alive = False
        if stat.exists():
            fields = stat.read_text().rsplit(')', 1)[1].split()
            # Native start ticks are measured in the *same* boot only.
            if (config.get('native_boot_id') == boot and fields[0] != 'Z' and
                fields[19] == launch['process_start_ticks']):
                command = (stat.parent / 'cmdline').read_bytes()
                alive = b'p6_main_runtime_linux.py' in command
        root = BASE / 'main-runs' / name
        contract_path = root / 'control/run-contract.json'
        contract = json.loads(contract_path.read_bytes()) if contract_path.exists() else None
        if alive: active.append(name)
        if launch['started_unix'] < config['batch_started_unix'] or name.startswith('p6-main-offline-'):
            continue
        # Refuse ambiguous launch gaps. The run may not have written its contract yet.
        if contract is None:
            runs.append({'run_id': name, 'status': 'LAUNCH_UNCERTAIN', 'alive': alive,
                         'started_unix': launch['started_unix']})
            continue
        if contract['manifest']['manifest_sha256'] != config['manifest_sha256']:
            continue
        if (contract['source_sha256'] != config['runner_source_sha256'] or
            contract['entrypoint_sha256'] != config['entrypoint_sha256'] or
            sha(json.dumps(contract['budget'], sort_keys=True, separators=(',', ':')).encode()) != config['authorization_sha256']):
            raise ValueError('Recovered run source or authorization differs')
        row = {'run_id': name, 'task_id': contract['task']['task_id'], 'mode': contract['mode'],
               'alive': alive, 'started_unix': launch['started_unix'],
               'contract_sha256': sha(contract_path.read_bytes()), 'receipt_sha256': None,
               'status': 'RUNNING' if alive else 'EXIT_WITHOUT_RECEIPT'}
        if (root / 'failure.json').exists():
            failure = json.loads((root / 'failure.json').read_bytes())
            row.update(status=failure['status'], model_failure=failure.get('model_failure', 'unavailable'))
        elif (root / 'receipt.json').exists():
            raw = (root / 'receipt.json').read_bytes(); receipt = json.loads(raw)
            row.update(status=receipt['status'], receipt_sha256=sha(raw))
            if contract['mode'] == 'execute' and receipt['status'] == 'MAIN_TASK_COMPLETED':
                if receipt['task_id'] != row['task_id'] or receipt['run_id'] != name:
                    raise ValueError('Completed task receipt identity mismatch')
                arms = [json.loads(p.read_bytes()) for p in root.glob('arm-*.json')]
                if sorted(r['arm'] for r in arms) != list('ABCDEF'):
                    raise ValueError('Incomplete six-arm receipt cannot be skipped as completed')
                row['arms'] = {r['arm']: r['outcome'] for r in arms}
            elif contract['mode'] == 'sensitivity':
                row['source_run'] = receipt.get('source_run')
        row['completed_role_count'] = len(list(root.glob('*/controller-outcome.json')))
        row['completed_arm_count'] = len(list(root.glob('arm-*.json')))
        runs.append(row)
    # A process whose launch receipt was lost must also prevent another launch.
    unowned = []
    known_pids = {str(json.loads(p.read_bytes())['pid']) for p in folder.glob('*.json')}
    for proc in PROC.iterdir():
        if not proc.name.isdigit(): continue
        try:
            cmd = (proc / 'cmdline').read_bytes().split(b'\0')
            if '/opt/workbench/source/p6_main_runtime_linux.py'.encode() in cmd:
                # The frozen launcher records GNU timeout, whose child is the runtime.
                ancestor = proc.name; known = False
                for _ in range(8):
                    if ancestor in known_pids: known = True; break
                    info = (PROC / ancestor / 'stat').read_text().rsplit(')', 1)[1].split()
                    ancestor = info[1]
                    if ancestor in ('0', '1'): break
                if not known: unowned.append(int(proc.name))
        except (OSError, ProcessLookupError): pass
    return {'native_boot_id': boot, 'ledger': ledger_view, 'runs': runs,
            'active_main_runs': active, 'unowned_main_pids': unowned,
            'acceptance_continuation': acceptance_inventory(config)}


if __name__ == '__main__':
    import sys
    print(json.dumps(inventory(json.load(sys.stdin))))
