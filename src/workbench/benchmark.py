"""Frozen exploratory benchmark contracts. This module does not execute agents."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

ARMS = {
    'A': ('deepseek-flash', 'official DSH', 'native_ds'),
    'B': ('deepseek-flash', 'Humanize + official DSH', 'best_of_n'),
    'C': ('deepseek-flash + gpt-6.1-sol', 'Humanize + official DSH/Codex', 'enhanced'),
    'D': ('gpt-6.1-sol', 'official Codex', 'native_sol'),
    'E': ('deepseek-flash + gpt-6.1-sol', 'Humanize + official DSH/Codex', 'relay'),
    'F': ('deepseek-flash + gpt-6.1-sol', 'Humanize + official DSH/Codex', 'enhanced_relay'),
}
OUTCOMES = {'PASS', 'FAIL', 'TIMEOUT', 'INFRA_FAIL', 'INDETERMINATE', 'NOT_RUN'}
SHA40 = re.compile(r'^[0-9a-f]{40}$')
SHA64 = re.compile(r'^[0-9a-f]{64}$')
REQUIRED_METRICS = ('end_to_end_seconds', 'input_tokens', 'output_tokens',
                    'cache_read_tokens', 'api_cash_usd', 'api_upper_bound_usd',
                    'subscription_turns', 'subscription_cost_usd',
                    'human_interventions', 'human_seconds')


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_manifest(value):
    if value.get('schema_version') != 1 or value.get('phase') != 'P6':
        raise ValueError('Not a P6 manifest')
    tasks = value.get('tasks', [])
    if len(tasks) != 16 or Counter(t['family'] for t in tasks) != {'BugsInPy': 6, 'SWE-bench Lite': 6, 'scientific': 4}:
        raise ValueError('The baseline requires exactly 6 + 6 + 4 tasks')
    if len({t['task_id'] for t in tasks}) != 16:
        raise ValueError('Duplicate task identity')
    if value.get('seed') != 42 or value.get('repetitions') != 1:
        raise ValueError('Protocol change requires a new manifest and decision record')
    if value.get('protocol_version') in (11,12):
        if (type(value.get('per_request_output_tokens')) is not int or value['per_request_output_tokens']!=256000 or
            value.get('output_budget_revision')!='USER_APPROVED_2026-10-12_DSH_DEFAULT256000' or
            not isinstance(value.get('generation_guidance'),str) or not value['generation_guidance'] or
            not SHA64.fullmatch(value.get('output_control_receipt_sha256',''))):
            raise ValueError('Frozen prospective DSH output policy and native control required')
    time_caps = (600,1200,10800) if value.get('protocol_version')==12 else (120,1200,10800) if value.get('protocol_version') in (10,11) else (120,600,1200)
    if value.get('n_candidates') != 3 or any(type(value.get(k)) is not int for k in ('request_time_cap_seconds','candidate_time_cap_seconds','task_time_cap_seconds')) or (value.get('request_time_cap_seconds'), value.get('candidate_time_cap_seconds'), value.get('task_time_cap_seconds')) != time_caps:
        raise ValueError('Frozen candidate count and explicit time caps required')
    if value.get('protocol_version') in (10,11,12):
        for key,expected in (('role_timeout_seconds_by_family',{'public':900,'scientific':1200}),
                             ('experiment_timeout_seconds_by_family',{'public':7200,'scientific':10800})):
            if value.get(key)!=expected or any(type(v) is not int for v in value[key].values()):
                raise ValueError('Human-approved family time allocation required')
    ids = {t['task_id'] for t in tasks}
    if value.get('protocol_version')==12:
        if (value.get('per_role_api_requests')!=1000 or value.get('network_consecutive_failure_limit')!=5
                or value.get('network_recovery_revision')!='USER_APPROVED_2026-10-12_ROLE1000_REQUEST600_NETWORK5'
                or not SHA64.fullmatch(value.get('network_control_receipt_sha256',''))):
            raise ValueError('Prospective request/reconnect policy and actual control required')
    smoke = value.get('smoke_tasks', [])
    if len(smoke) != 2 or len(set(smoke)) != 2 or not set(smoke) <= ids:
        raise ValueError('Two distinct smoke identities required')
    for task in tasks:
        if value.get('protocol_version') in (10,11,12):
            family='scientific' if task['family']=='scientific' else 'public'
            for field,mapping in (('role_time_cap_seconds','role_timeout_seconds_by_family'),
                                  ('model_activity_time_cap_seconds','experiment_timeout_seconds_by_family')):
                if type(task.get(field)) is not int or task[field]!=value[mapping][family]:
                    raise ValueError('Per-task time allocation differs from its frozen family')
        if task['family'] != 'scientific':
            if not SHA40.fullmatch(task.get('base_commit', '')) or not SHA40.fullmatch(task.get('source_revision', '')):
                raise ValueError('Public task needs exact upstream revisions')
            if not SHA64.fullmatch(task.get('material_sha256', '')):
                raise ValueError('Public task material hash missing')
        elif task.get('preparation_status') == 'READY':
            if not all(task.get(k) for k in ('paper', 'license', 'tolerances', 'invariants')) or not SHA40.fullmatch(task.get('base_commit', '')) or not all(SHA64.fullmatch(task.get(k, '')) for k in ('data_sha256', 'gold_sha256')):
                raise ValueError('Scientific acceptance requires identified materials and numerical gold')
            if not isinstance(task['tolerances'], dict) or not isinstance(task['invariants'], list):
                raise ValueError('Numerical tolerances and executable invariant identities required')
        if task.get('preparation_status') not in {'MATERIAL_FROZEN_ENV_PENDING', 'NOT_RUN_MISSING_MATERIAL', 'READY', 'INFRA_FAIL'}:
            raise ValueError('Unknown preparation state')
    return value


def freeze_manifest(value, path):
    validate_manifest(value)
    body = dict(value)
    body['manifest_sha256'] = digest(value)
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != body:
            raise ValueError('Existing manifest is immutable; freeze a new version')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            json.dump(body, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    return body


def check_manifest(body):
    value = dict(body)
    expected = value.pop('manifest_sha256', None)
    if expected != digest(value):
        raise ValueError('Frozen manifest was altered')
    return validate_manifest(value)


def plan(body):
    value = check_manifest(body)
    return [dict(task_id=t['task_id'], arm=arm, seed=value['seed'], repetition=0,
                 manifest_sha256=body['manifest_sha256'], outcome='NOT_RUN',
                 reason=t['preparation_status'], model_identity=ARMS[arm][0],
                 harness=ARMS[arm][1], metrics={key: 'unavailable' for key in REQUIRED_METRICS})
            for t in value['tasks'] for arm in ARMS]


def validate_result(row, body, preparation):
    value = check_manifest(body)
    task = next((t for t in value['tasks'] if t['task_id'] == row.get('task_id')), None)
    if task is None or row.get('arm') not in ARMS or row.get('outcome') not in OUTCOMES:
        raise ValueError('Unknown result identity or outcome')
    if row.get('manifest_sha256') != body['manifest_sha256'] or row.get('seed') != value['seed'] or row.get('repetition') != 0:
        raise ValueError('Result differs from the frozen protocol')
    if row['outcome'] == 'NOT_RUN':
        if not row.get('reason'):
            raise ValueError('Missing preparation/authorization reason')
        return row
    if row.get('evidence_kind') != 'REAL_MODEL' or row.get('model_identity') != ARMS[row['arm']][0] or row.get('harness') != ARMS[row['arm']][1]:
        raise ValueError('Mocks or substituted identities are not benchmark results')
    if preparation.get('status') != 'READY' or preparation.get('task_id') != task['task_id']:
        raise ValueError('Unverified environment cannot enter the model comparison')
    for key in ('env_sha256', 'hardware_sha256', 'permissions_sha256', 'base_commit', 'hidden_suite_sha256'):
        if not preparation.get(key) or row.get(key) != preparation[key]:
            raise ValueError('Unfair or unbound result: ' + key)
    if row['base_commit'] != task['base_commit']:
        raise ValueError('Initial source differs from frozen task')
    expected_cap=task['model_activity_time_cap_seconds'] if value.get('protocol_version') in (10,11,12) else value['task_time_cap_seconds']
    if row.get('time_cap_seconds') != expected_cap:
        raise ValueError('Time caps must be equal across arms')
    metrics = row.get('metrics', {})
    for key in REQUIRED_METRICS:
        number = metrics.get(key)
        if number != 'unavailable' and (isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number < 0):
            raise ValueError('Missing or invalid measurement: ' + key)
    for key in ('evidence_sha256', 'run_contract_sha256'):
        if not SHA64.fullmatch(row.get(key, '')):
            raise ValueError('Auditable result hash required')
    if row['outcome'] == 'PASS' and (row.get('independent_acceptance') != 'PASS' or not SHA40.fullmatch(row.get('head_commit', ''))):
        raise ValueError('Judge score cannot replace independent acceptance')
    return row


def same_pool(records):
    """All judge/merge comparisons bind identical candidate objects and public rubric."""
    if not records:
        raise ValueError('Empty comparison')
    for key in ('pool_sha256', 'rubric_sha256', 'public_evidence_sha256'):
        hashes = {r.get(key) for r in records}
        if len(hashes) != 1 or not SHA64.fullmatch(next(iter(hashes)) or ''):
            raise ValueError('Comparison changed the frozen ' + key)
    return True


def summarize(rows):
    """Unknown measurements are never zeros; API upper bounds are never bills."""
    seen = set()
    for row in rows:
        identity = (row['task_id'], row['arm'], row['seed'], row['repetition'])
        if identity in seen:
            raise ValueError('Duplicate result would select a seed or double count cost')
        seen.add(identity)
    result = {}
    for arm in ARMS:
        group = [r for r in rows if r['arm'] == arm]
        counts = Counter(r['outcome'] for r in group)
        attempted = [r for r in group if r['outcome'] != 'NOT_RUN']
        passed = counts['PASS']
        n = len(attempted)
        interval = 'unavailable'
        if n:
            z = 1.96; p = passed / n; den = 1 + z*z/n
            mid = (p + z*z/(2*n))/den
            half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
            interval = [max(0, mid-half), min(1, mid+half)]
        sums = {}
        for key in REQUIRED_METRICS:
            values = [r['metrics'].get(key, 'unavailable') for r in attempted]
            known = [v for v in values if v != 'unavailable']
            sums[key] = dict(known_sum=sum(known), known_count=len(known), unknown_count=len(values)-len(known),
                             total=sum(known) if values and len(values) == len(known) else 'unavailable')
        cash = sums['api_cash_usd']['total']
        result[arm] = dict(planned=len(group), attempted=n, outcomes=dict(counts),
                           completion_rate=passed/n if n else 'unavailable', exploratory_wilson95=interval,
                           metrics=sums, api_cash_per_success=cash/passed if passed and cash != 'unavailable' else 'unavailable')
    return dict(arms=result, statistical_claim='Exploratory selected tasks only; no efficacy or population significance claim')
