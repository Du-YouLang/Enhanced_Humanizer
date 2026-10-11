"""Read only known P3 run traces; never traverse credential, cache, DB or symlink paths."""

import base64
import json
from pathlib import Path
import sys
import re

BASE=Path('/opt/workbench')


def main():
    spec=json.load(sys.stdin);output=[];size=0
    for item in spec:
        for key in ('run_id','role','candidate'):
            if item.get(key) and not re.fullmatch('[A-Za-z0-9_-]+',item[key]):raise ValueError('Invalid trace selector')
        root=BASE/'runs'/item['run_id']
        if not item['run_id'].startswith('p3-') or root.parent!=BASE/'runs':raise ValueError('Unknown historical run')
        if item.get('role'):
            attempt=root/'roles'/item['role']
            worker=json.loads((attempt/'worker.json').read_text())
            paths=[Path(worker['epic'])] if worker.get('epic') else []
        else:attempt=root/item['candidate'];paths=[attempt/'humanize']
        files=[]
        for folder in paths:
            if not folder.resolve().is_relative_to(attempt.resolve()):raise ValueError('Trace path outside its own role')
            files += [p for p in folder.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix in ('.jsonl','.log')]
        files += [p for p in attempt.glob('worker.*.private.log') if p.is_file() and not p.is_symlink()]
        for path in files:
            if not path.resolve().is_relative_to(attempt.resolve()):raise ValueError('Trace symlink escape')
            if any(word in path.name.lower() for word in ('auth','credential','token')):continue
            data=path.read_bytes();size+=len(data)
            if size>80_000_000:raise ValueError('Explicit trace import size cap exceeded')
            output.append({'node_id':item['node_id'],'source':str(path),'data':base64.b64encode(data).decode()})
    sys.stdout.write(json.dumps(output))


if __name__=='__main__':main()
