"""Trusted, non-root P6 preparation; downloads and environments remain in the project VHD."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
import argparse

BASE = Path('/opt/workbench/benchmark')
MINIFORGE_VERSION = '26.7.2-0'
MINIFORGE_SHA256 = '281b0ac7d550802efc81af633225a5e6116d29ae72f3ab4eae7168c3931a4c05'


def confined(path):
    path = Path(path)
    if not path.resolve().is_relative_to(BASE.resolve()):
        raise ValueError('Preparation path escapes project benchmark state')
    return path


def setup_env():
    if os.name != 'posix' or os.getuid() == 0:
        raise RuntimeError('Native Linux, non-root workbench account required')
    BASE.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not any(word in k.upper() for word in ('TOKEN', 'API_KEY', 'PASSWORD'))}
    env.update(HOME=str(BASE/'setup-home'), XDG_CACHE_HOME=str(BASE/'cache'),
               CONDA_PKGS_DIRS=str(BASE/'cache/conda'), CONDA_ENVS_PATH=str(BASE/'envs'),
               TMPDIR=str(BASE/'tmp'), PIP_CACHE_DIR=str(BASE/'cache/pip'),
               GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0', PYTHONDONTWRITEBYTECODE='1')
    for key in ('HOME', 'XDG_CACHE_HOME', 'CONDA_PKGS_DIRS', 'TMPDIR', 'PIP_CACHE_DIR'):
        confined(env[key]).mkdir(parents=True, exist_ok=True)
    return env


def fetch(url, target, expected):
    target = confined(target)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError('Existing download differs; preserve it and investigate')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix+'.partial')
    with urllib.request.urlopen(url, timeout=60) as source, partial.open('xb') as dest:
        while data := source.read(1024*1024):
            dest.write(data)
    if hashlib.sha256(partial.read_bytes()).hexdigest() != expected:
        raise ValueError('Downloaded artifact SHA256 differs')
    partial.rename(target)


def bootstrap():
    tick = time.perf_counter(); env = setup_env(); prefix = BASE/'conda'
    installer = BASE/'downloads'/f'Miniforge3-{MINIFORGE_VERSION}-Linux-x86_64.sh'
    receipt = dict(operation='P6_CONDA_BOOTSTRAP', model_requests=0, uid=os.getuid(),
                   version=MINIFORGE_VERSION, installer_sha256=MINIFORGE_SHA256, prefix=str(prefix))
    log = BASE/'bootstrap.private.log'
    try:
        fetch(f'https://github.com/conda-forge/miniforge/releases/download/{MINIFORGE_VERSION}/Miniforge3-Linux-x86_64.sh', installer, MINIFORGE_SHA256)
        if not (prefix/'bin/conda').exists():
            if prefix.exists():
                raise RuntimeError('Partial installation preserved; no overwrite')
            with log.open('ab') as handle:
                subprocess.run(['/bin/bash', str(installer), '-b', '-p', str(prefix)], env=env,
                               stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=600)
        receipt.update(status='PASS', conda_version=subprocess.check_output([str(prefix/'bin/conda'), '--version'], env=env, text=True).strip())
    except Exception as error:
        receipt.update(status='INFRA_FAIL', error_type=type(error).__name__)
    receipt['preparation_seconds'] = time.perf_counter()-tick
    (BASE/'bootstrap-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def checkout(repository, commit, target):
    """Trusted source clone with only the requested commit; gold history is kept elsewhere."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Public repository and exact revision required')
    target = confined(target); env = setup_env()
    git = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-c', 'credential.helper=']
    if not target.exists():
        target.mkdir(parents=True)
        log = target.parent/(target.name+'-checkout.private.log')
        with log.open('ab') as handle:
            for command in [git+['init', str(target)],
                            git+['-C', str(target), 'fetch', '--no-tags', '--depth', '1', 'https://github.com/'+repository+'.git', commit],
                            git+['-C', str(target), 'checkout', '--detach', 'FETCH_HEAD']]:
                subprocess.run(command, env=env, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=180)
    actual = subprocess.check_output(git+['-C', str(target), 'rev-parse', 'HEAD'], env=env, text=True).strip()
    dirty = subprocess.check_output(git+['-C', str(target), 'status', '--porcelain'], env=env, text=True)
    if actual != commit or dirty or (target/'.git/objects/info/alternates').exists():
        raise ValueError('Prepared source is not the clean independently frozen commit')
    return dict(base_commit=actual, source=str(target), independent_objects=True)


