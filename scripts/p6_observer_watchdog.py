"""Windows login/restart wrapper for the pinned read-only P6 observer only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_config(path):
    path = Path(path).resolve()
    value = read(path)
    project = Path(value['project']).resolve()
    if not path.is_relative_to(project / '.local-workbench/recovery'):
        raise ValueError('Watchdog must remain inside project recovery state')
    if sha(__file__) != value['watchdog_sha256']:
        raise ValueError('Watchdog source changed')
    source = Path(value['observer_config']).resolve()
    if not source.is_relative_to(project / '.local-workbench/recovery'):
        raise ValueError('Observer configuration is outside project recovery state')
    if sha(source) != value['observer_config_sha256']:
        raise ValueError('Observer configuration changed')
    observer = read(source)
    if (observer['mode'] != 'READ_ONLY_NO_DISPATCH' or observer['interval_seconds'] != 30
            or not all(observer[k] is True for k in ('no_models', 'no_ledger_edits', 'no_candidate_replay'))):
        raise ValueError('Only the existing read-only observer is permitted')
    script = source.parent / 'observe.py'
    inspector = Path(observer['inspector']).resolve()
    if (not inspector.is_relative_to(project / '.local-workbench')
            or sha(script) != observer['observer_sha256']
            or sha(inspector) != observer['inspector_sha256']):
        raise ValueError('Pinned observer or inspector changed')
    if Path(observer['project']).resolve() != project:
        raise ValueError('Observer project differs')
    pythonw = Path(observer['python']).resolve().with_name('pythonw.exe')
    if not pythonw.is_file():
        raise ValueError('Existing windowless interpreter is unavailable')
    return path, value, source, script, pythonw


def run(path, preflight=False):
    path, value, source, script, pythonw = checked_config(path)
    enabled = read(source.parent / 'enabled.private.json')['enabled']
    if preflight:
        return {'status': 'PREFLIGHT_PASS', 'enabled': enabled, 'models_started': 0}
    if enabled is not True:
        return {'status': 'DISABLED_BY_OWNER', 'models_started': 0}
    if os.name != 'nt':
        raise RuntimeError('Windows observer watchdog only')
    folder = path.parent
    def record(event):
        event.update(checked_at=datetime.now(timezone.utc).isoformat(), models_started=0,
                     ledger_mutations=0, mode='READ_ONLY_NO_DISPATCH')
        with (folder / 'events.private.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(event) + '\n')
            file.flush()
    with (folder / 'stdout.private.txt').open('ab') as stdout, (folder / 'stderr.private.txt').open('ab') as stderr:
        child = subprocess.Popen([str(pythonw), str(script), '--config', str(source)],
            cwd=value['project'], stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW)
        record({'status': 'OBSERVER_STARTED_OR_SINGLETON_CHECK', 'pid': child.pid})
        code = child.wait()
        record({'status': 'OBSERVER_EXITED', 'pid': child.pid, 'returncode': code})
    return {'status': 'OBSERVER_EXITED', 'returncode': code, 'models_started': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    result = run(args.config, args.preflight)
    if args.preflight:
        print(json.dumps(result))
    raise SystemExit(1 if result.get('returncode', 0) else 0)
