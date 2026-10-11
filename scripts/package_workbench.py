"""Build/verify/install a local preview; publishing is outside this command's scope."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from workbench.delivery import build, install, verify


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['build', 'verify', 'install'])
    p.add_argument('--output', type=Path)
    p.add_argument('--archive', type=Path)
    p.add_argument('--sha256')
    p.add_argument('--destination', type=Path)
    a = p.parse_args()
    if a.mode == 'build':
        if a.output is None: p.error('--output is required')
        result = build(ROOT, a.output)
    else:
        if not a.archive or not a.sha256: p.error('--archive and --sha256 are required')
        if a.mode == 'install':
            if not a.destination: p.error('--destination is required')
            result = install(a.archive, a.sha256, a.destination)
        else:
            m = verify(a.archive, a.sha256)
            result = {'status': 'VERIFIED', 'commit': m['commit'], 'file_count': len(m['files'])}
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
