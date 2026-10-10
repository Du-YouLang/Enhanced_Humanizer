"""Install checksum-verified Linux runtimes into the approved project VHD only."""

from datetime import datetime, timezone
import hashlib
import json
import subprocess
import time

from wsl_project import BASE, ROOT, run


def checked(argv, *, input_bytes=None, timeout=120):
    tick = time.perf_counter()
    p = run(argv, input_bytes=input_bytes, timeout=timeout)
    row = {'argv': argv, 'exit_code': p.returncode,
           'elapsed_seconds': round(time.perf_counter()-tick, 6),
           'stdout': p.stdout.decode('utf-8', errors='replace'),
           'stderr': p.stderr.decode('utf-8', errors='replace')}
    print(json.dumps({k: v for k, v in row.items() if k not in ('stdout', 'stderr')}, ensure_ascii=True), flush=True)
    if p.returncode:
        raise RuntimeError('Linux setup step failed; no model was invoked')
    return row


def main():
    approval = json.loads((ROOT / '.local-workbench/approvals/wsl.json').read_text(encoding='utf-8-sig'))
    if approval.get('approved_by') != 'human_user' or not approval.get('system_components_allowed'):
        raise PermissionError('Project WSL setup is not authorized')
    tick = time.perf_counter()
    lock = json.loads((ROOT / 'configs/linux-tools.lock.json').read_text(encoding='utf-8'))
    rows = []
    runtime_check = '''import hashlib, os, signal, sys
assert sys.version.split()[0] == sys.argv[1], 'Ubuntu Python version changed'
assert hashlib.sha256(open(sys.executable,'rb').read()).hexdigest() == sys.argv[2], 'Ubuntu Python binary changed'
assert hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'), 'Native pidfd support missing'
print('Pinned native Ubuntu Python and pidfd support verified')
'''
    rows.append(checked(['/usr/bin/python3','-c',runtime_check,lock['python_version'],lock['python_sha256']]))
    for asset, destination in zip(lock['assets'], [BASE+'/tools/uv/0.11.21', BASE+'/tools/codex/0.162.0-alpha.2'], strict=True):
        archive = ROOT / '.local-workbench/wsl/downloads' / asset['name']
        with archive.open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != asset['sha256']:
                raise ValueError('Linux archive digest mismatch')
        code = '''import io, pathlib, sys, tarfile
target=pathlib.Path(sys.argv[1]); target.mkdir(parents=True,exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:
    archive.extractall(target, filter='data')
print('Extracted verified public tool archive into '+str(target))
'''
        rows.append(checked(['/usr/bin/python3','-c',code,destination], input_bytes=archive.read_bytes()))
    archive = subprocess.check_output(['git','archive','HEAD'], cwd=ROOT)
    code = '''import io, pathlib, sys, tarfile
target=pathlib.Path('/opt/workbench/source/project'); target.mkdir(parents=True,exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
    archive.extractall(target,filter='data')
print('Copied tracked public Git snapshot only; no ignored state or credentials')
'''
    rows.append(checked(['/usr/bin/python3','-c',code], input_bytes=archive))
    exists = run(['test','-f',lock['venv_path']+'/pyvenv.cfg'])
    if exists.returncode:
        rows.append(checked(['uv','venv','--python','/usr/bin/python3',lock['venv_path']]))
    rows.append(checked([lock['venv_path']+'/bin/python','-c',runtime_check,lock['python_version'],lock['python_sha256']]))
    for argv in (["uv", "--version"], ["codex", "--version"],
                 ["uv", "pip", "compile", "--python-version", "3.12", "--python-platform", "linux",
                  "--prerelease", "if-necessary-or-explicit", "--generate-hashes", "--no-build",
                  "--constraint", BASE+'/source/project/configs/requirements-p0-windows.lock',
                  "--output-file", BASE+'/source/project/configs/requirements-p0-linux.lock',
                  BASE+'/source/project/configs/requirements-p0.in'],
                 ["uv", "pip", "sync", "--python", lock['venv_path']+'/bin/python', "--require-hashes", "--no-build",
                  BASE+'/source/project/configs/requirements-p0-linux.lock']):
        rows.append(checked(argv, timeout=300))
    linux_lock = run(['cat', BASE+'/source/project/configs/requirements-p0-linux.lock'])
    if linux_lock.returncode:
        raise RuntimeError('Linux lock export failed')
    (ROOT/'configs/requirements-p0-linux.lock').write_bytes(linux_lock.stdout)
    record = {'observed_at':datetime.now(timezone.utc).isoformat(),'steps':rows,
              'elapsed_seconds':round(time.perf_counter()-tick,6),'model_requests':0}
    (ROOT/'.local-workbench/audits/linux-tools-native-install.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
