"""Exact shutdown checkpoint scope and cumulative session accounting."""
import math
from p6_guidance_protocol import TASKS

REVISION='GUIDANCE_USER_SHUTDOWN_CONTINUATION_20261016'
SOURCE_RUN='guidance-20261016T090045Z'
PARTIAL_TASK=TASKS[11]
MENTOR='code-tests-trace-mentor'
SESSION_ID='01a1442f-14fe-76b3-974b-e862ee17e509'
NEW_TASKS=TASKS[12:]
REMAINING_ROLES=('code-tests-mentor','code-tests-trace-ds','code-tests-ds')

def scope(role):return 'GUIDANCE/'+SOURCE_RUN+'/'+PARTIAL_TASK+'/'+role

def allow_partial(job):
    return job['scope'] in {scope(r) for r in REMAINING_ROLES}

def allow_science(value,run_id):
    return any(value=='GUIDANCE/'+run_id+'/'+tid+'/'+r for tid in NEW_TASKS
        for r in ('initial-ds','code-tests-mentor','code-tests-trace-mentor','code-tests-ds','code-tests-trace-ds'))

def remaining_seconds(started,stopped,cap=900):
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in (started,stopped)) or stopped<started:
        raise ValueError('Actual interruption timestamps required')
    debit=math.ceil(stopped-started)
    if not 0<debit<cap:raise ValueError('No remaining role time; do not invent a fresh role')
    return debit,cap-debit

def usage_segments(before,after):
    fields=('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','total_tokens')
    for row in (before,after):
        if any(type(row.get(k)) is not int or row[k]<0 for k in fields):raise ValueError('Finite integer session usage required')
        if row['cached_input_tokens']>row['input_tokens']:raise ValueError('Invalid cache subset')
    delta={k:after[k]-before[k] for k in fields}
    if any(v<0 for v in delta.values()):raise ValueError('Resumed session counters regressed')
    if delta['cached_input_tokens']>delta['input_tokens']:raise ValueError('Invalid resumed cache delta')
    return before,delta
