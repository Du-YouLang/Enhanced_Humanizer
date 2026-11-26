"""Provider-separated refresh accounting; cumulative sessions are counted once."""

def summarize(ledger,workers,scope_prefix):
    ds=[v for v in ledger['requests'] if v['experiment'].startswith(scope_prefix+'/')]
    subscriptions=[v for v in ledger['codex_turns'] if v['experiment'].startswith(scope_prefix+'/')]
    active=[w for w in workers.values() if w['scope'].startswith(scope_prefix+'/')]
    known=[v['usage'] for v in ds if isinstance(v.get('usage'),dict)]
    unknown=sum(not isinstance(v.get('usage'),dict) for v in ds)
    sessions={};missing=[]
    for w in active:
        if not any(t.get('harness')=='codex' for t in w.get('turns',[])) and not any(r['experiment']==w['scope'] or r['experiment'] in w.get('additional_accounting_scopes',[]) for r in subscriptions):continue
        rows=w.get('usage',[])
        if not rows:missing.append(w['scope']);continue
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('usage'),dict):missing.append(w['scope']);continue
            v=row['usage']
            if not row.get('session_id') or any(type(v.get(k)) is not int or v[k]<0 for k in ('input_tokens','cached_input_tokens','output_tokens')) or v['cached_input_tokens']>v['input_tokens']:
                missing.append(w['scope']);continue
            key=(row.get('session_id'),row.get('usage_segment','COMPLETE_TOTAL'))
            if key in sessions and sessions[key]!=row['usage']:raise ValueError('Conflicting duplicate session usage')
            sessions[key]=row['usage']
    def ds_total(k):return sum(v.get(k,0) for v in known)
    def sub_total(k):return sum(v.get(k,0) for v in sessions.values())
    return {'deepseek':{'requests':len(ds),'known_usage_requests':len(known),'unknown_usage_requests':unknown,
        'input_tokens_known':sum(ds_total(k) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens')),
        'cache_read_input_tokens_known':ds_total('cache_read_input_tokens'),'output_tokens_known':ds_total('output_tokens'),
        'token_totals_are_lower_bounds':unknown>0,'api_upper_bound_usd':sum(v['charge_bound_nano'] for v in ds)/1e9,
        'actual_api_cash_usd':'unavailable'},
        'openai':{'subscription_reservations':len(subscriptions),'recorded_session_usage_segments':len(sessions),
        'input_tokens_recorded':sub_total('input_tokens'),'cached_input_tokens_subset':sub_total('cached_input_tokens'),
        'output_tokens_recorded':sub_total('output_tokens'),'unknown_usage_scopes':sorted(set(missing)),
        'token_totals_are_lower_bounds':bool(missing),
        'actual_subscription_cash_usd':'unavailable','reasoning_tokens_not_added_to_output_again':True},
        'model_activity_seconds':sum(w.get('wall_seconds',0) for w in active),
        'completed_role_slots':sum(len(w.get('matched_slot_receipts',[])) if w.get('matched_slot_receipts') else w.get('status')=='COMPLETED' for w in active),
        'activity_excludes_hidden_scientific_acceptance':True}


def preserve_authorized_ledger(ledger,expected_sha,archive):
    """Caller holds the experiment-owner lock; archive only, never reset/refund."""
    import hashlib,json,os
    from pathlib import Path
    raw=ledger.path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('Current ledger differs; reconcile before spending')
    value=json.loads(raw);ledger.validate(value)
    archive=Path(archive);archive.parent.mkdir(parents=True,exist_ok=True)
    with archive.open('xb') as output:output.write(raw);output.flush();os.fsync(output.fileno())
    if ledger.path.read_bytes()!=raw:raise ValueError('Concurrent ledger change while preserving history')
    return {'status':'EXISTING_AUTHORIZATION_RETAINED_NO_RESET','archive_sha256':expected_sha,
        'requests_retained':len(value['requests']),'subscriptions_retained':len(value['codex_turns']),'caps':ledger.caps()}
