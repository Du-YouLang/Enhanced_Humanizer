"""Preserve incomplete synthetic DS working trees without rewriting model results or their refs."""

import json
from pathlib import Path

from p1_broker import protect_memory
from p2_candidates import BASE,digest,exclusive_json,run_tests,safe_git,validate_pool
from p3_contracts import read_json
from p3_runtime_linux import all_files,archive,clone_clean,trusted_git


def main():
    protect_memory();ledger=BASE/'state/p3-budget/ledger.json';before=digest(ledger.read_bytes());saved=[]
    for pool_path in (BASE/'runs').glob('p3-ds-return-*/frozen-pool.json'):
        pool=validate_pool(read_json(pool_path))
        for c in pool['candidates']:
            if c['verdict']=='PASS':continue
            work=pool_path.parent/c['id']/'worktree';root=work.parent/'partial-archive'
            if (root/'manifest.json').exists():saved.append(read_json(root/'manifest.json'));continue
            root.mkdir();target=root/'worktree';branch='archive/'+pool_path.parent.name+'/'+c['id']+'-partial'
            clone_clean(work,target,branch)
            files=all_files(work)
            for name,text in files.items():
                path=target/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            for name in all_files(target):
                if name not in files:(target/name).unlink()
            trusted_git(target,'add','--all')
            trusted_git(target,'commit','--allow-empty','-m','Program archive of incomplete DS '+c['id']+'; original '+c['verdict']+' is unchanged')
            row={'id':c['id']+'-partial','kind':'PROGRAM_PARTIAL_SNAPSHOT_NOT_MODEL_SUCCESS','verdict':c['verdict'],
                 'original_pool_hash':pool['pool_hash'],'original_head_commit':c['head_commit'],
                 'original_working_tree':c['working_tree'],'branch':branch,'head_commit':safe_git(target,'rev-parse','HEAD'),
                 'test_report':run_tests(target,independent=True,contract=pool['contract_manifest']),
                 'model_requests_added':0,'files_sha256':digest(files)}
            assert all_files(target)==files
            archive({'work':str(target),'root':str(root)},row);saved.append(row)
    assert before==digest(ledger.read_bytes())
    print(json.dumps({'partial_archives':len(saved),'model_requests_added':0,'ledger_sha256':before}))


if __name__=='__main__':main()
