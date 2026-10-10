"""Independent zero-model replay of completed P3 roles, immutable handoffs and frozen suites."""

import json
from pathlib import Path
import sys
import time

from p1_broker import protect_memory
from p2_candidates import BASE,digest,exclusive_json,safe_git,run_tests,validate_pool
from p3_contracts import read_json,validate_handoff,validate_checkpoint
from p3_runtime_linux import STAGES,all_files,candidate_work,design_check,load_stage


def main():
    protect_memory();tick=time.perf_counter();payload=json.load(sys.stdin)
    ledger=BASE/'state/p3-budget/ledger.json';before=digest(ledger.read_bytes())
    prior={phase:digest((BASE/'state'/(phase.lower()+'-budget')/'ledger.json').read_bytes()) for phase in ('P1','P2')}
    assert prior==payload['prior_ledgers']
    completed={}
    for path in (BASE/'evidence').glob('p3-*-segment-*.json'):
        value=read_json(path)
        if value['status']=='COMPLETED' and value['functional_gate']=='PASS':completed[value['case']]=value
    assert set(completed)=={'mixed','all-failed','impossible'}
    sessions=set();tests=[];denials=0;checkpoints=[]
    for case,record in completed.items():
        root=BASE/'runs'/record['run_id'];contract=read_json(root/'control/run-contract.json')
        body=dict(contract);assert digest({k:v for k,v in body.items() if k!='contract_hash'})==body['contract_hash']
        pool=validate_pool(read_json(contract['pool_path']));assert pool['pool_hash']==record['pool_hash']
        package=validate_handoff(read_json(root/'inputs/initial-handoff.json'))
        assert package['pool_hash']==pool['pool_hash']
        if 'contract_manifest' in pool:
            assert pool['contract_manifest']['acceptance_test_program'] not in json.dumps(package)
        for c in pool['candidates']:
            work=candidate_work(contract['pool_path'],c['id'])
            assert safe_git(work,'rev-parse','HEAD')==c['head_commit'] and not safe_git(work,'status','--porcelain')
            supplied=next(v for v in package['candidates'] if v['id']==c['id'])
            assert supplied['files']==all_files(work)
            replay=run_tests(work,independent=True,contract=pool.get('contract_manifest'))
            assert replay['suite_sha256']==c['test_report']['suite_sha256'] and replay['verdict']==c['test_report']['verdict']
            tests.append({'case':case,'id':c['id'],'verdict':replay['verdict'],'suite_sha256':replay['suite_sha256']})
        for stage in STAGES:load_stage(root,stage)
        for path in sorted((root/'control').glob('checkpoint-*.json')):
            value=validate_checkpoint(read_json(path),contract['contract_hash'])
            for stage in value['stages']:assert load_stage(root,stage['name'])['record_sha256']==stage['result_sha256']
        final=read_json(root/'control/checkpoint-7.json');assert final['next_step']==7
        checkpoints.append({'case':case,'completed_stages':7,'checkpoint_sha256':digest(final)})
        for path in (root/'roles').glob('*/worker.json'):
            worker=read_json(path);assert worker['status']=='COMPLETED' and worker['kind']=='REAL_MODEL_EXPERIMENT'
            assert worker['model_id']=='gpt-6.1-sol' and worker['uid']!=0 and worker['cap_eff']=='0000000000000000'
            assert worker['session_id'] not in sessions;sessions.add(worker['session_id'])
            isolation=read_json(path.parent/'isolation.json');assert isolation['verdict']=='PASS'
            assert all(r['read']==r['write']=='DENIED' for r in isolation['paths'])
            assert all(r['write']=='DENIED' for r in isolation['readonly'])
            denials+=2*len(isolation['paths'])+len(isolation['readonly'])
        merged=load_stage(root,'verify_m');work=root/'roles/reviewer/worktree'
        replay=run_tests(work,independent=True,contract=pool.get('contract_manifest'))
        assert replay['suite_sha256']==merged['test_report']['suite_sha256'] and replay['verdict']==merged['test_report']['verdict']
        if merged['verdict']=='PASS':
            assert safe_git(work,'rev-parse','HEAD')!=pool['base_commit'] and not safe_git(work,'status','--porcelain')
            assert merged['frozen_test_unchanged'] and merged['independent_object_store']
        tests.append({'case':case,'id':'M','verdict':replay['verdict'],'role_verdict':merged['verdict'],'suite_sha256':replay['suite_sha256']})
        if case=='impossible':assert record['task_status']=='FAIL' and record['comparison']['selected_candidate'] is None
        if case=='mixed':
            segments=[read_json(p) for p in sorted((root/'control').glob('segment-*.json'))]
            assert len(segments)==2 and segments[0]['status']=='PAUSED' and segments[1]['status']=='COMPLETED'
            assert len(read_json(root/'control/pause-2.json')['stages'])==2
            builder=load_stage(root,'builder');assert builder['verdict']=='PASS'
            replay=run_tests(root/'roles/builder/worktree',independent=True,contract=pool.get('contract_manifest'))
            assert replay['verdict']=='PASS' and replay['suite_sha256']==builder['test_report']['suite_sha256']
            tests.append({'case':'Sol-Builder','id':'S','verdict':'PASS','suite_sha256':replay['suite_sha256']})
            assert design_check(root/'roles/builder/worktree')['verdict']=='PASS'
            assert safe_git(root/'roles/builder/worktree','rev-parse','HEAD')==builder['head_commit']
            returned=load_stage(root,'ds_return');newpool=validate_pool(read_json(returned['pool_path']))
            assert newpool['base_commit']==builder['head_commit']
            assert any(c['verdict']=='PASS' for c in newpool['candidates'])
            for c in newpool['candidates']:
                assert c['isolation']['verdict']=='PASS'
                if c['worker_status']=='COMPLETED':
                    assert c['session_id']!='unavailable' and c['session_id'] not in sessions;sessions.add(c['session_id'])
                else:
                    assert c['verdict'] in ('BUDGET_EXHAUSTED','TIMEOUT','INFRA_FAIL')
                work=candidate_work(returned['pool_path'],c['id'])
                replay=run_tests(work,independent=True,contract=newpool['contract_manifest'])
                assert replay['verdict']==c['test_report']['verdict'] and replay['suite_sha256']==c['test_report']['suite_sha256']
                assert safe_git(work,'rev-parse','HEAD')==c['head_commit']
                assert safe_git(work,'status','--porcelain')==c['working_tree']
                if c['verdict']!='PASS':
                    partial=read_json(work.parent/'partial-archive/manifest.json')
                    assert partial['kind']=='PROGRAM_PARTIAL_SNAPSHOT_NOT_MODEL_SUCCESS' and partial['verdict']==c['verdict']
                    assert all_files(work.parent/'partial-archive/worktree')==all_files(work)
                tests.append({'case':'DS-return','id':c['id'],'verdict':replay['verdict'],'role_verdict':c['verdict'],
                              'session_id':c['session_id'],'suite_sha256':replay['suite_sha256']})
    for source,sha in payload['source_sha256'].items():
        path=BASE/'source'/(source.removeprefix('scripts/') if source.startswith('scripts/') else source.replace('.hmz/',''))
        assert digest(path.read_bytes())==sha,(source,'deployment changed')
    assert before==digest(ledger.read_bytes())
    value={'verdict':'PASS','kind':'INDEPENDENT_ZERO_MODEL_FINAL_REPLAY','model_requests_added':0,
           'cases':sorted(completed),'frozen_test_replays':tests,'checkpoints':checkpoints,
           'unique_current_model_sessions':len(sessions),'actual_runtime_access_denials':denials,
           'ledger_sha256':before,'prior_ledger_sha256':prior,'source_sha256':payload['source_sha256'],
           'elapsed_seconds':time.perf_counter()-tick}
    path=BASE/'evidence'/('p3-final-replay-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.json')
    exclusive_json(path,value);print(json.dumps({'path':str(path),'verdict':'PASS','elapsed_seconds':value['elapsed_seconds'],'test_replays':len(tests)}))


if __name__=='__main__':main()
