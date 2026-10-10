"""Read registered P5 evidence through safe Git/file readers; no model calls."""
import base64
import json
from pathlib import Path
import re
import sys
from p2_candidates import BASE,safe_source,safe_git
from p3_runtime_linux import all_files


def main():
    run_id=sys.argv[1]
    if not re.fullmatch('p5-[a-z0-9-]+',run_id):raise ValueError('Invalid run selector')
    root=BASE/'runs'/run_id
    if not root.exists():print('{}');return
    value={'run_id':run_id,'stages':{},'roles':{},'traces':[],'bundles':[]}
    resume=root/'control/resume.json'
    terminal=json.loads(resume.read_text())['status'] if resume.exists() else None
    for file in (root/'results').glob('*.json'):value['stages'][file.stem]=json.loads(file.read_text())
    for file in (root/'roles').glob('*/worker.json'):
        role=file.parent.name;worker=json.loads(file.read_text());value['roles'][role]=worker
        work=file.parent/'worktree'
        if (work/'.git').exists():
            worker['partial_files']=all_files(work)
            worker['head_commit']=safe_git(work,'rev-parse','HEAD')
            if terminal in ('CANCELLED','INFRA_FAIL','TIMEOUT') and not (file.parent/'candidate.bundle').exists():
                scratch=file.parent/'verify-tmp/partial.bundle'
                safe_git(work,'bundle','create',str(scratch),'--all')
                (file.parent/'candidate.bundle').write_bytes(scratch.read_bytes())
        folders=[Path(worker['epic'])] if worker.get('epic') else []
        logs=list(file.parent.glob('worker.*.private.log'))
        for folder in folders:
            if folder.resolve().is_relative_to(file.parent.resolve()):logs += list(folder.rglob('*.jsonl'))
        for log in logs:
            if log.is_symlink() or not log.resolve().is_relative_to(file.parent.resolve()) or log.stat().st_size>20_000_000:continue
            value['traces'].append({'role':role,'path':str(log),'data':base64.b64encode(log.read_bytes()).decode()})
        bundle=file.parent/'candidate.bundle'
        if bundle.exists():value['bundles'].append({'role':role,'data':base64.b64encode(bundle.read_bytes()).decode()})
    candidates=value['stages'].get('candidates',{})
    pool_path=Path(candidates['pool_path']) if candidates.get('pool_path') else root.parent/(run_id+'-pool')/'frozen-pool.json'
    value['pool_path']=str(pool_path)
    if pool_path.exists():
        value['pool']=json.loads(pool_path.read_text())
        for row in value['pool']['candidates']:
            cid=row['id'];attempt=pool_path.parent/cid
            bundle=pool_path.parent/(cid+'.bundle')
            if bundle.exists():value['bundles'].append({'candidate':cid,'data':base64.b64encode(bundle.read_bytes()).decode()})
            row['partial_files']=all_files(attempt/'worktree')
            for log in list((attempt/'humanize').rglob('*.jsonl'))+list(attempt.glob('worker.*.private.log')):
                if log.is_symlink() or not log.resolve().is_relative_to(attempt.resolve()) or log.stat().st_size>20_000_000:continue
                value['traces'].append({'candidate':cid,'path':str(log),'data':base64.b64encode(log.read_bytes()).decode()})
    if resume.exists():value['resume']=json.loads(resume.read_text())
    ledger=BASE/'state/p5-budget/ledger.json'
    if ledger.exists():value['ledger']=json.loads(ledger.read_text())
    print(json.dumps(value))


if __name__=='__main__':main()
