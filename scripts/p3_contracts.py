"""Pure P3 contracts: frozen evidence, no hidden answers, and explicit unsuccessful outcomes."""

import json
from pathlib import Path

from p2_candidates import digest, validate_pool, failure_report


def handoff(pool, files, visible_reports, judgments=()):
    validate_pool(pool)
    ids={c['id'] for c in pool['candidates']}
    if set(files)!=ids or set(visible_reports)!=ids:
        raise ValueError('Handoff must include every successful and failed candidate')
    for j in judgments:
        if j['pool_hash']!=pool['pool_hash'] or j['rubric_hash']!=pool['rubric_hash']:
            raise ValueError('Judgment belongs to another frozen pool')
    rows=[]
    for c in pool['candidates']:
        rows.append({k:c.get(k,'unavailable') for k in ('id','kind','base_commit','head_commit','verdict','patch','source')})
        rows[-1].update(files=files[c['id']],visible_tests=visible_reports[c['id']],
                        hard_test_summary={'verdict':c.get('test_report',{}).get('verdict','unavailable'),
                                           'suite_sha256':c.get('test_report',{}).get('suite_sha256','unavailable'),
                                           'details':'withheld from agents; retained in private controller evidence'})
    package={'schema_version':1,'pool_hash':pool['pool_hash'],'rubric_hash':pool['rubric_hash'],
             'base_commit':pool['base_commit'],'env_hash':pool['env_hash'],'task_hash':pool['task_hash'],
             'task_contract':pool['task_contract'],'rubric':pool['rubric'],'candidates':rows,
             'judgments':list(judgments),'context_transfer':'program evidence, not prior chats or hidden test answers',
             'human_review_required':True}
    package['handoff_hash']=digest(package)
    return package


def validate_handoff(package):
    body=dict(package);expected=body.pop('handoff_hash')
    if digest(body)!=expected:raise ValueError('Handoff changed')
    ids=[c['id'] for c in package['candidates']]
    if not ids or len(set(ids))!=len(ids):raise ValueError('Duplicate/missing candidates')
    return package


def judge_pool(package, extra=None):
    """J3 receives identical public evidence for A..N and M, never private hard-test logs."""
    validate_handoff(package)
    rows=[]
    for c in package['candidates']+([extra] if extra else []):
        rows.append({k:c.get(k,'unavailable') for k in ('id','kind','base_commit','head_commit','verdict','patch','source')})
        rows[-1].update(env_hash=package['env_hash'],prompt_hash=package['task_hash'],
                        test_report=c.get('visible_tests',{}),known_failures=[c['verdict']] if c['verdict']!='PASS' else [])
    pool={k:package[k] for k in ('task_contract','task_hash','base_commit','env_hash','rubric','rubric_hash')}
    pool.update(candidates=rows,failure_report=failure_report(rows))
    if len(rows) in (2,6):pool['purpose']='JUDGE_COMPARISON'
    pool['pool_hash']=digest(pool)
    return validate_pool(pool)


def compare(pool, merged, judgment):
    validate_pool(pool)
    original_passed=[c['id'] for c in pool['candidates'] if c['verdict']=='PASS']
    merged_passed=merged['verdict']=='PASS'
    selected=judgment.get('eligible_selected') if judgment else None
    eligible={c['id'] for c in pool['candidates'] if c['verdict']=='PASS'}
    if merged_passed:eligible.add('M')
    if selected is not None and selected not in eligible:raise ValueError('Judge selected a failed candidate')
    status='PASS' if eligible else ('INDETERMINATE' if merged['verdict'] in ('INFRA_FAIL','BUDGET_EXHAUSTED') else 'FAIL')
    return {'status':status,'original_passing_candidates':original_passed,'M_verdict':merged['verdict'],
            'M_added_any_passing_solution':merged_passed and not original_passed,'selected_candidate':selected,
            'M_wins_automatically':False,'human_review_required':True,'efficacy_claim':False}


def checkpoint(next_step, stages, contract_hash):
    value={'next_step':next_step,'stages':stages,'contract_hash':contract_hash}
    value['checkpoint_hash']=digest(value)
    return value


def validate_checkpoint(value, contract_hash):
    body=dict(value);claimed=body.pop('checkpoint_hash')
    if digest(body)!=claimed or value['contract_hash']!=contract_hash or value['next_step']!=len(value['stages']):
        raise ValueError('Checkpoint or task contract changed')
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))
