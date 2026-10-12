"""Run the frozen public tests with public build/trust overlays in a scratch copy.

This runs within the model's existing OS fence. It receives no hidden tests or
reference patches, and never edits the coding worktree or installed environment.
Compatible with the frozen Python 3.8 task interpreter.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--contract',required=True)
    args=p.parse_args();value=json.loads(Path(args.contract).read_text())
    with tempfile.TemporaryDirectory(prefix='p6-visible-',dir=os.environ['TMPDIR']) as temp:
        work=Path(temp)/'code'
        shutil.copytree(Path.cwd(),work,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc'),symlinks=True)
        for name,encoded in value['public_overlays'].items():
            target=work/name
            if os.path.commonpath((str(target.resolve()),str(work.resolve())))!=str(work.resolve()):raise ValueError('Public overlay escapes scratch copy')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(base64.b64decode(encoded))
        argv=[word.replace('{junit}',str(Path(temp)/'junit.xml')) for word in value['argv']]
        env=dict(os.environ);env.update(PYTHONPATH=str(work/'src')+':'+str(work),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(argv,cwd=work,env=env,timeout=90)
        return result.returncode


if __name__=='__main__':raise SystemExit(main())
