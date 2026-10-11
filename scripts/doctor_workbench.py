"""Read-only readiness report; zero inference, auth refresh or remote Git calls."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def report(native=False):
    baselines = json.loads((ROOT/'docs/requirements/baselines.json').read_text(encoding='utf8'))
    source_ok = all(hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest() == s['sha256'] for s in baselines['sources'])
    static_ok = all((ROOT/'src/workbench/web'/p).is_file() for p in ['index.html','app.js','style.css'])
    git_ok = shutil.which('git') is not None
    python_ok = sys.version_info >= (3,12)
    preview = (ROOT/'.local-workbench/delivery/install-receipt.json').is_file()
    value = {'status':'LOCAL_UI_READY' if source_ok and static_ok and git_ok and python_ok else 'LOCAL_UI_NOT_READY',
             'project_root':str(ROOT),'python':sys.version.split()[0],'python_path':sys.executable,
             'checks':{'original_baselines':source_ok,'static_files':static_ok,'git':git_ok,'python_312_plus':python_ok,
                       'pyyaml':importlib.util.find_spec('yaml') is not None},
             'delivery_preview':preview,'model_execution':'DISABLED_IN_INSTALLED_PREVIEW' if preview else 'REQUIRES_EXISTING_PHASE_ACCEPTANCE_AND_BUDGET',
             'api_requests':0,'remote_git_operations':0,'publication':'DEFERRED_REQUIRES_HUMAN_CONFIRMATION'}
    if native:
        from wsl_project import run
        code='''import json,os,sys
from pathlib import Path
import importlib.metadata as m
print(json.dumps({'uid':os.getuid(),'python':sys.version.split()[0], 'pidfd':hasattr(os,'pidfd_open'),
 'humanize':m.version('hmz'), 'codex_auth_present':Path('/opt/workbench/state/codex/auth.json').is_file(),
 'dsh_present':Path('/opt/workbench/.venv-linux/bin/dsh').is_file(),
 'wsl_drive_mounts_disabled':not Path('/mnt/c/Windows').exists()}))
'''
        try:
            p = run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],timeout=25)
            if p.returncode: raise RuntimeError('Native preconditions could not be inspected')
            value['native'] = json.loads(p.stdout)
            value['native_readiness'] = 'PRECONDITIONS_INSPECTED_CONNECTIVITY_NOT_TESTED'
        except (OSError,RuntimeError,subprocess.TimeoutExpired):
            value['native_readiness'] = 'NOT_READY_OR_NOT_PRESENT'
    return value


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--native',action='store_true')
    args=parser.parse_args();value=report(args.native)
    print(json.dumps(value,indent=2));sys.exit(0 if value['status']=='LOCAL_UI_READY' else 1)
