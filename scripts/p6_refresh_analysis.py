"""Offline typed views of the frozen144 cells; never dispatch or edit candidates."""
import copy
import hashlib
import html
import json
import math
import statistics
from p6_refresh_protocol import TASKS,MODELS,METHODS

EXPECTED={(t,m,f) for t in TASKS for m in MODELS for f in METHODS}
MODEL_LABELS={'GPT61-Sol':'GPT-6.1-Sol','GPT62-Sol':'GPT-6.2-Sol','DS41-Flash1017':'DeepSeek-V4.1-Flash-1017'}
METHOD_LABELS={'Direct':'Direct','Enhanced':'Enhanced','SingleAgent-MatchedBudget':'MatchedBudget'}
SUPPLEMENTS={(TASKS[0],m,'Enhanced') for m in ('GPT61-Sol','GPT62-Sol')}


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def key(row):return row['task_id'],row['model'],row['method']
def method_label(model,method):return METHOD_LABELS[method]+'-'+MODEL_LABELS[model]


def count(value):
    if type(value)is not int or value<0:raise ValueError('Nonnegative integer telemetry required')
    return value


def elapsed(value):
    if value is None or isinstance(value,str):return None
    if type(value)not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('Invalid elapsed observation')
    return value


def index_rows(rows):
    result={}
    for row in rows:
        k=key(row)
        if k not in EXPECTED or k in result:raise ValueError('Unknown or duplicate model-task-method cell')
        if not isinstance(row.get('outcome'),str) or not row['outcome']:raise ValueError('Actual outcome required')
        result[k]=row
    return result


def eligible_pass(row):
    c=row.get('candidate');f=row.get('frozen')
    return (row.get('outcome')=='PASS' and isinstance(c,dict) and isinstance(f,dict)
        and c.get('verdict')=='PASS' and c.get('test_report',{}).get('verdict')=='PASS'
        and c.get('working_tree')=='' and c.get('protected_paths_modified')==[]
        and c.get('head_commit')!=c.get('base_commit') and bool(f.get('program_sha256'))
        and row.get('acceptance',{}).get('verdict')=='PASS')


def views(rows,supplements=(),adjudications=(),*,final=False):
    raw=index_rows(rows);reviewed={k:copy.deepcopy(v) for k,v in raw.items()};origins={k:'ORIGINAL_RAW' for k in raw}
    seen=set()
    for row in supplements:
        k=key(row)
        if k not in SUPPLEMENTS or k in seen or k not in raw:raise ValueError('Unexpected/duplicate interface supplement')
        if raw[k]['outcome']!='INDETERMINATE':raise ValueError('Supplement cannot replace a completed success/failure')
        if row['outcome']=='PASS' and not eligible_pass(row):raise ValueError('Supplement PASS lacks frozen public/hidden evidence')
        reviewed[k]=copy.deepcopy(row);origins[k]='SEPARATE_INTERFACE_SUPPLEMENT';seen.add(k)
    audited=set()
    for a in adjudications:
        k=tuple(a['cell'])
        if k not in reviewed or not k[0].startswith('SCI-') or k in audited:raise ValueError('Unexpected/duplicate science adjudication')
        row=reviewed[k]
        if a.get('row_sha256')!=digest(row) or a.get('independent_review') is not True:raise ValueError('Science audit not bound to exact retained row')
        program=row.get('frozen',{}).get('program_sha256') if row.get('frozen') else None
        if a.get('program_sha256')!=program:raise ValueError('Science audit is for another program')
        if a.get('status')not in ('PASS','FAIL','INDETERMINATE'):raise ValueError('Explicit science status required')
        if a['status']!='PASS' and (not a.get('reason') or not a.get('evidence')):raise ValueError('Unresolved/failed science review requires reason and retained evidence')
        if a['status']=='PASS':
            if (row.get('candidate')or{}).get('verdict')!='PASS':raise ValueError('Science review cannot bypass failed public contract')
            if a.get('numerical')!='PASS' or a.get('source_method')!='PASS':raise ValueError('Scientific PASS always requires numerical and source-method PASS')
            for field in ('numerical','source_method','report','figure'):
                value=a.get(field)
                if value not in ('PASS','NOT_REQUIRED'):raise ValueError('Scientific PASS needs independent source/report/figure/numeric review')
                if value=='NOT_REQUIRED' and not a.get(field+'_reason'):raise ValueError('Optional artifact exclusion requires contract evidence')
            if not a.get('evidence'):raise ValueError('Scientific review evidence required')
        row['reviewed_outcome']=a['status'];row['science_adjudication']=copy.deepcopy(a);audited.add(k)
    for k,row in reviewed.items():
        if k[0].startswith('SCI-') and k not in audited:row['reviewed_outcome']='PENDING_SCIENTIFIC_REVIEW'
        else:row.setdefault('reviewed_outcome',row['outcome'])
        if not k[0].startswith('SCI-') and row['reviewed_outcome']=='PASS' and not eligible_pass(row):raise ValueError('Software PASS lacks frozen acceptance')
        row['result_origin']=origins[k]
    if final and (set(raw)!=EXPECTED or len(audited)!=36):raise ValueError('Final report requires144 unique cells and36 independently audited scientific cells')
    return raw,reviewed


