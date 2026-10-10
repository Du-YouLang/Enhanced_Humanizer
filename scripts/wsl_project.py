"""Run trusted setup/probes in the single approved project WSL distribution."""

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DISTRO = 'EnhancedHumanizer-P0'
BASE = '/opt/workbench'
ENV = {
    'HUMANIZE_HOME': BASE + '/state/humanize',
    'HUMANIZE_SENTRY': 'off',
    'DSH_HOME': BASE + '/state/dsh',
    'CODEX_HOME': BASE + '/state/codex',
    'XDG_CACHE_HOME': BASE + '/cache',
    'UV_CACHE_DIR': BASE + '/cache/uv',
    'UV_PYTHON_INSTALL_DIR': BASE + '/runtimes/python',
    'PKG_NATIVE_CACHE_PATH': BASE + '/cache/pkg',
    'TMPDIR': BASE + '/tmp',
    'PATH': ':'.join([
        BASE + '/.venv-linux/bin',
        BASE + '/tools/codex/0.162.0-alpha.2/bin',
        BASE + '/tools/uv/0.11.21/uv-x86_64-unknown-linux-gnu',
        '/usr/local/sbin', '/usr/local/bin', '/usr/sbin', '/usr/bin', '/sbin', '/bin',
    ]),
}


def run(argv, *, user='workbench', cwd=BASE, input_bytes=None, timeout=120):
    # No Windows credential/configuration variables are forwarded through WSLENV.
    child_env = os.environ | {'WSL_UTF8': '1', 'WSLENV': ''}
    command = ['wsl.exe', '-d', DISTRO, '-u', user, '--cd', cwd, '--exec',
               '/usr/bin/env', *(f'{key}={value}' for key, value in ENV.items()), *argv]
    return subprocess.run(command, cwd=ROOT, input=input_bytes, capture_output=True,
                          timeout=timeout, env=child_env, check=False)
