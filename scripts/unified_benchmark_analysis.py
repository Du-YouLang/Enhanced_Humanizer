"""Offline benchmark normalization; preserves raw attempts and provider usage."""
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics

MAIN_METHODS={
 'A':('Native-DSH-DS',('native-ds',),'原生DSH，单DeepSeek候选'),
 'B':('Best3-DS',('pool-A','pool-B','pool-C'),'Humanfia Flow，三个DS候选并行，公开测试选优'),
 'C':('Enhanced-DS',('pool-A','pool-B','pool-C','judge-input','reviewer','judge-merge'),'同一DS三候选池 + Sol评审、融合、复评'),
 'D':('Native-Codex-Sol',('native-sol',),'原生Codex，单Sol候选'),
 'E':('DS-to-Sol',('native-ds','relay'),'单DS候选 → Sol Builder接力'),
 'F':('Enhanced-DS-to-Sol',('pool-A','pool-B','pool-C','judge-input','reviewer','judge-merge','enhanced-relay'),'Enhanced-DS → 额外Sol Builder接力')}
PROFILES={'P0':'Base','P1':'SciSkills','P2':'NeuroForge','P3':'ResearchLoop'}
TOKEN_FIELDS=('input','cache_read','cache_write','output','reasoning')


def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def cell_key(cell):return cell['task_id'],cell['profile'],cell['provider']
def empty_usage():return dict.fromkeys(TOKEN_FIELDS,0)


def normalized_codex_usage(usage):
    """Codex input includes cached input; reasoning is an output subset."""
    if not isinstance(usage,dict) or not all(type(usage.get(k)) is int for k in ('input_tokens','output_tokens')):return None
    if usage['input_tokens']<0 or usage['output_tokens']<0:raise ValueError('Negative usage counter')
    cached=usage.get('cached_input_tokens',0);write=usage.get('cache_write_input_tokens',0)
    if not all(type(v) is int and v>=0 for v in (cached,write)) or cached+write>usage['input_tokens']:
        raise ValueError('Invalid Codex cached/input relationship')
    return {'input':usage['input_tokens']-cached-write,'cache_read':cached,'cache_write':write,
            'output':usage['output_tokens'],'reasoning':usage.get('reasoning_output_tokens')}