def telemetry(row):
    metrics=row.get('metrics') or {};result={}
    ds=metrics.get('deepseek');oa=metrics.get('openai')
    result['deepseek']=None if ds is None else {k:count(ds[k]) for k in ('requests','known_usage_requests','unknown_usage_requests','input_tokens_known','cache_read_input_tokens_known','output_tokens_known')}
    if ds is not None:
        if ds['known_usage_requests']+ds['unknown_usage_requests']!=ds['requests']:raise ValueError('DS request coverage mismatch')
        if ds['cache_read_input_tokens_known']>ds['input_tokens_known']:raise ValueError('DS cached tokens are a subset')
        result['deepseek']['lower_bound']=bool(ds['unknown_usage_requests'] or ds.get('token_totals_are_lower_bounds'))
    result['openai']=None if oa is None else {k:count(oa[k]) for k in ('subscription_reservations','recorded_session_usage_segments','input_tokens_recorded','cached_input_tokens_subset','output_tokens_recorded')}
    if oa is not None:
        if oa['cached_input_tokens_subset']>oa['input_tokens_recorded']:raise ValueError('OpenAI cached tokens are a subset')
        result['openai']['lower_bound']=bool(oa.get('token_totals_are_lower_bounds') or oa.get('unknown_usage_scopes') or (oa['subscription_reservations']>0 and oa['recorded_session_usage_segments']==0))
    timing=row.get('method_timing')or{};seconds=elapsed(timing.get('elapsed_seconds'))
    io=timing.get('io_adjustment')or{};adjusted=None
    if seconds is not None and io:
        raw_time=elapsed(io.get('raw_elapsed_seconds'));stall=elapsed(io.get('full_local_io_stall_seconds'));estimate=elapsed(io.get('io_adjusted_elapsed_estimate_seconds'))
        if None not in (raw_time,stall,estimate):
            if abs(raw_time-seconds)>1e-6 or stall>raw_time or abs(raw_time-stall-estimate)>1e-6:raise ValueError('I/O adjustment not bound to the full method interval')
            adjusted=estimate
    acceptance=row.get('acceptance_io_adjustment')or{}
    validation_seconds=elapsed(acceptance.get('raw_elapsed_seconds'))
    if validation_seconds is None:validation_seconds=elapsed((row.get('acceptance',{}).get('trusted_measurement')or{}).get('monotonic_seconds'))
    result.update(elapsed_seconds=seconds,io_adjusted_estimate_seconds=adjusted,hidden_acceptance_seconds=validation_seconds,
        active_phase_sum_seconds=seconds+validation_seconds if seconds is not None and validation_seconds is not None else None,
        timing_unavailable_reason=timing.get('elapsed_seconds') if seconds is None else None)
    return result


def aggregate_provider(items,name):
    present=[v[name] for v in items if v[name]is not None]
    if not present:return None
    keys=[k for k in present[0] if k!='lower_bound']
    return dict({k:sum(v[k] for v in present) for k in keys},lower_bound=len(present)!=len(items) or any(v['lower_bound'] for v in present),telemetry_components=len(present))