def seal_environment(prefix, task_id):
    prefix = confined(prefix); env = setup_env()
    if not prefix.resolve().is_relative_to((BASE/'envs').resolve()):
        raise ValueError('Only project task environments can be sealed')
    inventory = {}
    for path in sorted(prefix.rglob('*')):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            inventory[str(path.relative_to(prefix))] = {'symlink': os.readlink(path)}
        elif path.is_file():
            inventory[str(path.relative_to(prefix))] = hashlib.sha256(path.read_bytes()).hexdigest()
    explicit = subprocess.check_output([str(BASE/'conda/bin/conda'), 'list', '--prefix', str(prefix), '--explicit', '--md5'], env=env, text=True)
    packages = subprocess.check_output([str(prefix/'bin/python'), '-m', 'pip', 'freeze', '--all'], env=env, text=True)
    value = dict(prefix=str(prefix), file_inventory=inventory, conda_explicit=explicit, pip_freeze=packages,
                 python=subprocess.check_output([str(prefix/'bin/python'), '--version'], env=env, text=True).strip())
    value['env_sha256'] = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    file = BASE/'private/environment-seals'/f'{task_id}.json';file.parent.mkdir(parents=True, exist_ok=True)
    if file.exists() and json.loads(file.read_text()) != value:
        raise ValueError('Sealed environment changed; preserve and version the preparation')
    if not file.exists():
        with file.open('x') as handle:json.dump(value, handle, indent=2)
    return dict(env_sha256=value['env_sha256'], file_count=len(inventory), python=value['python'])


def black_smoke(job):
    """Reproducible preparation/positive-negative control; no model execution or budget use."""
    from p6_evaluate_linux import evaluate
    tick = time.perf_counter(); env = setup_env(); task_id = 'BIP-black-2'
    if job.get('task_id') != task_id or job.get('python_version') != '3.8.3':
        raise ValueError('This preparer only supports the frozen Black smoke contract')
    source = BASE/'sources'/task_id; gold = BASE/'private/gold'/task_id
    checkout('psf/black', job['buggy_commit_id'], source)
    checkout('psf/black', job['fixed_commit_id'], gold)
    prefix = BASE/'envs/black-py383'; log = BASE/'black-smoke-preparation.private.log'
    with log.open('ab') as handle:
        if not (prefix/'bin/python').exists():
            subprocess.run([str(BASE/'conda/bin/conda'), 'create', '--yes', '--prefix', str(prefix),
                            '--override-channels', '--channel', 'conda-forge', 'python=3.8.3', 'pip=23.3.2', '--no-default-packages'],
                           env=env, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=600)
        seal_file = BASE/'private/environment-seals'/f'{task_id}.json'
        if not seal_file.exists():
            packages = ['appdirs==1.4.3', 'attrs==19.3.0', 'click==7.1.1', 'pathspec==0.7.0', 'toml==0.10.0',
                        'regex==2020.2.20', 'typed-ast==1.4.0', 'mypy-extensions==0.4.3', 'aiohttp==3.6.2',
                        'aiohttp-cors==0.7.0', 'typing-extensions==3.7.4.1', 'setuptools-scm==3.5.0']
            subprocess.run([str(prefix/'bin/python'), '-m', 'pip', 'install', *packages], env=env,
                           stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=300)
            subprocess.run([str(prefix/'bin/python'), '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', str(source)],
                           env=env, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=120)
    seal = seal_environment(prefix, task_id)
    hidden = {'tests/test_black.py': (gold/'tests/test_black.py').read_bytes(), 'tests/__init__.py': b'',
              'tests/data/fmtonoff4.py': (gold/'tests/data/fmtonoff4.py').read_bytes()}
    argv = [str(prefix/'bin/python'), '-B', '-m', 'unittest', '-q', 'tests.test_black.BlackTestCase.test_fmtonoff4']
    results = {name: evaluate(path, prefix, argv, hidden) for name, path in [('buggy', source), ('gold', gold)]}
    receipt = dict(task_id=task_id, status='EVALUATOR_VALIDATED' if results['buggy']['verdict']=='FAIL' and results['gold']['verdict']=='PASS' else 'INFRA_FAIL',
                   base_commit=job['buggy_commit_id'], results=results, environment=seal,
                   preparation_seconds=time.perf_counter()-tick, model_requests=0)
    directory=BASE/'private/preparation-attempts';directory.mkdir(exist_ok=True,parents=True)
    with (directory/(str(time.time_ns())+'-black.json')).open('x') as handle:json.dump(receipt,handle,indent=2)
    return {key: receipt[key] for key in ('task_id','status','environment','preparation_seconds','model_requests')}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--black-smoke', action='store_true')
    args=parser.parse_args()
    if args.black_smoke:
        import sys
        print(json.dumps(black_smoke(json.load(sys.stdin))))
    else:print(json.dumps(bootstrap()))
