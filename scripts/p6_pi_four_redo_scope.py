"""Exact four fresh supplemental trials authorized by the human on 2026-10-16."""
import re

REVISION = 'USER_APPROVED_2026-10-16_FOUR_PI_INFRA_FRESH_TRIALS_USD500'
SCOPE = 'ONLY_FOUR_AUTHORIZED_PI_INFRA_FRESH_TRIALS'
AUTH = 'DIRECT_HUMAN_2026-10-16_REDO_FOUR_PI_INFRA_CELLS'
RUN_PATTERN = r'formal-infra-redo4-[0-9]{8}T[0-9]{6}Z'
TARGETS = (
    ('formal-full-compare-20261014T161449Z', 'BIP-black-3', 'P0', 'subscription', 'INFRA_FAIL'),
    ('formal-full-compare-20261014T171931Z', 'BIP-black-4', 'P1', 'subscription', 'INFRA_RETRY_PENDING'),
    ('formal-full-compare-20261015T012431Z', 'BIP-black-5', 'P1', 'deepseek', 'INFRA_RETRY_PENDING'),
    ('formal-full-compare-20261015T021613Z', 'BIP-black-5', 'P2', 'deepseek', 'INFRA_RETRY_PENDING'),
)

def allowed_cells():
    return [dict(task_id=t, profile=p, provider=v, repetition=0) for _, t, p, v, _ in TARGETS]


def allowed_scope(experiment, provider):
    return isinstance(experiment, str) and any(
        c['provider'] == provider and re.fullmatch(
            r'PI_FORMAL/' + RUN_PATTERN + '/' + re.escape(c['task_id']+'-'+c['profile']+'-'+provider), experiment)
        for c in allowed_cells())


def validate_targets(plan, originals):
    if (plan.get('authorization') != AUTH or plan.get('cells') != allowed_cells()
            or plan.get('fresh_role_seconds') != 900 or type(plan.get('fresh_role_seconds')) is not int
            or plan.get('fresh_role_requests') != 1000 or type(plan.get('fresh_role_requests')) is not int
            or type(plan.get('maximum_new_trials_per_cell')) is not int or plan['maximum_new_trials_per_cell'] != 1
            or plan.get('cumulative_caps') != {'deepseek_requests':10000,'api_cash_usd':500}
            or plan.get('original_result_preserved') is not True or plan.get('external_release_authorized') is not False
            or len(originals) != 4 or len(plan.get('originals',[])) != 4):
        raise ValueError('Only the exact four authorized fresh supplemental trials are permitted')
    for target, row, cell, entry in zip(TARGETS, originals, allowed_cells(), plan['originals']):
        expected_path='/opt/workbench/benchmark/private/pi-comparison/'+target[0]+'/'+cell['task_id']+'-'+cell['profile']+'-'+cell['provider']+'/result.json'
        if (entry['original_run'] != target[0] or row['cell'] != cell or row['outcome'] != target[4]
                or row['role_seconds'] != 900 or entry.get('result_path') != expected_path):
            raise ValueError('Original failed cell identity/outcome differs')
    return plan