def summaries(raw,reviewed,infrastructure_attempts=()):
    output=[]
    for model in MODELS:
        for method in METHODS:
            items=[v for k,v in reviewed.items() if k[1:]==(model,method)];tr=[telemetry(v) for v in items];projections=list(tr)
            for row in items:
                retained=(row.get('metrics')or{}).get('retained_builders_projection_not_additive_bill')
                if retained:projections.append(telemetry({'metrics':retained}))
            times=[v['elapsed_seconds'] for v in tr if v['elapsed_seconds']is not None]
            hidden=[v['hidden_acceptance_seconds'] for v in tr if v['hidden_acceptance_seconds']is not None]
            active_sums=[v['active_phase_sum_seconds'] for v in tr if v['active_phase_sum_seconds']is not None]
            adjusted=[v['io_adjusted_estimate_seconds'] for v in tr if v['io_adjusted_estimate_seconds']is not None]
            counts={}
            for row in items:counts[row['reviewed_outcome']]=counts.get(row['reviewed_outcome'],0)+1
            # Count actual original attempts plus NEW downstream telemetry. Never
            # add the nested retained-builder resource projection a second time.
            attempts=[]
            for k,row in reviewed.items():
                if k[1:]!=(model,method):continue
                attempts.append(telemetry(raw[k]))
                if row['result_origin']=='SEPARATE_INTERFACE_SUPPLEMENT':attempts.append(telemetry(row))
            for attempt in infrastructure_attempts:
                if tuple(attempt['cell'])[1:]==(model,method):attempts.append(telemetry({'metrics':attempt['metrics']}))
            output.append({'model':model,'method':method,'name':method_label(model,method),'completed_cells':len(items),'expected_cells':16,
                'successes':counts.get('PASS',0),'outcomes':counts,'software_successes':sum(v['reviewed_outcome']=='PASS' for v in items if not v['task_id'].startswith('SCI-')),
                'scientific_successes':sum(v['reviewed_outcome']=='PASS' for v in items if v['task_id'].startswith('SCI-')),
                'elapsed_measured_cells':len(times),'elapsed_sum_seconds':sum(times) if times else None,'elapsed_median_seconds':statistics.median(times) if times else None,
                'hidden_acceptance_measured_cells':len(hidden),'hidden_acceptance_sum_seconds':sum(hidden) if hidden else None,'hidden_acceptance_median_seconds':statistics.median(hidden) if hidden else None,
                'active_phase_sum_measured_cells':len(active_sums),'active_phase_sum_seconds':sum(active_sums) if active_sums else None,'active_phase_sum_median_seconds':statistics.median(active_sums) if active_sums else None,
                'io_adjusted_measured_cells':len(adjusted),'io_adjusted_sum_seconds':sum(adjusted) if adjusted else None,'io_adjusted_median_seconds':statistics.median(adjusted) if adjusted else None,
                'all_attempt_deepseek':aggregate_provider(attempts,'deepseek'),'all_attempt_openai':aggregate_provider(attempts,'openai'),
                'completed_cell_deepseek_projection':aggregate_provider(projections,'deepseek'),'completed_cell_openai_projection':aggregate_provider(projections,'openai'),
                'actual_cash':'unavailable','shared_builder_projection_is_not_an_additional_bill':True})
    return output


def binary_outcome(status):
    if status=='PASS':return True
    if status in ('FAIL','TIMEOUT','OUTPUT_LIMIT','BUDGET_EXHAUSTED'):return False
    return None


def paired_comparisons(reviewed,*,include_corrected=False):
    output=[]
    for model in MODELS:
        for left,right in (('Enhanced','Direct'),('Enhanced','SingleAgent-MatchedBudget'),('SingleAgent-MatchedBudget','Direct')):
            pairs=[(reviewed.get((t,model,left)),reviewed.get((t,model,right))) for t in TASKS]
            excluded=[t for t,(a,b) in zip(TASKS,pairs) if a and b and not include_corrected and any(r.get('result_origin')=='SEPARATE_INTERFACE_SUPPLEMENT' for r in (a,b))]
            complete=[(a,b) for t,(a,b) in zip(TASKS,pairs) if t not in excluded and a and b and binary_outcome(a['reviewed_outcome'])is not None and binary_outcome(b['reviewed_outcome'])is not None]
            wins=sum(binary_outcome(a['reviewed_outcome'])is True and binary_outcome(b['reviewed_outcome'])is False for a,b in complete)
            losses=sum(binary_outcome(a['reviewed_outcome'])is False and binary_outcome(b['reviewed_outcome'])is True for a,b in complete);n=wins+losses
            p=min(1.,2*sum(math.comb(n,k) for k in range(min(wins,losses)+1))/2**n) if n else 1.
            ratios=[];adjusted=[]
            for a,b in complete:
                if a['reviewed_outcome']!=b['reviewed_outcome'] or a['reviewed_outcome']!='PASS':continue
                ta,tb=telemetry(a),telemetry(b)
                if ta['elapsed_seconds']is not None and tb['elapsed_seconds']is not None and tb['elapsed_seconds']>0:ratios.append(ta['elapsed_seconds']/tb['elapsed_seconds'])
                if ta['io_adjusted_estimate_seconds']is not None and tb['io_adjusted_estimate_seconds']is not None and tb['io_adjusted_estimate_seconds']>0:adjusted.append(ta['io_adjusted_estimate_seconds']/tb['io_adjusted_estimate_seconds'])
            output.append({'model':model,'left':left,'right':right,'comparison_view':'QUALITY_WITH_CORRECTED_SUPPLEMENTS' if include_corrected else 'UNCHANGED_PROCESS_PAIRS','excluded_corrected_tasks':excluded,'paired_tasks':len(complete),'discordant_pairs':n,'left_only_success':wins,'right_only_success':losses,
                'exploratory_paired_sign_p':p,'bonferroni_nine_comparisons_p':min(1.,9*p),'mutual_success_timing_pairs':len(ratios),
                'median_left_over_right_elapsed':statistics.median(ratios) if ratios else None,'io_adjusted_pairs':len(adjusted),
                'median_left_over_right_io_estimate':statistics.median(adjusted) if adjusted else None,
                'interpretation':'Exploratory convenience-task comparison; repository/task dependencies and single stochastic runs limit population and causal claims.'})
    return output


