"""Offline from-empty-project task-contract and authenticated-cache replay checks; zero requests."""

import json
from pathlib import Path
import sys
import time

from p1_broker import protect_memory
from p2_candidates import BASE,digest,prepare,finalize,freeze,validate_pool,exclusive_json,safe_git
from p2_contract import validate_contract
from p2_judges import J1


def main():
    protect_memory();started=time.perf_counter()
    ledger=BASE/'state/p2-budget/ledger.json';before=digest(ledger.read_bytes())
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    base_root=BASE/'source'/('p2-empty-base-'+stamp);base_root.mkdir()
    from p1_experiment_linux import git
    git(base_root,'init','-b','fixture/base');git(base_root,'config','user.name','Workbench Fixture');git(base_root,'config','user.email','fixture@example.invalid')
    (base_root/'.gitignore').write_text('__pycache__/\n.hmz/\n')
    git(base_root,'add','.');git(base_root,'commit','-m','Empty-project contract fixture')
    env_hash=json.loads(next((BASE/'runs').glob('p2-n1-*/frozen-pool.json')).read_text())['env_hash']
    visible='from square import square\nassert square(3)==9\n'
    contract=validate_contract({'task_id':'from-empty-offline-fixture','prompt':'Create square.py with square(value), implement and test the complete tiny project, then commit.',
        'base_repository':str(base_root),'base_commit':git(base_root,'rev-parse','HEAD'),'env_hash':env_hash,
        'source_file':'square.py','visible_test_program':visible,'acceptance_test_program':visible+'assert square(-4)==16\n',
        'protected_files':{'.gitignore':digest((base_root/'.gitignore').read_bytes())}},env_hash)
    root=BASE/'runs'/('p2-control-custom-'+stamp);base,jobs=prepare(root,1,contract);job=jobs[0]
    assert not (Path(job['work'])/'square.py').exists()
    missing=finalize(job,{'kind':'CONTROLLED_FAULT_INJECTION','status':'COMPLETED'},{},0,env_hash)
    assert missing['verdict']=='FAIL','Missing requested output is model/task failure, not infrastructure failure'
    (Path(job['work'])/'square.py').write_text('def square(value):\n    return value * value\n')
    git(job['work'],'add','.');git(job['work'],'commit','-m','Controlled complete tiny project; no model used')
    row=finalize(job,{'kind':'CONTROLLED_FAULT_INJECTION','status':'COMPLETED'},{},0,env_hash)
    assert row['verdict']=='PASS'
    pool=validate_pool(freeze(root,[row],base,env_hash,contract))
    bundle=root/'A.bundle';scratch=Path(job['root'])/'verify-tmp/candidate.bundle'
    safe_git(job['work'],'bundle','create',str(scratch),'--all');bundle.write_bytes(scratch.read_bytes())
    original=json.loads(next((BASE/'runs').glob('p2-n3-*/frozen-pool.json')).read_text())
    class NoNetwork:
        probability_evidence=[]
        requests_sent=0
        def __getattr__(self,name):raise RuntimeError('A validated cache replay must never call a provider')
    cached=J1(NoNetwork(),'/opt/workbench/upstreams/lav',BASE/'state/p2-judge-cache').judge(original)
    assert cached['requests']==0 and cached['probability_evidence']
    assert before==digest(ledger.read_bytes())
    report={'verdict':'PASS','kind':'OFFLINE_CONTRACT_AND_CACHE','custom_task_pool_hash':pool['pool_hash'],
            'custom_task_run_id':root.name,'from_empty_project':'PASS_OFFLINE_ONLY','missing_output_classification':missing['verdict'],
            'cache_replay':cached,'model_requests_added':0,'ledger_sha256_before':before,'ledger_sha256_after':digest(ledger.read_bytes()),
            'elapsed_seconds':time.perf_counter()-started}
    exclusive_json(BASE/'evidence'/('p2-contract-cache-'+stamp+'.json'),report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
