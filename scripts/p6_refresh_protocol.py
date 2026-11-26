"""Exact prospective model/task/role contracts; no model calls or tool execution."""
import hashlib
import json
import re
from pathlib import PurePosixPath
from p6_guidance_protocol import TASKS

REVISION='USER_APPROVED_2026-11-26_MODEL_REFRESH_25000_USD500'
SCOPE='ONLY_NEW_THREE_MODEL_SIXTEEN_TASK_THREE_METHOD_REFRESH'
MODELS={'GPT61-Sol':'gpt-6.1-sol','GPT62-Sol':'gpt-6.2-sol','DS41-Flash1017':'deepseek-flash'}
METHODS=('Direct','Enhanced','SingleAgent-MatchedBudget')
ENHANCED=('pool-A','pool-B','pool-C','judge-input','reviewer','judge-final')
MATCHED=tuple('matched-'+str(i) for i in range(1,7))


def expected_model(scope):
    if not isinstance(scope,str):raise ValueError('Explicit refresh scope required')
    parts=scope.split('/')
    if len(parts)!=6:raise ValueError('Six scope components required')
    prefix,run,task,model,method,role=parts
    if prefix!='REFRESH' or not re.fullmatch(r'refresh-[0-9]{8}T[0-9]{6}Z',run):raise ValueError('Fresh run ID required')
    if task not in TASKS or model not in MODELS or method not in METHODS:raise ValueError('Unknown task/model/method')
    allowed={'Direct':('direct',),'Enhanced':ENHANCED,'SingleAgent-MatchedBudget':MATCHED}[method]
    if role not in allowed:raise ValueError('Role outside frozen method')
    return 'gpt-6.1-sol' if method=='Enhanced' and role in ('judge-input','reviewer','judge-final') else MODELS[model]


def allowed_scope(scope,provider,model=None):
    try:expected=expected_model(scope)
    except ValueError:return False
    if model is not None and model!=expected:return False
    return provider==('deepseek' if expected=='deepseek-flash' else 'subscription')


def model_for_job(job):
    if job.get('budget',{}).get('cash_budget_revision')!=REVISION:raise ValueError('New scope budget required')
    expected=expected_model(job['scope'])
    if job.get('requested_model')!=expected:raise ValueError('Requested model does not match role scope')
    backend='dsh' if expected=='deepseek-flash' else 'codex'
    if job['backend']!=backend:raise ValueError('Model/harness mismatch')
    return expected


def verify_session(usage,turns,expected):
    if expected not in ('gpt-6.1-sol','gpt-6.2-sol'):raise ValueError('Unsupported subscription model')
    done=[t for t in turns if t.get('status')=='COMPLETED']
    if not done:raise ValueError('No completed turn')
    ids={t.get('session_id') for t in done}
    if len(ids)!=1 or None in ids or any(t.get('model_requested')!=expected for t in done):raise ValueError('Model/session drift')
    rows=[r for r in usage if r.get('session_id') in ids]
    if len(rows)!=1 or rows[0].get('model_id')!=expected:raise ValueError('Returned model not bound')
    tokens=rows[0].get('usage',{})
    if any(type(tokens.get(k)) is not int or tokens[k]<0 for k in ('input_tokens','output_tokens','cached_input_tokens')):raise ValueError('Missing usage')
    if tokens['cached_input_tokens']>tokens['input_tokens']:raise ValueError('Invalid cached tokens')
    return rows[0]


def handoff_prompt(path,raw,task_prompt):
    p=PurePosixPath(str(path))
    if not p.is_absolute() or not isinstance(raw,bytes):raise ValueError('Absolute trusted input path/bytes required')
    digest=hashlib.sha256(raw).hexdigest()
    # Full input is inlined as well as available at its exact read-only path.
    # No reliance on parent directory listing or an unverified model assertion.
    if len(raw)>8_000_000:raise ValueError('Full handoff exceeds bound; never silently truncate')
    return (task_prompt+'\nTrusted controller handoff location: '+str(p)+'\n'
        'Input SHA-256: '+digest+'\nRead the entire input. Before editing or issuing other tools, '
        'read this exact file completely and print its absolute path, full byte count and SHA-256 in a tool result. A directory-search failure is not evidence '
        'the file is missing. Report accepting/rejecting each suggestion with evidence; advice is not authority.\n'
        '<complete_public_handoff>\n'+raw.decode('utf8')+'\n</complete_public_handoff>')


def verify_handoff_trace(trace,path,raw):
    """Require observable tool output binding complete byte length and SHA.

    The public input is already inlined so receipt loss cannot silently hide it.
    This evidence gate distinguishes unread/unverified handoff from model FAIL.
    A reported hash alone is not claimed to prove semantic comprehension.
    """
    if trace.get('truncated') is not False:raise ValueError('Full observable trace required')
    expected=hashlib.sha256(raw).hexdigest();size=len(raw)
    calls={};results=[]
    for record in trace.get('records',[]):
        d=record.get('data',{})
        if record.get('type')=='tool/call':calls[d.get('callId')]=d
        if record.get('type')=='tool/result':results.append(d.get('message',{}))
    for result in results:
        call=calls.get(result.get('source',{}).get('callId'))
        if call is None:continue
        args=str(call.get('arguments',''));output=json.dumps(result,ensure_ascii=False)
        if str(path) in args and expected in output and str(size) in output:
            return {'status':'HANDOFF_READ_RECEIPT_OBSERVED','path':str(path),'sha256':expected,'bytes':size,
                    'semantic_comprehension_proven':False}
    return {'status':'INFRA_HANDOFF_UNCONSUMED','path':str(path),'sha256':expected,'bytes':size}


def method_order(task_index,model_index):
    shift=(task_index+model_index)%3
    return METHODS[shift:]+METHODS[:shift]


def require_clean_barrier(rows):
    if set(rows)!=set(METHODS):raise ValueError('All three final programs must freeze before hidden acceptance')
    for row in rows.values():
        if row.get('hidden_seen') is not False or not re.fullmatch('[0-9a-f]{64}',row.get('program_sha256','')):
            raise ValueError('Hidden leakage or missing frozen program')
    return True


def complete_group(path,name,value):
    # Use the journal module's exact Unicode serialization, not a different
    # helper that escapes non-ASCII and would break completed-stage reuse.
    from pi_full_protocol import exclusive,digest as journal_digest
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):raise ValueError('Unsafe stage name')
    exclusive(path,{'stage':name,'value':value,'value_sha256':journal_digest(value)})
