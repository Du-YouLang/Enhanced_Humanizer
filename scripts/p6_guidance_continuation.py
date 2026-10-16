"""Exact no-replay suffix after the embedded-helper infrastructure stop."""
from p6_guidance_protocol import TASKS,branch_order

REVISION='GUIDANCE_HELPER_RECOVERY_20261016'
ORIGINAL_RUN='guidance-20261016T060944Z'
PARTIAL_TASK=TASKS[9]
RETAINED_TASKS=TASKS[:9]
NEW_TASKS=TASKS[10:]
AFFECTED_TASKS=TASKS[6:10]


def role_order(tid):
    order=branch_order(tid)
    return ('initial-ds',)+tuple(b+'-mentor' for b in order)+tuple(b+'-ds' for b in order)


def remaining_partial_roles(completed):
    wanted=role_order(PARTIAL_TASK)
    if tuple(completed)!=wanted[:4]:raise ValueError('Exactly four completed partial-task model roles must be reused')
    return wanted[4:]


def permit_launch(scope,run_id,mode):
    if mode=='original-partial':
        return scope=='GUIDANCE/'+ORIGINAL_RUN+'/'+PARTIAL_TASK+'/'+role_order(PARTIAL_TASK)[-1]
    if mode=='new-suffix':
        return any(scope=='GUIDANCE/'+run_id+'/'+tid+'/'+role for tid in NEW_TASKS for role in role_order(tid))
    return False
