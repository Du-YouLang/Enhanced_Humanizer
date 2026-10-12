"""Complete DSH tool call/result evidence, with explicit secret redactions.

Provider headers, authentication configuration and private reasoning are never
exported. Tool arguments/results are retained in full or the view is refused.
"""
import hashlib
import json
from pathlib import Path
import re


def redact(value):
    """Also remove local broker capabilities if a tool prints its environment."""
    count=0
    if isinstance(value,dict):
        cleaned={}
        for key,item in value.items():
            if isinstance(item,str) and re.search(r'(?i)(?:api[_-]?key|authorization|capability|access[_-]?token)$',key):
                cleaned[key]='[REDACTED_CREDENTIAL]';count+=1
            else:
                cleaned[key],number=redact(item);count+=number
        return cleaned,count
    if isinstance(value,list):
        cleaned=[]
        for item in value:
            item,number=redact(item);cleaned.append(item);count+=number
        return cleaned,count
    if not isinstance(value,str):return value,0
    value,number=re.subn(r'(?i)\b(?:sk-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|eyJ[a-z0-9_-]{15,}\.[a-z0-9_-]{15,}\.[a-z0-9_-]{15,})','[REDACTED_CREDENTIAL]',value);count+=number
    value,number=re.subn(r'(?i)(\bBearer\s+)[a-z0-9._~+/-]{16,}',r'\1[REDACTED_CREDENTIAL]',value);count+=number
    value,number=re.subn(r'''(?i)((?:[a-z0-9_]*API_KEY|x-api-key|capability)\s*["']?\s*[:=]\s*["']?)[a-z0-9._~+/-]{16,}''',r'\1[REDACTED_CREDENTIAL]',value);count+=number
    return value,count


def tool_trace(root,*,max_bytes=2_000_000):
    files=sorted(Path(root).glob('humanize/epics/*/*/sessions/dsh/sessions/*/*/session.v3.jsonl'))
    backend='dsh'
    if not files:
        backend='codex';files=sorted(Path(root).rglob('rollout-*.jsonl'))
    if not files:raise ValueError('Native Harness tool trace is unavailable')
    records=[];origins=[];redactions=0
    for file in files:
        if file.is_symlink() or file.stat().st_size>20_000_000:raise ValueError('Invalid native trace')
        raw=file.read_bytes();origins.append({'file':str(file.relative_to(root)),'sha256':hashlib.sha256(raw).hexdigest()})
        for line in raw.decode('utf-8').splitlines():
            row=json.loads(line)
            if backend=='codex':
                payload=row.get('payload',{});kind=payload.get('type','')
                if row.get('type')!='response_item' or kind not in ('function_call','function_call_output','custom_tool_call','custom_tool_call_output','web_search_call','computer_call','computer_call_output','file_search_call','mcp_call','mcp_list_tools'):continue
                row={'type':'tool/result' if kind.endswith('_output') else 'tool/call',
                     'source_backend':'codex','timestamp':row.get('timestamp'),'data':payload}
            if row.get('type') not in ('tool/call','tool/result'):continue
            row,count=redact(row)
            redactions+=count;records.append(row)
    value={'kind':'COMPLETE_NATIVE_TOOL_CALLS_AND_RESULTS','backend':backend,'records':records,'origin_hashes':origins,
           'tool_calls':sum(r['type']=='tool/call' for r in records),'tool_results':sum(r['type']=='tool/result' for r in records),
           'credential_redactions':redactions,'private_reasoning':'EXCLUDED','provider_headers':'EXCLUDED','truncated':False}
    if len(json.dumps(value).encode())>max_bytes:raise ValueError('Complete tool evidence exceeds declared bound; no truncation')
    return value


def trace_pool(pool,roots):
    import copy
    from p2_candidates import digest,validate_pool
    validate_pool(pool);value=copy.deepcopy(pool);value.pop('pool_hash')
    origins=[]
    for candidate in value['candidates']:
        trace=tool_trace(roots[candidate['id']])
        origins.append({'id':candidate['id'],'head_commit':candidate['head_commit'],'patch_sha256':digest(candidate['patch'].encode()),
                        'source_evidence_sha256':digest(candidate['source'].encode()),'tool_trace_sha256':digest(trace)})
        candidate['source']=json.dumps({'complete_worktree':candidate['source'],'complete_tool_trace':trace},sort_keys=True)
    value['pool_hash']=digest(value);validate_pool(value)
    return value,{'original_pool_hash':pool['pool_hash'],'trace_pool_hash':value['pool_hash'],
                  'unchanged_candidate_objects':origins,'different_public_evidence_is_intentional':True}
