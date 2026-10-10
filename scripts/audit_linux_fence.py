"""Real OS denial tests on synthetic fixtures; never open actual credential contents."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from hmz.coganchor.fence import Fence, enforceable, wrapper


def main():
    started = time.perf_counter()
    root = Path('/opt/workbench/runs') / ('fence-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    candidate, sibling, protected = (root / name for name in ('candidate-a', 'candidate-b', 'protected'))
    for path in (candidate, sibling, protected, root / 'scratch'):
        path.mkdir(parents=True)
    (sibling / 'result.txt').write_text('NONSECRET_SIBLING_FIXTURE\n')
    (protected / 'credential-canary.txt').write_text('NONSECRET_CREDENTIAL_FIXTURE\n')
    (protected / 'keep.txt').write_text('NONSECRET_DELETE_FIXTURE\n')

    def git(*args, cwd=candidate):
        return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.STDOUT).decode().strip()

    git('init', '-b', 'run/p0/a')
    git('config', 'user.name', 'Workbench Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    (candidate / 'fixture.txt').write_text('base\n')
    git('add', 'fixture.txt')
    git('commit', '-m', 'synthetic base')
    base = git('rev-parse', 'HEAD')
    authority = protected / 'authority.git'
    git('init', '--bare', '-b', 'main', str(authority))
    git('--git-dir='+str(authority), 'fetch', str(candidate), 'HEAD:refs/heads/main')
    # Explicit path grants avoid local=all's shared /tmp grant. No linked Git object store.
    fence = Fence.of(local='none', user='none', system='none', online=False,
                     workdir=candidate, home=Path.home(), write=(candidate, root/'scratch'))
    from dataclasses import replace
    fence = replace(fence, tmp=str(root/'scratch'))
    rows = []

    def check(name, code, expected):
        tick = time.perf_counter()
        p = subprocess.run([*wrapper(fence), sys.executable, '-c', code], cwd=candidate,
                           capture_output=True, text=True, timeout=30)
        rows.append({'name': name, 'exit_code': p.returncode, 'expected': expected,
                     'passed': (p.returncode == 0) if expected == 'allow' else (p.returncode != 0),
                     'elapsed_seconds': round(time.perf_counter()-tick,6),
                     'stdout': p.stdout, 'stderr': p.stderr})

    check('candidate_write_and_commit', "import pathlib,subprocess; pathlib.Path('fixture.txt').write_text('edited\\n'); subprocess.run(['git','add','fixture.txt'],check=True); subprocess.run(['git','commit','-m','fenced edit'],check=True)", 'allow')
    check('outside_write', f"from pathlib import Path; Path({str(protected/'new.txt')!r}).write_text('deny')", 'deny')
    check('sibling_read', f"from pathlib import Path; Path({str(sibling/'result.txt')!r}).read_bytes()", 'deny')
    check('credential_fixture_read', f"from pathlib import Path; Path({str(protected/'credential-canary.txt')!r}).read_bytes()", 'deny')
    check('symlink_escape_read', f"from pathlib import Path; p=Path('escape'); p.symlink_to({str(protected/'credential-canary.txt')!r}); p.read_bytes()", 'deny')
    check('authority_main_ref_update', f"import subprocess; subprocess.run(['git','--git-dir={authority}','update-ref','refs/heads/main','{base}'],check=True)", 'deny')
    check('force_push_to_authority', f"import subprocess; subprocess.run(['git','push','--force','{authority}','HEAD:main'],check=True)", 'deny')
    check('delete_outside_candidate', f"from pathlib import Path; Path({str(protected/'keep.txt')!r}).unlink()", 'deny')
    check('direct_tcp', "import socket; socket.create_connection(('1.1.1.1',443),timeout=3)", 'deny')
    check('unapproved_proxy_host', "import urllib.request; urllib.request.urlopen('https://github.com',timeout=3)", 'deny')
    check('windows_interop_execute', "import subprocess; subprocess.run(['cmd.exe','/c','ver'],check=True)", 'deny')
    # Host mount absence checked outside the fence too: denial is not merely a missing grant.
    mounts = Path('/proc/mounts').read_text()
    host_mounts_absent = not any(line.split()[1] in ('/mnt/c','/mnt/d') for line in mounts.splitlines())
    authority_unchanged = git('--git-dir='+str(authority), 'rev-parse','refs/heads/main') == base
    result = {'schema_version':1, 'observed_at':datetime.now(timezone.utc).isoformat(),
              'verdict':'PASS' if all(row['passed'] for row in rows) and authority_unchanged and host_mounts_absent and enforceable(net=True) else 'INFRA_FAIL',
              'uid':os.getuid(),'kernel':os.uname().release,
              'filesystem_enforceable':enforceable(net=False),'network_enforceable':enforceable(net=True),
              'windows_drives_unmounted':host_mounts_absent,'authority_ref_unchanged':authority_unchanged,
              'fixture_only':True, 'root':str(root), 'policy':json.loads(fence.dumps()),
              'cases':rows,'elapsed_seconds':round(time.perf_counter()-started,6),
              'limitations':['Not a malicious-kernel boundary','CLI needs access to its own login state; host credentials remain inaccessible','Private candidate Git history can be rewritten; authoritative refs are outside the writable fence','No shared candidate object store; cross-candidate session isolation requires separate state roots']}
    destination = Path('/opt/workbench/evidence') / (root.name+'.json')
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['verdict']=='PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
