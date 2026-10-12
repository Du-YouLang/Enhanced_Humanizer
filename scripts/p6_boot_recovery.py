"""Local restart supervisor: adopt active work, skip receipts, never replay an ambiguous model call.

The frozen experiment runner is unchanged. This supplementary controller owns only
new recovery records and launches previously unstarted task/phase slots after reboot.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('xb') as handle:
        handle.write(canonical(value) + b'\n'); handle.flush(); os.fsync(handle.fileno())
    for attempt in range(6):
        try: os.replace(temporary, path); break
        except PermissionError:
            if attempt == 5: raise
            time.sleep(.02 * (attempt + 1))
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


class SupervisorAlreadyRunning(RuntimeError):
    pass


@contextmanager
def singleton(path):
    """Nonblocking OS-owned lock; reboot releases it, stale PID text grants no ownership."""
    with Path(path).open('a+b') as file:
        try:
            if os.name == 'nt':
                import msvcrt
                file.seek(0); msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, PermissionError) as error:
            raise SupervisorAlreadyRunning('Another process owns the recovery lock') from error
        try: yield
        finally:
            if os.name == 'nt':
                file.seek(0); msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)


class Journal:
    def __init__(self, path):
        self.path = Path(path); self.sequence = 0; self.previous = '0' * 64; self.entries = []
        if self.path.exists():
            raw = self.path.read_bytes()
            if raw and not raw.endswith(b'\n'):
                raise ValueError('Interrupted journal tail preserved; recovery requires inspection')
            for line in raw.split(b'\n')[:-1]:
                item = json.loads(line); body = {k: v for k, v in item.items() if k != 'hash'}
                if (body['sequence'] != self.sequence + 1 or body['previous'] != self.previous or
                    digest(canonical(body)) != item['hash']):
                    raise ValueError('Recovery journal corruption; no model restart')
                self.sequence = body['sequence']; self.previous = item['hash']
                self.entries.append(item)

    def append(self, event, detail):
        body = {'sequence': self.sequence + 1, 'previous': self.previous,
                'at': datetime.now(timezone.utc).isoformat(), 'event': event, 'detail': detail}
        value = dict(body, hash=digest(canonical(body)))
        with self.path.open('ab') as file:
            file.write(canonical(value) + b'\n'); file.flush(); os.fsync(file.fileno())
        self.sequence += 1; self.previous = value['hash']
        self.entries.append(json.loads(canonical(value)))

    def launch_intents(self):
        records = {}
        for item in self.entries:
            if item['event'] in ('LAUNCH_INTENT', 'LAUNCHED'):
                records[item['detail']['id']] = item['detail']
        return list(records.values())


def contained(project, name):
    path = (project / name).resolve()
    if not path.is_relative_to(project.resolve()): raise ValueError('State must stay inside project')
    return path


def next_step(config, state, inventory, *, original_alive, boot_changed):
    """Pure, testable exactly-once decision. Terminal failures are retained, not retried."""
    if original_alive: return {'action': 'OBSERVE_ORIGINAL'}
    if inventory['unowned_main_pids']: return {'action': 'BLOCK_UNOWNED_NATIVE'}
    if inventory['active_main_runs']: return {'action': 'ADOPT_NATIVE'}
    runs = inventory['runs']; used = state.get('launches', [])
    pending = []
    for task in config['tasks']:
        source = None
        for mode in config['modes']:
            matching = [r for r in runs if r.get('task_id') == task and r.get('mode') == mode]
            complete = [r for r in matching if r['status'] == ('MAIN_TASK_COMPLETED' if mode == 'execute' else 'FULL_TOOL_TRACE_SENSITIVITY_COMPLETED')]
            if len(complete) > 1: return {'action': 'BLOCK_DUPLICATE_COMPLETION', 'task': task, 'mode': mode}
            if complete:
                if mode == 'execute': source = complete[0]['run_id']
                elif complete[0].get('source_run') != source:
                    return {'action': 'BLOCK_SENSITIVITY_SOURCE', 'task': task}
                continue
            intents = [i for i in used if i['task'] == task and i['mode'] == mode]
            # The old Windows index may contain LAUNCHING without a native receipt.
            old = [a for a in config.get('old_attempts', []) if a['task_id'] == task and a['mode'] == mode]
            if matching or intents or old:
                pending.append({'task': task, 'mode': mode, 'status': 'INTERRUPTED_OR_UNCERTAIN_PRESERVED',
                                'run_ids': [r['run_id'] for r in matching]})
                continue
            if mode == 'sensitivity' and source is None:
                pending.append({'task': task, 'mode': mode, 'status': 'WAITING_FOR_COMPLETE_SOURCE'})
                continue
            # Any unassigned native launch makes attributing a new request unsafe.
            if any(r['status'] == 'LAUNCH_UNCERTAIN' for r in runs):
                return {'action': 'BLOCK_LAUNCH_GAP', 'pending': pending}
            if not boot_changed:
                return {'action': 'WAIT_FOR_REBOOT_OR_MANUAL_RECOVERY', 'pending': pending}
            return {'action': 'LAUNCH_UNSTARTED', 'task': task, 'mode': mode,
                    'source_run': source, 'pending': pending}
    return {'action': 'FINISHED_WITH_PENDING_INTERRUPTED' if pending else 'ALL_COMPLETED', 'pending': pending}


def ps_json(code):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', code],
                            capture_output=True, timeout=30, encoding='utf-8')
    if result.returncode: raise RuntimeError('Windows process/boot query failed')
    return json.loads(result.stdout.lstrip('\ufeff'))


def host_identity():
    return ps_json("$o=Get-CimInstance Win32_OperatingSystem; @{boot=$o.LastBootUpTime.ToUniversalTime().ToString('o')} | ConvertTo-Json -Compress")


def windows_controllers():
    # Filtering the returned inventory keeps unrelated process commands private.
    return ps_json("$v=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and $_.CommandLine -match 'scripts[\\\\/]run_p6_main_batch\\.py' } | ForEach-Object { @{ProcessId=$_.ProcessId; CreationDate=$_.CreationDate.ToString('o'); ExecutablePath=$_.ExecutablePath; CommandLine=$_.CommandLine} }); ConvertTo-Json -InputObject $v -Compress")


def native(config):
    project = Path(config['project']); script = Path(__file__).with_name('p6_recovery_probe_linux.py').read_text(encoding='utf-8')
    env = dict(os.environ, WSLENV='', WSL_UTF8='1')
    result = subprocess.run(['wsl.exe', '-d', 'EnhancedHumanizer-P0', '-u', 'workbench', '--cd', '/opt/workbench',
                             '--exec', '/opt/workbench/.venv-linux/bin/python', '-B', '-c', script],
                            cwd=project, input=canonical(config), capture_output=True, timeout=45, env=env)
    if result.returncode: raise RuntimeError('Read-only native inventory unavailable or invalid')
    return json.loads(result.stdout)


def validate_sources(config):
    project = Path(config['project'])
    manifest = json.loads(contained(project, config['manifest_file']).read_bytes())
    body = dict(manifest); body.pop('manifest_sha256')
    if digest(canonical(body)) != config['manifest_sha256']: raise ValueError('Frozen manifest changed')
    if manifest['entrypoint_sha256'] != config['entrypoint_sha256'] or manifest['runner_source_sha256'] != config['runner_source_sha256']:
        raise ValueError('Source contract changed')
    if digest((project / 'scripts/run_p6_main.py').read_bytes()) != config['entrypoint_sha256']:
        raise ValueError('Frozen entry changed')
    # Same source mapping as the frozen entry. No deployment or code execution here.
    for name, expected in config['runner_source_sha256'].items():
        if '/flows/' in name: rel = '.hmz/flows/' + name.split('/flows/')[1]
        elif '/src/workbench/' in name: rel = 'src/workbench/' + name.split('/src/workbench/')[1]
        else: rel = 'scripts/' + Path(name).name
        if digest(contained(project, rel).read_text(encoding='utf-8').encode()) != expected:
            raise ValueError('Frozen executable source changed')
    budget = json.loads(contained(project, manifest['budget_config']).read_bytes())
    if digest(json.dumps(budget, sort_keys=True, separators=(',', ':')).encode()) != config['authorization_sha256']:
        raise ValueError('Budget authorization changed')
    return budget


def supervise(config_path, *, execute=False, once=False):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_bytes())
    project = Path(config['project']).resolve(); folder = config_path.parent
    if not folder.is_relative_to(project / '.local-workbench'): raise ValueError('Private project recovery state required')
    if config['authorization'] != 'HUMAN_APPROVED_LOCAL_BOOT_RECOVERY_20261012': raise ValueError('Missing restart authorization')
    for name, expected in config['supervisor_files'].items():
        if digest(Path(__file__).with_name(name).read_bytes()) != expected: raise ValueError('Installed supervisor changed')
    state_path = folder / 'state.private.json'; enabled = folder / 'enabled.private.json'
    with singleton(folder / 'supervisor.lock'):
        journal = Journal(folder / 'events.private.ndjson')
        state = json.loads(state_path.read_bytes()) if state_path.exists() else {'launches': [], 'ledger_floor': config['ledger_floor']}
        if state.get('config_sha256', digest(config_path.read_bytes())) != digest(config_path.read_bytes()):
            raise ValueError('Recovery state/config binding changed')
        intents = journal.launch_intents()
        if any(i['id'] not in {j['id'] for j in intents} for i in state['launches']):
            raise ValueError('Recovery state has a launch without its durable journal')
        # Covers a crash between journal fsync and state replacement without replay.
        state['launches'] = intents
        state['config_sha256'] = digest(config_path.read_bytes())
        while True:
            if not json.loads(enabled.read_bytes()).get('enabled'):
                print(json.dumps({'status': 'DISABLED'})); return
            try:
                budget = validate_sources(config)
                identity = host_identity(); controls = windows_controllers()
                expected = config['original_owner']
                matches = [c for c in controls if c['ProcessId'] == expected['ProcessId'] and
                           datetime.fromisoformat(c['CreationDate']) == datetime.fromisoformat(expected['CreationDate']) and c['CommandLine'] == expected['CommandLine'] and
                           c['ExecutablePath'] == expected['ExecutablePath']]
                if controls and not matches: raise ValueError('Another Windows benchmark controller is active')
                probe_config = dict(config, ledger_floor=state['ledger_floor'])
                # New boot observation invalidates old PID ticks; two snapshots rebind native boot.
                inv = native(probe_config)
                if inv['native_boot_id'] != config['native_boot_id']:
                    probe_config['native_boot_id'] = inv['native_boot_id']; inv = native(probe_config)
                    # Across a reboot, old launch ticks alone never establish active ownership.
                    inv['active_main_runs'] = [r['run_id'] for r in inv['runs'] if r['alive'] and r['run_id'] in {i.get('run_id') for i in state['launches']}]
                    # If any actual main process exists, retain its receipt and wait rather than launch.
                    if any(r['alive'] for r in inv['runs']) and not inv['active_main_runs']:
                        raise ValueError('Native process across boot requires ownership reconciliation')
                boot_changed = identity['boot'] != config['windows_boot']
                # Refresh authoritative old attempts without ever overwriting the old batch.
                old = json.loads(contained(project, config['batch_index']).read_bytes())
                if old['manifest_sha256'] != config['manifest_sha256']: raise ValueError('Original batch changed protocol')
                decision = next_step(dict(config, old_attempts=old['attempts']), state, inv,
                                     original_alive=bool(matches), boot_changed=boot_changed)
                completed = state.setdefault('completed_receipts', {})
                for row in inv['runs']:
                    if row.get('receipt_sha256'):
                        if row['run_id'] in completed and completed[row['run_id']] != row['receipt_sha256']:
                            raise ValueError('Previously completed receipt changed')
                        completed[row['run_id']] = row['receipt_sha256']
                state['ledger_floor'] = inv['ledger']['floor']
                state.update(last_probe_unix=time.time(), boot=identity['boot'], decision=decision,
                             ledger=inv['ledger'], native_boot_id=inv['native_boot_id'], status=decision['action'])
                state.pop('error_type', None)
                if decision != state.get('last_event_decision'):
                    journal.append('DECISION', {'decision': decision, 'ledger': inv['ledger']})
                    state['last_event_decision'] = decision
                atomic(state_path, state)
                if decision['action'] == 'LAUNCH_UNSTARTED' and execute:
                    if len(inv['runs']) and any(r['alive'] for r in inv['runs']): raise ValueError('Concurrent native controller')
                    if inv['ledger']['requests'] >= budget['deepseek_inference_requests'] or inv['ledger']['cash_bound_nano'] >= int(budget['api_cash_usd'] * 1_000_000_000):
                        raise ValueError('Cumulative model budget exhausted')
                    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=project).strip():
                        raise ValueError('Uncommitted source: recovery launch refused')
                    intent = dict(task=decision['task'], mode=decision['mode'], source_run=decision['source_run'],
                                  id=uuid.uuid4().hex, status='LAUNCH_INTENT', at_unix=time.time())
                    state['launches'].append(intent)
                    # Intent is durable BEFORE any runner may read a credential or call a provider.
                    journal.append('LAUNCH_INTENT', intent); atomic(state_path, state)
                    argv = [config['python'], 'scripts/run_p6_main.py', decision['mode'], '--task', decision['task'],
                            '--detach', '--manifest', config['manifest_file']]
                    if decision['source_run']: argv += ['--reuse-run', decision['source_run']]
                    with (folder / (intent['id'] + '.launch.private.log')).open('xb') as log:
                        result = subprocess.run(argv, cwd=project, stdout=subprocess.PIPE, stderr=log, timeout=150)
                        log.write(result.stdout); log.flush(); os.fsync(log.fileno())
                    if result.returncode: raise RuntimeError('Frozen runner refused; intent preserved without replay')
                    receipt = json.loads(result.stdout); intent.update(receipt, status='STARTED')
                    state['native_boot_id'] = inv['native_boot_id']
                    journal.append('LAUNCHED', intent); atomic(state_path, state)
                    if once:
                        print(json.dumps({'status': 'STARTED', 'run_id': receipt['run_id']})); return
                elif decision['action'] in ('ALL_COMPLETED', 'FINISHED_WITH_PENDING_INTERRUPTED'):
                    state['status'] = decision['action']; atomic(state_path, state)
                    print(json.dumps({'status': decision['action'], 'pending': decision.get('pending', [])})); return
                elif once:
                    print(json.dumps({'status': decision['action'], 'ledger': inv['ledger']})); return
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                journal.append('RECOVERY_BLOCKED', {'error_type': type(error).__name__, 'message': str(error)[:180]})
                state.update(status='RECOVERY_BLOCKED', error_type=type(error).__name__, last_probe_unix=time.time())
                atomic(state_path, state)
                if once: raise
                # No paid retries, no credential reads; next inventory may become available.
            time.sleep(config.get('poll_seconds', 30))


def arm(project, batch, owner, destination):
    project = Path(project).resolve(); folder = contained(project, destination); folder.mkdir(parents=True, exist_ok=False)
    original = json.loads(contained(project, batch).read_bytes())
    manifest = json.loads(contained(project, original['manifest_file']).read_bytes())
    config = {'authorization': 'HUMAN_APPROVED_LOCAL_BOOT_RECOVERY_20261012', 'project': str(project),
              'python': sys.executable, 'batch_index': batch, 'manifest_file': original['manifest_file'],
              'manifest_sha256': manifest['manifest_sha256'], 'runner_source_sha256': manifest['runner_source_sha256'],
              'entrypoint_sha256': manifest['entrypoint_sha256'], 'authorization_sha256': manifest['budget_authorization_sha256'],
              'batch_started_unix': original['started_unix'], 'tasks': original['planned_tasks'],
              'modes': original['execution_modes'], 'original_owner': json.loads(contained(project, owner).read_bytes()),
              'windows_boot': host_identity()['boot'], 'poll_seconds': 30, 'native_boot_id': None}
    validate_sources(config)
    inv = native(config); config['native_boot_id'] = inv['native_boot_id']; config['ledger_floor'] = inv['ledger']['floor']
    config['supervisor_files'] = {}
    for name in ('p6_boot_recovery.py', 'p6_recovery_probe_linux.py'):
        data = Path(__file__).with_name(name).read_bytes(); (folder / name).write_bytes(data)
        config['supervisor_files'][name] = digest(data)
    atomic(folder / 'config.private.json', config); atomic(folder / 'enabled.private.json', {'enabled': True})
    Journal(folder / 'events.private.ndjson').append('ARMED_READ_ONLY', {'original_batch': batch, 'ledger': inv['ledger']})
    print(json.dumps({'config': str(folder / 'config.private.json'), 'model_calls': 0}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('arm'); a.add_argument('--project', required=True); a.add_argument('--batch-index', required=True)
    a.add_argument('--owner', required=True); a.add_argument('--destination', required=True)
    s = sub.add_parser('supervise'); s.add_argument('--config', required=True); s.add_argument('--execute', action='store_true'); s.add_argument('--once', action='store_true')
    args = p.parse_args()
    if args.command == 'arm': arm(args.project, args.batch_index, args.owner, args.destination)
    else:
        try: supervise(args.config, execute=args.execute, once=args.once)
        except SupervisorAlreadyRunning: print(json.dumps({'status': 'ANOTHER_SUPERVISOR_OWNS_LOCK'}))