def normalized_pi_usage(usage):
    if not isinstance(usage,dict) or not all(type(usage.get(k)) is int for k in ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens')):return None
    if any(usage[k]<0 for k in ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens')):raise ValueError('Negative usage counter')
    return dict(zip(TOKEN_FIELDS,(usage['input_tokens'],usage['cache_read_tokens'],usage['cache_write_tokens'],usage['output_tokens'],usage.get('reasoning_tokens'))))


def add_observed(rows):
    """Sum only observed fields, keeping the absence of reasoning visible."""
    rows=[r for r in rows if r is not None]
    return {k:sum(r[k] for r in rows if type(r.get(k)) is int) if any(type(r.get(k)) is int for r in rows) else None for k in TOKEN_FIELDS}


def ds_usage(scopes,ledger):
    missing=set(scopes)-set(ledger)
    if missing:raise ValueError('Missing ledger scopes cannot be counted as zero usage: '+', '.join(sorted(missing)))
    rows=[ledger[s] for s in sorted(set(scopes))]
    values=[{'input':r['usage']['input_tokens'],'cache_read':r['usage']['cache_read_input_tokens'],
             'cache_write':r['usage']['cache_creation_input_tokens'],'output':r['usage']['output_tokens'],'reasoning':None} for r in rows if r['known_usage']]
    total=add_observed(values)
    requests=sum(r['requests'] for r in rows);unknown=sum(r['unknown_usage'] for r in rows)
    if requests==0:total=empty_usage()
    return {'observed':total,'requests':requests,'known_requests':requests-unknown,'unknown_requests':unknown,'complete':unknown==0,
            'charge_bound_usd':sum(r['charge_bound_nano'] for r in rows)/1e9,'scopes':sorted(set(scopes))}


def codex_usage(workers,ledger):
    scopes={w['scope'] for w in workers};expected=sum(ledger.get(s,{}).get('subscription_reservations',0) for s in scopes)
    sessions={}
    for worker in workers:
        for row in worker.get('usage') or []:
            key=row.get('session_id') or row.get('trace_file')
            value=normalized_codex_usage(row.get('usage'))
            if not key or value is None:continue
            if key in sessions and sessions[key]!=value:raise ValueError('Conflicting cumulative session counters')
            sessions[key]=value
    if not expected and not sessions:values=empty_usage()
    else:values=add_observed(list(sessions.values()))
    return {'observed':values,'expected_reservations':expected,'known_sessions':len(sessions),
            'complete':len(sessions)>=expected,'sessions':sorted(sessions)}


def normalize_main(intake,latest):
    lookup={(r['task_id'],r['arm']):r for r in latest['main96_rows_with_separate_supplemented_view']};rows=[]
    for run in intake['main']:
        for arm,(method,roles,definition) in MAIN_METHODS.items():
            legacy=run['arms'][arm];review=lookup[run['task_id'],arm];workers=[run['workers'][r] for r in roles]
            ds=ds_usage([w['scope'] for w in workers],intake['ledger_scopes'])
            oa=codex_usage(workers,intake['ledger_scopes'])
            seconds=legacy['metrics'].get('model_and_public_check_seconds')
            rows.append({'method':method,'series':'Humanfia-DSH-Codex','task_id':run['task_id'],'definition':definition,
                'family':'scientific' if run['task_id'].startswith('SCI-') else 'public',
                'first_reviewed_status':review['supplemented_review_status'],'latest_status':review['supplemented_review_status'],
                'raw_status':legacy['outcome'],'selected_seconds':seconds if finite(seconds) else None,
                'all_attempt_seconds_observed':seconds if finite(seconds) else None,'time_complete':finite(seconds),
                'ds':ds,'openai':oa,'selected_ds':copy.deepcopy(ds),'selected_openai':copy.deepcopy(oa),
                'attempts':1,'fresh_retries':0,'session_continuations':int(run['task_id']=='BIP-black-5'),
                'original_identity':review['program_identity'],'source_run':run['run_id'],'scopes':[w['scope'] for w in workers],
                'independent_acceptance_seconds':legacy['metrics'].get('independent_acceptance_seconds'),
                'failure_attribution':review.get('attribution'),'scientific_supplement':review.get('supplement')})
    return rows


def normalize_pi(intake,reviewed):
    original={cell_key(r['result']['cell']):r['result'] for r in intake['pi']}
    review={cell_key(r):r for r in reviewed['pi_rows']}
    fresh={cell_key(r['cell']):r for r in intake['supplements']['pi_four_fresh']['data']['results']}
    network=intake['supplements']['pi_network_redo']['data']['result'];network_key=cell_key(network['cell'])
    overload={cell_key(r['cell']):r for r in intake['supplements']['pi_overload_recovery']['data']['results']}
    rows=[]
    for key,first in original.items():
        selected=fresh.get(key,first);attempts=[first]
        if key==network_key:attempts.append(network)
        if key in fresh:attempts.append(fresh[key])
        recovery=overload.get(key)
        if recovery:attempts.append(recovery)
        model=first['cell']['provider'];is_ds=model=='deepseek'
        method='Pi-'+PROFILES[key[1]]+('-DS' if is_ds else '-Sol')
        all_scopes={r.get('scope') for r in attempts if r.get('scope')}
        def measured_usage(values):
            usages=[normalized_pi_usage(r.get('usage')) for r in values]
            known=add_observed(usages)
            if is_ds:return ds_usage([r['scope'] for r in values if r.get('scope')],intake['ledger_scopes'])
            expected=sum(intake['ledger_scopes'].get(s,{}).get('subscription_reservations',0) for s in {r.get('scope') for r in values})
            return {'observed':known,'expected_reservations':expected,'known_sessions':sum(u is not None for u in usages),'complete':all(u is not None for u in usages),'sessions':[]}
        value=measured_usage(attempts);chosen=measured_usage([selected])
        base_seconds=selected.get('coding_and_public_seconds');complete=finite(base_seconds) and recovery is None
        observed=[r.get('coding_and_public_seconds',r.get('recovery_seconds')) for r in attempts]
        ds=value if is_ds else ds_usage([],intake['ledger_scopes']);oa=codex_usage([],intake['ledger_scopes']) if is_ds else value
        selected_ds=chosen if is_ds else ds_usage([],intake['ledger_scopes']);selected_oa=codex_usage([],intake['ledger_scopes']) if is_ds else chosen
        rows.append({'method':method,'series':'Pi','task_id':key[0],'family':'scientific' if key[0].startswith('SCI-') else 'public',
            'definition':PROFILES[key[1]]+' + official Pi SDK + '+('DeepSeek API' if is_ds else 'Sol subscription'),
            'raw_status':first['outcome'],'first_reviewed_status':review[key]['official_status'],
            'latest_status':selected['outcome'] if key in fresh else review[key]['official_status'],
            'selected_seconds':base_seconds if complete else None,'original_coding_seconds':first.get('coding_and_public_seconds'),
            'all_attempt_seconds_observed':sum(v for v in observed if finite(v)),'time_complete':all(finite(v) for v in observed) and recovery is None,
            'ds':ds,'openai':oa,'selected_ds':selected_ds,'selected_openai':selected_oa,
            'attempts':len(attempts),'fresh_retries':len(attempts)-1-int(recovery is not None),'session_continuations':int(recovery is not None),
            'original_identity':review[key]['head_commit'],'selected_head':selected['head_commit'],
            'source_run':review[key]['source_run'],'selected_scope':selected.get('scope'),'scopes':sorted(all_scopes),
            'attempt_records':[{'scope':r.get('scope'),'outcome':r['outcome'],'seconds':r.get('coding_and_public_seconds',r.get('recovery_seconds')),'usage':r.get('usage')} for r in attempts],
            'independent_acceptance_seconds':selected.get('acceptance',{}).get('elapsed_seconds')})
    return rows


def summarize(rows):
    answer=[]
    order=[v[0] for v in MAIN_METHODS.values()]+['Pi-'+v+'-'+s for s in ('DS','Sol') for v in PROFILES.values()]
    for method in order:
        r=[x for x in rows if x['method']==method]
        if len(r)!=16 or len({x['task_id'] for x in r})!=16:raise ValueError('Every method must have exactly the same16 task identities')
        pass_count=sum(x['latest_status']=='PASS' for x in r);seconds=[x['selected_seconds'] for x in r if finite(x['selected_seconds'])]
        v={'method':method,'series':r[0]['series'],'definition':r[0]['definition'],'total':16,'success':pass_count,
           'failed':sum(x['latest_status']=='FAIL' for x in r),'first_reviewed_success':sum(x['first_reviewed_status']=='PASS' for x in r),
           'public_success':sum(x['latest_status']=='PASS' for x in r if x['family']=='public'),
           'science_success':sum(x['latest_status']=='PASS' for x in r if x['family']=='scientific'),
           'selected_coding_median_seconds':statistics.median(seconds) if seconds else None,'time_coverage':len(seconds),
           'recorded_all_attempt_seconds_sum':sum(x['all_attempt_seconds_observed'] for x in r if finite(x['all_attempt_seconds_observed'])),
           'attempt_time_coverage':sum(x['time_complete'] for x in r),'fresh_retries':sum(x['fresh_retries'] for x in r),'session_continuations':sum(x['session_continuations'] for x in r)}
        for provider in ('ds','openai','selected_ds','selected_openai'):
            val=add_observed([x[provider]['observed'] for x in r]);inputs=[val[k] for k in ('input','cache_read','cache_write') if val[k] is not None]
            val['input_including_cache']=sum(inputs) if inputs else None
            v[provider]={'observed':val,'complete_cells':sum(x[provider]['complete'] for x in r),
                'requests':sum(x[provider].get('requests',0) for x in r),'unknown_requests':sum(x[provider].get('unknown_requests',0) for x in r),
                'known_sessions':sum(x[provider].get('known_sessions',0) for x in r),'expected_reservations':sum(x[provider].get('expected_reservations',0) for x in r),
                'observed_tokens_per_success':(val['input_including_cache']+val['output'])/pass_count if pass_count and val['input_including_cache'] is not None and val['output'] is not None else None}
        answer.append(v)
    return answer


def exact_p(left_only,right_only):
    n=left_only+right_only
    return min(1.,2*sum(math.comb(n,k) for k in range(min(left_only,right_only)+1))/2**n) if n else 1.


def compare(rows,left,right):
    a={r['task_id']:r for r in rows if r['method']==left};b={r['task_id']:r for r in rows if r['method']==right}
    if set(a)!=set(b) or len(a)!=16:raise ValueError('Paired task identities required')
    left_only=right_only=both=neither=0;ratios=[];all_ratios=[]
    for task in sorted(a):
        l,r=a[task],b[task];lp=l['latest_status']=='PASS';rp=r['latest_status']=='PASS'
        left_only+=lp and not rp;right_only+=rp and not lp;both+=lp and rp;neither+=not lp and not rp
        if finite(l['selected_seconds']) and finite(r['selected_seconds']) and r['selected_seconds']>0:
            all_ratios.append(l['selected_seconds']/r['selected_seconds'])
            if lp and rp:ratios.append(l['selected_seconds']/r['selected_seconds'])
    return {'left':left,'right':right,'left_only':left_only,'right_only':right_only,'both_pass':both,'neither_pass':neither,
            'success_difference_pp':100*(left_only-right_only)/16,'paired_exact_p_exploratory':exact_p(left_only,right_only),
            'median_coding_ratio_all_common':statistics.median(all_ratios) if all_ratios else None,'time_pairs':len(all_ratios),
            'median_coding_ratio_both_pass':statistics.median(ratios) if ratios else None,'both_pass_time_pairs':len(ratios)}


def build(intake,main_latest,pi_reviewed):
    rows=normalize_main(intake,main_latest)+normalize_pi(intake,pi_reviewed)
    if len(rows)!=224:raise ValueError('224 method-task cells required; no retry denominator inflation')
    pairs=[('Best3-DS','Native-DSH-DS'),('Enhanced-DS','Native-DSH-DS'),('Enhanced-DS','Best3-DS'),
           ('DS-to-Sol','Native-Codex-Sol'),('Enhanced-DS-to-Sol','Native-Codex-Sol'),('Enhanced-DS-to-Sol','Native-DSH-DS'),('Enhanced-DS-to-Sol','DS-to-Sol'),
           ('Enhanced-DS-to-Sol','Pi-Base-Sol'),('Enhanced-DS-to-Sol','Pi-ResearchLoop-Sol')]
    pairs += [('Pi-'+name+'-'+provider,'Pi-Base-'+provider) for provider in ('DS','Sol') for name in ('SciSkills','NeuroForge','ResearchLoop')]
    comparisons=[compare(rows,*pair) for pair in pairs]
    # Holm adjustment is descriptive; no randomized population inference is claimed.
    previous=0.
    for i,r in enumerate(sorted(comparisons,key=lambda x:x['paired_exact_p_exploratory'])):
        previous=max(previous,min(1.,(len(comparisons)-i)*r['paired_exact_p_exploratory']));r['holm_adjusted_p_exploratory']=previous
    return {'status':'OFFLINE_UNIFIED_16_TASK_14_METHOD_BENCHMARK','methods':summarize(rows),'rows':rows,'comparisons':comparisons,
            'task_count':16,'method_count':14,'cell_count':224,'latest_counts':dict(Counter(r['latest_status'] for r in rows)),
            'original_ledger':intake['ledger'],'new_model_calls':0,'candidate_executions':0,'original_results_modified':False,
            'row_tokens_are_overlapping_flow_resource_projections':True,'first_reviewed_counts':dict(Counter(r['first_reviewed_status'] for r in rows))}