def accounting_reconciliation(summary,reference,*,final=False):
    # A final directory must account for ALL refresh attempts across all three
    # run IDs, including retained infrastructure prefixes and supplements.
    fields={'deepseek':('requests','known_usage_requests','unknown_usage_requests','input_tokens_known','cache_read_input_tokens_known','output_tokens_known'),
            'openai':('subscription_reservations','recorded_session_usage_segments','input_tokens_recorded','cached_input_tokens_subset','output_tokens_recorded')}
    if reference is None:
        if final:raise ValueError('Final report requires independent all-refresh accounting reference')
        return {'status':'REFERENCE_UNAVAILABLE_PROGRESS_ONLY'}
    comparisons={};equal=True
    for provider,names in fields.items():
        expected=telemetry({'metrics':reference})[provider]
        if expected is None:raise ValueError('Provider accounting reference unavailable')
        actual=[row['all_attempt_'+provider] for row in summary if row['all_attempt_'+provider]is not None]
        comparisons[provider]={}
        for name in names:
            observed=sum(v[name] for v in actual);target=expected[name]
            comparisons[provider][name]={'closed_directory':observed,'all_refresh_attempts':target,'difference':target-observed}
            equal=equal and observed==target
    if final and not equal:raise ValueError('Final refresh accounting does not reconcile with all retained attempts')
    return {'status':'EXACT_ALL_ATTEMPTS_RECONCILED' if equal else 'PROGRESS_UNCLOSED_OR_INFLIGHT_USAGE_REMAINS','comparisons':comparisons}


def build(snapshot,*,final=False):
    rows=[r for g in snapshot.get('groups',[]) for r in g['rows']]
    supplements=[r for g in snapshot.get('interface_supplements',[]) for r in g['rows']]
    raw,reviewed=views(rows,supplements,snapshot.get('science_adjudications',[]),final=final)
    summary=summaries(raw,reviewed,snapshot.get('infrastructure_attempts',[]))
    accounting=accounting_reconciliation(summary,snapshot.get('all_refresh_accounting_reference'),final=final)
    return {'status':'FINAL_REVIEWED_144' if final else 'PROGRESS_SNAPSHOT_NOT_FINAL','unique_cells':len(raw),'expected_cells':144,
        'science_audits':len(snapshot.get('science_adjudications',[])),'interface_supplements_separate':len(supplements),
        'summary':summary,'accounting_reconciliation':accounting,'paired':paired_comparisons(reviewed),'paired_quality_including_corrections':paired_comparisons(reviewed,include_corrected=True),'raw_rows':[raw[k] for k in sorted(raw)],
        'reviewed_rows':[reviewed[k] for k in sorted(reviewed)],'run_id':snapshot.get('run_id'),'provenance':snapshot.get('provenance'),
        'budget':snapshot.get('budget'),'infrastructure_attempts_separate':snapshot.get('infrastructure_attempts',[]),'shared_projections_not_additive_bills':True,
        'limitations':['Resource match is total model-active-time ceiling, not equal realized tokens/calls/cash.',
        'Enhanced uses tested-model builders plus fixed GPT-6.1-Sol reviewers/judges.',
        'Original invalid interface outcomes/costs stay retained; corrected supplements do not increase144-cell denominator.',
        'Main quality counts include the two explicitly corrected interface cells. Unchanged-process pair comparisons exclude them; a separate all-quality comparison remains available.',
        'Method elapsed includes solving/public checks and excludes hidden acceptance; the latter is reported separately. Active-phase sums exclude waiting for other experimental methods and unmeasured outer bookkeeping.',
        'Local I/O-adjusted estimates are sensitivity measurements, not causal zero-latency-disk speed.',
        'Missing/split durations remain unavailable. Cache input and reasoning output are subsets, not extra tokens.',
        'Historical provider invoices and subscription cash are unavailable; do not interpret conservative bounds as paid bills.']}
