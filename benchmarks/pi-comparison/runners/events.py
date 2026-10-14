"""Normalize pinned Pi JSONL without counting its repeated end-of-turn summaries.

This is a read-only adapter, not a coding harness or authoritative bill/grade.
"""
import hashlib
import json

TOKEN_FIELDS = {'input_tokens':'input','output_tokens':'output',
                'cache_read_tokens':'cacheRead','cache_write_tokens':'cacheWrite'}


def records(raw):
    # splitlines() would split valid U+2028/U+2029 inside JSON strings.
    for line in raw.decode('utf-8').split('\n'):
        if line.strip():
            row = json.loads(line.rstrip('\r'))
            if not isinstance(row,dict) or not isinstance(row.get('type'),str):
                raise ValueError('Object event with type required')
            yield row


def summarize(raw):
    events=list(records(raw));messages=[];tool_calls={};tool_errors=0
    turn=0;identities=set();duplicates=[];retries=compactions=0;settled=False
    models=set()
    for row in events:
        kind=row['type']
        if kind=='turn_start':turn+=1
        if kind=='message_end' and row.get('message',{}).get('role')=='assistant':
            msg=row['message'];identity=(turn,msg.get('id',msg.get('timestamp')))
            if identity in identities:
                duplicates.append(identity);continue
            identities.add(identity);messages.append(msg)
            if msg.get('model'):models.add((msg.get('provider'),msg['model']))
        if kind=='tool_execution_start':
            key=row.get('toolCallId')
            if not key or key in tool_calls:raise ValueError('Ambiguous tool event identity')
            tool_calls[key]=row.get('toolName')
        if kind=='tool_execution_end':tool_errors+=int(row.get('isError') is True)
        if kind=='auto_retry_start':retries+=1
        if kind=='auto_compaction_start':compactions+=1
        if kind=='agent_settled':settled=row.get('aborted') is False
    usage={};missing={}
    for field,key in TOKEN_FIELDS.items():
        values=[m.get('usage',{}).get(key) for m in messages]
        valid=bool(values) and all(type(v) is int and v>=0 for v in values)
        usage[field]=sum(values) if valid else None
        if not valid:missing[field]='No assistant usage or at least one message lacks an integer count'
    usage['reasoning_tokens']=None
    missing['reasoning_tokens']='Not a separately verified count in the pinned Pi message schema'
    errors=[m.get('errorMessage') for m in messages if m.get('stopReason') in ('error','aborted')]
    return {'schema_version':1,'trace_sha256':hashlib.sha256(raw).hexdigest(),
            'events':len(events),'assistant_requests_observed':len(messages),
            'model_ids_observed':[{'provider':p,'id':m} for p,m in sorted(models,key=str)],
            'usage':usage,'missing_reason':missing,'total_tool_calls':len(tool_calls),
            'tool_errors':tool_errors,'provider_retries':retries,'context_compactions':compactions,
            'duplicate_assistant_events':len(duplicates),'agent_settled':settled,
            'terminal_errors_observed':len(errors),'hidden_grade':'NOT_RUN',
            'historical_assistant_errors_observed':len(errors),
            'last_assistant_stop_reason':messages[-1].get('stopReason') if messages else None,
            'api_cost_usd_actual_or_reconciled':None,
            'cost_missing_reason':'Pi estimated cost is not an authoritative supplier bill; broker ledger required',
            'ttft_seconds':None,'first_patch_seconds':None,'first_test_pass_seconds':None,
            'latency_missing_reason':'Event framing alone does not establish these timestamps'}


if __name__=='__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser();parser.add_argument('trace',type=Path)
    args=parser.parse_args();print(json.dumps(summarize(args.trace.read_bytes()),indent=2))
