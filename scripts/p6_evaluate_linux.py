"""Hidden task acceptance in the existing Humanize fence/private namespace, never a Coding Harness."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

BASE = Path('/opt/workbench/benchmark')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def task_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in {'.', '..', '.git'} for p in path.parts):
        raise ValueError('Hidden material path escapes task')
    return path


def namespace(argv):
    return ['unshare', '--user', '--map-current-user', '--mount', '--pid', '--fork', '--mount-proc',
            '--kill-child=KILL', 'setpriv', '--no-new-privs', *argv]


def validate_source_links(source):
    # Windows CI may expose its workspace through a junction. Resolve the
    # existing root before walking so internal dangling links use the same base.
    source = Path(source).resolve()
    for directory, names, files in os.walk(source):
        if '.git' in names: names.remove('.git')
        for name in names+files:
            path = Path(directory)/name
            if path.is_symlink():
                target = Path(os.readlink(path))
                # Some upstream docs link to generated files not present in Git.
                # Preserve these internal dangling links; they grant no outside access.
                if target.is_absolute() or not path.resolve().is_relative_to(source.resolve()):
                    raise ValueError('Source symlink escapes the frozen task')


def pytest_statuses(cases,expected):
    groups={name:[] for name in expected};identities=set()
    for case in cases:
        identity=case.attrib.get('classname','')+'.'+case.attrib.get('name','')
        if identity in identities:raise ValueError('Duplicate full JUnit test identity')
        identities.add(identity)
        for name in expected:
            path,remainder=name.split('::',1)
            before,sep,parameter=remainder.partition('[')
            key=path.removesuffix('.py').replace('/','.')+'.'+before.replace('::','.')+sep+parameter
            if identity.split()[0]==key:groups[name].append(case)
    statuses={name:('PASS' if all(not any(c.tag in {'error','failure','skipped'} for c in case) for case in group) else 'FAIL') if group else 'UNMAPPED'
              for name,group in groups.items()}
    mapping={name:[case.attrib.get('classname','')+'.'+case.attrib.get('name','') for case in group] for name,group in groups.items()}
    return statuses,mapping


def evaluate(source, prefix, argv, hidden_files, *, timeout=120, expected_tests=None, test_patch=None,
             fixture_url=None, tls_regressions=False, test_framework='pytest',fixture_ca=None,
             writable_fixture_paths=(),local_tls_only=False):
    from hmz.coganchor.fence import Fence, wrapper
    if os.getuid() == 0:
        raise RuntimeError('Evaluator must never run as root')
    source = Path(source); prefix = Path(prefix)
    if not source.resolve().is_relative_to(BASE.resolve()) or not prefix.resolve().is_relative_to((BASE/'envs').resolve()):
        raise ValueError('Task source/environment outside project benchmark')
    if not (prefix/'bin/python').is_file() or not argv or argv[0] != str(prefix/'bin/python'):
        raise ValueError('The frozen task interpreter is required')
    validate_source_links(source)
    root = BASE/'private/evaluations'/uuid.uuid4().hex
    work = root/'code'; scratch = root/'tmp'; scratch.mkdir(parents=True)
    shutil.copytree(source, work, symlinks=True, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
    for name, raw in hidden_files.items():
        path = work/str(task_path(name))
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != work and parent.is_relative_to(work)):
            raise ValueError('Hidden test destination cannot alias candidate implementation')
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    if test_patch:
        # Default git apply rejects traversal. Test-only paths are independently checked.
        for line in test_patch.splitlines():
            if line.startswith(('+++ b/', '--- a/')):
                name = line[6:]; path = task_path(name)
                if (not str(path).startswith(('tests/', 'test_', 'testing/'))
                        and not re.fullmatch(r'sympy/(?:[A-Za-z0-9_]+/)*tests/test_[A-Za-z0-9_]+\.py',str(path))):
                    raise ValueError('Hidden test patch tried to change implementation')
        applied = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'apply', '--check', '-'], cwd=work,
                                 input=test_patch.encode(), capture_output=True, timeout=20)
        if applied.returncode:
            raise ValueError('Frozen test patch cannot apply to this task source')
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'apply', '-'], cwd=work,
                       input=test_patch.encode(), capture_output=True, check=True, timeout=20)
    # Python 3.8's http.server imports the host's MIME table even without network use.
    # Grant this one public system file read-only, rather than the entire /etc tree.
    system_read = ('/etc/mime.types',) if Path('/etc/mime.types').is_file() else ()
    if '/opt/workbench/source/p6_pytest_runner.py' in argv:
        system_read+=('/opt/workbench/source/p6_pytest_runner.py',)
    if '/opt/workbench/source/p6_sympy_runner.py' in argv:
        system_read+=('/opt/workbench/source/p6_sympy_runner.py',)
    hosts=()
    if fixture_url:
        from urllib.parse import urlsplit
        import socket
        parsed=urlsplit(fixture_url)
        if parsed.scheme!='http' or parsed.hostname!=socket.gethostname().lower() or not parsed.port or parsed.path not in ('','/'):
            raise ValueError('Only the trusted local HTTPBIN fixture is permitted')
        hosts=(parsed.netloc,)
    if tls_regressions:
        if not fixture_url:raise ValueError('TLS regressions require the Requests fixture contract')
        if not local_tls_only:hosts+=('httpbin.org:443',)
        system_read+=('/etc/ssl/certs/ca-certificates.crt',)
        if fixture_ca:
            ca=Path(fixture_ca).resolve()
            if not ca.is_relative_to(BASE/'public-fixtures') or not ca.is_file():raise ValueError('Invalid benchmark-scoped fixture CA')
            system_read+=(str(ca),)
        system_read+=('/opt/workbench/source/p6_requests_runner.py',)
        if '--frozen-selection' in argv:system_read+=('/opt/workbench/source/p6_pytest_runner.py',)
    fixture_writes=[]
    for name in writable_fixture_paths:
        path=work/str(task_path(name))
        if not str(name).startswith('tests/data/') or not path.is_file() or path.is_symlink():
            raise ValueError('Only frozen private-copy formatter fixtures may be writable')
        fixture_writes.append(str(path))
    fence = Fence.of(local='none', user='none', system='none', online=False, workdir=work,
                     home=root/'home', read=(str(work), str(prefix), *system_read), write=(str(scratch),*fixture_writes), hosts=hosts)
    fence = replace(fence, tmp=str(scratch))
    denied = [BASE/'private/gold', Path('/opt/workbench/state/codex/auth.json'), BASE/'bootstrap-receipt.json']
    # Probe real blocked files, without printing their contents or touching credentials.
    gold_probe = BASE/'private/gold/.denial-probe'; gold_probe.parent.mkdir(parents=True, exist_ok=True)
    if not gold_probe.exists(): gold_probe.write_text('non-secret project probe')
    denied[0] = gold_probe
    probe = '''import os,json,sys
from pathlib import Path
spec=json.loads(sys.argv[1]);rows=[]
for name in spec['denied']:
 try:Path(name).read_bytes();state='ALLOWED_FAILURE'
 except PermissionError:state='DENIED'
 except FileNotFoundError:state='MISSING_NOT_PROOF'
 rows.append(state)
try:
 with open(spec['environment_file'],'ab'):pass
 readonly='ALLOWED_FAILURE'
except PermissionError:readonly='DENIED'
print(json.dumps(dict(uid=os.getuid(),cap_eff=next(l.split()[-1] for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('CapEff:')),denied=rows,environment_write=readonly,pid_namespace=os.readlink('/proc/self/ns/pid'))))
'''
    env = {k: v for k, v in os.environ.items() if k in ('LANG', 'LC_ALL')}
    env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin', HOME=str(root/'home'), TMPDIR=str(scratch),
               PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='42', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(work/'src')+':'+str(work))
    if fixture_url:env['HTTPBIN_URL']=fixture_url
    if tls_regressions:env['REQUESTS_CA_BUNDLE']=str(fixture_ca or '/etc/ssl/certs/ca-certificates.crt')
    probe_result = subprocess.run(namespace([*wrapper(fence), str(prefix/'bin/python'), '-B', '-c', probe,
                                           json.dumps(dict(denied=[str(p) for p in denied], environment_file=str(prefix/'conda-meta/history')))]),
                                  cwd=work, env=env, capture_output=True, text=True, timeout=20)
    (root/'probe.private.log').write_text(probe_result.stdout+probe_result.stderr)
    if probe_result.returncode:
        raise RuntimeError('Actual evaluator fence probe failed: '+str(root))
    isolation = json.loads(probe_result.stdout)
    if isolation['uid'] == 0 or isolation['cap_eff'] != '0000000000000000' or isolation['denied'] != ['DENIED']*len(denied) or isolation['environment_write'] != 'DENIED' or isolation['pid_namespace'] == os.readlink('/proc/self/ns/pid'):
        raise RuntimeError('Evaluator isolation not verified')
    xml = scratch/'junit.xml'
    command = [arg.replace('{junit}', str(xml)) for arg in argv]
    tick = time.perf_counter()
    try:
        outcome = subprocess.run(namespace([*wrapper(fence), *command]), cwd=work, env=env,
                                 capture_output=True, text=True, timeout=timeout)
        raw = outcome.stdout+outcome.stderr
        (root/'test.private.log').write_text(raw)
        if expected_tests is not None:
            # Exact expected identities must all be represented. No zero-collection PASS.
            statuses = {}
            if test_framework=='sympy':
                # Same named-result convention as the pinned SWE-bench native
                # SymPy parser, with duplicate/missing names refused explicitly.
                observed={}
                for name,state in re.findall(r'^[ \t]*(test_[^ \t\r\n]+)[ \t]+(ok|F|E)(?:[ \t]+\[(?:OK|FAIL)\])?[ \t]*$',raw,re.MULTILINE):
                    observed.setdefault(name,[]).append(state)
                for name in expected_tests:
                    values=observed.get(name,[])
                    statuses[name]=('PASS' if values[0]=='ok' else 'FAIL') if len(values)==1 else 'UNMAPPED'
            elif test_framework=='pytest':
                cases = list(ET.parse(xml).iter('testcase')) if xml.exists() else []
                statuses,identity_mapping=pytest_statuses(cases,expected_tests)
            else:raise ValueError('Unapproved test framework')
            ran = len(statuses)
            verdict = 'INFRA_FAIL' if not ran or 'UNMAPPED' in statuses.values() else ('PASS' if outcome.returncode == 0 and all(x == 'PASS' for x in statuses.values()) else 'FAIL')
        else:
            match = re.search(r'Ran (\d+) tests? in ', raw)
            ran = int(match.group(1)) if match else 0; statuses = None
            verdict = ('INFRA_FAIL' if not ran or 'Failed to import test module' in raw else
                       ('PASS' if outcome.returncode == 0 else 'FAIL'))
        result = dict(verdict=verdict, exit_code=outcome.returncode, tests_observed=ran, test_statuses=statuses,
                      private_log_sha256=digest(raw.encode()))
        if expected_tests is not None and test_framework=='pytest':
            result.update(full_test_identities=identity_mapping,full_tests_observed=len(cases))
    except subprocess.TimeoutExpired:
        result = dict(verdict='TIMEOUT', tests_observed='unavailable', exit_code='unavailable')
    result.update(elapsed_seconds=time.perf_counter()-tick, isolation=isolation, evidence_root=str(root), model_requests=0,
                  public_system_files={name: digest(Path(name).read_bytes()) for name in system_read},
                  hidden_suite_sha256=digest(json.dumps({'files':{k:digest(v) for k,v in hidden_files.items()},
                        'patch':test_patch or '', 'argv':argv,'expected_tests':expected_tests,'test_framework':test_framework,
                        'writable_fixture_paths':list(writable_fixture_paths)},sort_keys=True).encode()))
    (root/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
