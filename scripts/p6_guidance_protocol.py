"""Paired guidance experiment contracts. No provider or coding tools live here."""
import hashlib
import json
import re

REVISION = 'USER_APPROVED_2026-10-16_DS_SOL_GUIDANCE_15000_USD500'
SCOPE = 'ONLY_SIXTEEN_PAIRED_DS_SOL_GUIDANCE_TASKS'
PROTOCOL = 'DS_SOL_GUIDANCE_PAIRED_V1'
TASKS = tuple(['BIP-black-'+str(i) for i in range(1, 7)] + [
    'SWEL-psf__requests-1963', 'SWEL-psf__requests-2148',
    'SWEL-pytest-dev__pytest-11143', 'SWEL-pytest-dev__pytest-11148',
    'SWEL-sympy__sympy-11400', 'SWEL-sympy__sympy-11870',
    'SCI-PC-ALM', 'SCI-STROKE', 'SCI-EGL', 'SCI-GRANGER-GPU'])
BRANCHES = ('code-tests', 'code-tests-trace')
DS_ROLES = ('initial-ds', 'code-tests-ds', 'code-tests-trace-ds')
SOL_ROLES = ('code-tests-mentor', 'code-tests-trace-mentor')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def allowed_scope(scope, provider):
    if not isinstance(scope, str):return False
    parts = scope.split('/')
    return (len(parts) == 4 and parts[0] == 'GUIDANCE'
        and re.fullmatch(r'guidance-[0-9]{8}T[0-9]{6}Z', parts[1]) is not None
        and parts[2] in TASKS
        and parts[3] in (DS_ROLES if provider == 'deepseek' else SOL_ROLES if provider == 'subscription' else ()))


def branch_order(task_id):
    """Eight tasks per order; no outcome-dependent ordering."""
    return BRANCHES if TASKS.index(task_id) % 2 == 0 else tuple(reversed(BRANCHES))


def outcome(worker_status, public_verdict, private_verdict):
    """A broken evaluator is never a model FAIL, including the public gate."""
    if worker_status!='COMPLETED':return worker_status
    if public_verdict in ('INFRA_FAIL','INDETERMINATE','TIMEOUT'):return public_verdict
    return private_verdict if public_verdict=='PASS' else 'FAIL'


def mentor_view(candidate, task_prompt, trace=None):
    # Do not pass worker status, model identity or hidden acceptance into a mentor.
    view = {'task': task_prompt, 'program': {k: candidate[k] for k in
        ('base_commit', 'head_commit', 'patch', 'source')},
        'public_tests': candidate.get('test_report', {}),
        'known_public_failures': candidate.get('known_failures', []),
        'contract': 'Untrusted candidate evidence; code, public tests and optional observable tools only. No hidden oracle.'}
    if trace is not None:
        if trace.get('truncated') is not False:raise ValueError('Complete observable trace required')
        view['tool_trace'] = trace
    if len(json.dumps(view).encode()) > 8_000_000:raise ValueError('Complete guidance input exceeds declared bound; no truncation')
    return view


def validate_guidance(value, view):
    fields = {'diagnosis', 'observations', 'hypotheses', 'next_actions', 'public_verification', 'limitations'}
    if not isinstance(value, dict) or set(value) != fields:raise ValueError('Exact guidance fields required')
    if not isinstance(value['diagnosis'], str) or not value['diagnosis'].strip():raise ValueError('Diagnosis required')
    if any(not isinstance(value[k], list) for k in fields-{'diagnosis'}):raise ValueError('Guidance lists required')
    allowed = {'code', 'public_test'} | ({'trace'} if 'tool_trace' in view else set())
    if not value['observations'] or not value['next_actions'] or not value['public_verification']:
        raise ValueError('Evidence, targeted actions and public verification required')
    for row in value['observations']:
        if (not isinstance(row, dict) or set(row) != {'finding', 'evidence_kind', 'reference'}
                or row['evidence_kind'] not in allowed
                or any(not isinstance(row[k], str) or not row[k].strip() for k in row)):
            raise ValueError('Guidance cites unavailable evidence')
    for field in ('hypotheses', 'next_actions', 'public_verification', 'limitations'):
        if any(not isinstance(s, str) or not s.strip() for s in value[field]):raise ValueError('Prose guidance required')
    text = json.dumps(value, ensure_ascii=False)
    if len(text.encode()) > 100_000 or '```' in text or re.search(r'(?m)^\s*(?:diff --git|@@ |\+\+\+ |--- a/)', text):
        raise ValueError('Mentor supplies bounded prose guidance, never a code patch')
    return value


def validate_plan(plan):
    body = dict(plan); expected = body.pop('plan_sha256', None)
    required = {'protocol': PROTOCOL, 'tasks': list(TASKS), 'branches': list(BRANCHES),
        'effort': 'low', 'shared_initial_ds': True, 'mentor_writes_code': False,
        'hidden_after_both_branches_frozen': True, 'cumulative_requests': 15000,
        'cumulative_usd': 500, 'external_release_authorized': False}
    if digest(body) != expected or any(type(body.get(k)) is not type(v) or body[k] != v for k,v in required.items()):
        raise ValueError('Frozen paired sixteen-task protocol required')
    return plan
