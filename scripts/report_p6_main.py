"""Export the authoritative finite batch, including missing/failed attempts.

Exports outcomes and accounting only. Private oracle values, source, transcripts,
research inputs and raw acceptance outputs never enter the shareable report.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

from wsl_project import ROOT,run
sys.path.insert(0,str(ROOT/'src'))
from workbench.benchmark import check_manifest,plan,summarize,validate_result
from report_latency import tool_timing
from report_sensitivity import paired_judgments

COLLECT=r'''import json,sys,re
from pathlib import Path
sys.path.insert(0,'/opt/workbench/source')
from p6_trace_evidence import tool_trace
from export_codex_usage import collect
batch=json.load(sys.stdin);base=Path('/opt/workbench/benchmark/private/main-runs');runs=[];sessions={};unknown_sessions=[]
for attempt in batch.get('reused_attempts',[])+batch['attempts']:
 name=attempt.get('run_id')
 if not name:continue
 root=base/name;contract=json.loads((root/'control/run-contract.json').read_text())
 if contract['manifest']['manifest_sha256']!=batch['manifest_sha256']:raise ValueError('Run differs from batch manifest')
 row={'run_id':name,'task_id':attempt['task_id'],'mode':attempt['mode'],'status':attempt['status'],'arms':[]}
 if (root/'receipt.json').exists():
  receipt=json.loads((root/'receipt.json').read_text());row['controller_timing']={k:receipt.get(k,'unavailable') for k in ('controller_end_to_end_seconds','model_activity_seconds')}
 if (root/'preparation.json').exists():row['preparation']=json.loads((root/'preparation.json').read_text())
 for p in sorted(root.glob('arm-*.json')):row['arms'].append(json.loads(p.read_text()))
 if (root/'judgments.json').exists():
  d=json.loads((root/'judgments.json').read_text());row['judgments']={k:{f:v[f] for f in ('status','pool_hash','evidence_hash','ranking','raw_selected','eligible_selected','elapsed_seconds','requests') if f in v} for k,v in d.items()}
 if (root/'merge-judgments.json').exists():
  d=json.loads((root/'merge-judgments.json').read_text());row['merge_judgments']={k:{f:v[f] for f in ('status','pool_hash','evidence_hash','ranking','raw_selected','eligible_selected','elapsed_seconds','requests') if f in v} for k,v in d.items()}
 oracle=root/'private-candidate-acceptance.json'
 if attempt['mode']=='sensitivity' and (root/'receipt.json').exists():
  receipt=json.loads((root/'receipt.json').read_text());oracle=base/receipt['source_run']/'private-candidate-acceptance.json'
  row['sensitivity']={k:receipt[k] for k in ('source_run','candidate_model_replays','identity','merge_identity','incremental_metrics')}
  def public_judgments(values):
   return {k:{f:v[f] for f in ('status','pool_hash','ranking','raw_selected','eligible_selected') if f in v} for k,v in values.items()}
  row['sensitivity']['source_judgments']=public_judgments(receipt['source_judgments'])
  row['sensitivity']['source_merge_judgments']=public_judgments(receipt['source_merge_judgments'])
 if oracle.exists():
  row['candidate_acceptance']={cid:{'verdict':v['acceptance']['verdict'],'public_verdict':v['public_verdict'],'program_identity':v['program_identity'],
   'worker_status':v['worker_status'],'elapsed_seconds':v['acceptance'].get('elapsed_seconds','unavailable')} for cid,v in json.loads(oracle.read_text()).items()}
 row['role_timing']=[]
 for p in root.glob('*/controller-outcome.json'):
  w=json.loads(p.read_text())
  role={'scope':w['scope'],'status':w['status'],'wall_seconds':w['wall_seconds']}
  try:role['tool_trace']=tool_trace(p.parent)
  except (ValueError,OSError,json.JSONDecodeError) as error:role['tool_timing_unavailable_reason']=type(error).__name__
  candidate=p.parent/'candidate-private.json'
  if candidate.exists():
   c=json.loads(candidate.read_text());role['public_check_seconds']=c.get('test_report',{}).get('elapsed_seconds','unavailable')
  row['role_timing'].append(role)
  for s in w.get('usage',[]):
   if s.get('session_id')=='unavailable':unknown_sessions.append({'scope':w['scope'],'usage':'unavailable'})
   else:sessions[s['session_id']]={'scope':w['scope'],'model_id':s['model_id'],'usage':s['usage']}
 runs.append(row)
ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json');accounting=None
if ledger.exists():
 v=json.loads(ledger.read_text());requests=v['requests'];settled=[r for r in requests if isinstance(r.get('usage'),dict)]
 phase_sessions={};missing_reservations=[]
 for reservation in v['codex_turns']:
  scope=reservation['experiment'];parts=scope.split('/')
  if len(parts)!=2 or not all(re.fullmatch(r'[A-Za-z0-9_-]+',part) for part in parts):raise ValueError('Invalid trusted reservation scope')
  role=base/parts[0]/parts[1];native=[]
  # Candidate worktrees cannot supply authoritative usage files.
  roots=[role/'home/.codex/sessions',*role.glob('humanize/epics/*/*/sessions/codex/sessions')]
  for source in roots:
   if source.exists():native.extend(collect(source))
  if not native:missing_reservations.append({'scope':scope,'usage':'unavailable','reason':'No trusted native session receipt'})
  for session in native:
   key=session['session_id']
   if key=='unavailable':missing_reservations.append({'scope':scope,'usage':'unavailable','reason':'Native session identity unavailable'});continue
   phase_sessions[key]={'scope':scope,'requested_model':reservation['model'],'session_id':key,'model_id':session['model_id'],'usage':session['usage']}
 known_subscription=[s['usage'] for s in phase_sessions.values() if isinstance(s['usage'],dict)]
 accounting={'phase':v['phase'],'deepseek_requests':len(requests),'unknown_request_usage':len(requests)-len(settled),
  'deepseek_known_input_tokens':sum(sum(r['usage'].get(k,0) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens')) for r in settled),
  'deepseek_known_output_tokens':sum(r['usage']['output_tokens'] for r in settled),'deepseek_known_cache_read_tokens':sum(r['usage']['cache_read_input_tokens'] for r in settled),
  'api_upper_bound_usd':v['cash_bound_nano']/1e9,'api_cash_usd':'unavailable','subscription_turns':len(v['codex_turns']),
  'subscription_cost_usd':'unavailable','subscription_sessions':list(phase_sessions.values()),
  'unknown_subscription_sessions':[{'scope':s['scope'],'session_id':s['session_id'],'usage':'unavailable'} for s in phase_sessions.values() if not isinstance(s['usage'],dict)],
  'unknown_subscription_reservations':missing_reservations,
  'subscription_known_input_tokens':sum(s.get('input_tokens',0) for s in known_subscription),
  'subscription_known_cached_input_tokens':sum(s.get('cached_input_tokens',0) for s in known_subscription),
  'subscription_known_output_tokens':sum(s.get('output_tokens',0) for s in known_subscription),
  'subscription_usage_scope':'All phase reservations, including stopped attempts; unique trusted native sessions. Cached input is a subset of input. Visible token records can be partial; missing usage is not zero. One reservation may contain multiple native sessions.',
  'api_request_timing':[{'scope':r['experiment'],'elapsed_seconds':r.get('elapsed_seconds','unavailable'),'first_delta_seconds':r.get('first_delta_seconds','unavailable'),'usage_status':r['status']} for r in requests],
  'scope':'Actual phase ledger, including preserved failures and both sensitivity pools; per-arm costs reuse components and must not be summed as phase expenditure'}
print(json.dumps({'runs':runs,'accounting':accounting}))
'''


def comparisons(entry):
    truth=entry.get('candidate_acceptance',{});result={}
    for group in ('judgments','merge_judgments'):
        judges=entry.get(group,{})
        if not judges:continue
        values={}
        for name,j in judges.items():
            row={'status':j['status'],'pool_hash':j['pool_hash']}
            for choice in ('raw_selected','eligible_selected'):
                selected=j.get(choice);verdict=truth.get(selected,{}).get('verdict')
                row[choice]=selected
                row[choice+'_accepted']=verdict=='PASS' if verdict in ('PASS','FAIL','TIMEOUT') else 'unavailable'
                row[choice+'_oracle_verdict']=verdict or 'unavailable'
            values[name]=row
        pairs=[]
        from itertools import combinations
        complete={k:v for k,v in judges.items() if v['status']=='COMPLETED'}
        for (left,a),(right,b) in combinations(complete.items(),2):
            if a['pool_hash']!=b['pool_hash'] or set(a['ranking'])!=set(b['ranking']):raise ValueError('Judge ranking comparison changed pool')
            ids=a['ranking'];pa={v:i for i,v in enumerate(ids)};pb={v:i for i,v in enumerate(b['ranking'])}
            orders=[(pa[x]<pa[y])==(pb[x]<pb[y]) for x,y in combinations(ids,2)]
            pairs.append({'judges':[left,right],'pairwise_order_agreement':sum(orders)/len(orders) if orders else 'unavailable'})
        result[group]={'selection':values,'ranking_agreement':pairs}
    if 'M' in truth:
        result['merge']={'M_independent_verdict':truth['M']['verdict'],
            'all_originals_failed_public':all(truth[cid]['public_verdict']!='PASS' for cid in 'ABC'),
            'all_originals_failed_independent':all(truth[cid]['verdict']=='FAIL' for cid in 'ABC')}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--plots',action='store_true')
    a=p.parse_args()
    for path in (a.batch,a.output):
        if not path.resolve().is_relative_to(ROOT):raise ValueError('Reports and batch evidence must stay in the project')
    batch=json.loads(a.batch.read_text());manifest_path=ROOT/batch.get('manifest_file','configs/benchmark-p6-v3.json')
    if not manifest_path.resolve().is_relative_to(ROOT):raise ValueError('Manifest must stay in the project')
    manifest=json.loads(manifest_path.read_text());check_manifest(manifest)
    if manifest['manifest_sha256']!=batch['manifest_sha256']:raise ValueError('Wrong frozen manifest for batch')
    result=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',COLLECT],input_bytes=json.dumps(batch).encode(),timeout=60)
    if result.returncode:raise RuntimeError('Unable to collect exact batch evidence')
    evidence=json.loads(result.stdout);rows={(r['task_id'],r['arm']):r for r in plan(manifest)};seen=set()
    for entry in evidence['runs']:
        for role in entry['role_timing']:
            trace=role.pop('tool_trace',None)
            if trace is not None:
                try:role['native_tool_timing']=tool_timing(trace)
                except ValueError as error:role['tool_timing_unavailable_reason']=str(error)
        if 'sensitivity' in entry:
            value=entry['sensitivity'];truth=entry.get('candidate_acceptance',{})
            entry['paired_tool_trace_sensitivity']={
                'original_pool':paired_judgments(value['source_judgments'],entry['judgments'],value['identity'],truth),
                'expanded_pool':paired_judgments(value['source_merge_judgments'],entry['merge_judgments'],value['merge_identity'],truth),
                'incremental_metrics':value['incremental_metrics'],'source_run':value['source_run'],
                'candidate_model_replays':value['candidate_model_replays']}
    for entry in evidence['runs']:
        if entry['mode']!='execute':continue
        if entry['task_id'] in seen:raise ValueError('Repeated task attempt requires explicit investigation, never best-attempt selection')
        seen.add(entry['task_id'])
        for r in entry['arms']:
            validate_result(r,manifest,entry['preparation']);rows[r['task_id'],r['arm']]=r
        for arm in 'ABCDEF':
            r=rows[entry['task_id'],arm]
            if r['outcome']=='NOT_RUN':r['reason']='No accepted arm receipt; preserved controller status '+entry['status']
    rows=list(rows.values());report={'status':'EXPLORATORY_MAIN_REPORT_NOT_PHASE_ACCEPTANCE','batch_status':batch['status'],
        'manifest_sha256':manifest['manifest_sha256'],'continuation_of':batch.get('continuation_of'),'reused_attempts':batch.get('reused_attempts',[]),'rows':rows,'summary':summarize(rows),'phase_accounting':evidence['accounting'],
        'judge_and_merge_comparisons':[{**{k:v for k,v in e.items() if k!='arms'},'comparison_metrics':comparisons(e)} for e in evidence['runs']],
        'latency_coverage':{
            'observed':['Actual controller matrix wall time when its receipt exists','Per-role wall time','Paired native tool-call/result interval union','Independent controller public-check elapsed','Private acceptance elapsed','Request first delta and API round-trip when visible','Judge/Reviewer/Builder elapsed when present'],
            'unavailable':{k:'No authoritative event measurement in this protocol; do not substitute tool success text, filesystem mtime, or logical arm sums' for k in ('time_to_first_patch','time_to_first_test_pass','user_wall_time_to_accepted','DS_provider_queue_seconds','DS_provider_generation_seconds','human_active_intervention_seconds')},
            'ci':'Development and owner-reviewed product CI are separate delivery evidence, not simulated per-arm CI',
            'time_basis':'Logical arm component times and actual serial matrix controller wall are separate; shared components and parallel tool intervals must not be added twice'},
        'limitations':['Selected convenience tasks; not representative or equal in difficulty','One seed/repetition; no efficacy significance claim',
                      'Scientific numerical passes still need substantive review','Unknown usage/cash/subscription cost is unavailable, not zero',
                      'First patch/test-pass/user acceptance event latency and provider queue/generation remain unmeasured; this is an explicit full-P6 acceptance gap',
                      'Private data/oracle/raw trajectories are excluded','Development chat usage and hardware electricity cost are unavailable and excluded from benchmark role ledger']}
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (a.output/'results.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['task_id','arm','outcome','reason','end_to_end_seconds','model_and_public_check_seconds','independent_acceptance_seconds','input_tokens','output_tokens','cache_read_tokens','api_upper_bound_usd','subscription_turns']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:row.get(k,row['metrics'].get(k,'unavailable')) for k in fields})
    if a.plots:
        import os
        os.environ['MPLCONFIGDIR']=str(ROOT/'.local-workbench/cache/matplotlib')
        import matplotlib
        matplotlib.use('Agg');import matplotlib.pyplot as plt
        arms=list('ABCDEF');fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
        bottom=[0]*len(arms)
        for outcome,color in zip(('PASS','FAIL','TIMEOUT','INFRA_FAIL','INDETERMINATE','NOT_RUN'),
                                 ('#25845e','#b94a48','#d39629','#7e586f','#686eb3','#dcdfe6')):
            counts=[sum(r['outcome']==outcome for r in rows if r['arm']==arm) for arm in arms]
            axes[0].bar(arms,counts,bottom=bottom,label=outcome,color=color)
            bottom=[a+b for a,b in zip(bottom,counts)]
        axes[0].set(title='Independent outcomes; missing retained',ylabel='Tasks',ylim=(0,16))
        axes[0].legend(fontsize=7,loc='upper left')
        for axis,metric,title in ((axes[1],'end_to_end_seconds','Known logical arm time (s)'),(axes[2],'api_upper_bound_usd','Known API upper bound (USD)')):
            values=[report['summary']['arms'][arm]['metrics'][metric]['known_sum']
                    if report['summary']['arms'][arm]['metrics'][metric]['known_count'] else float('nan') for arm in arms]
            axis.bar(arms,values);axis.set_title(title)
        fig.suptitle('Exploratory selected tasks; API bounds exclude subscription price')
        fig.savefig(a.output/'summary.png',dpi=180);fig.savefig(a.output/'summary.svg');plt.close(fig)
    print(json.dumps({'status':report['status'],'rows':len(rows),'summary':{arm:r['outcomes'] for arm,r in report['summary']['arms'].items()},'output':str(a.output)}))


if __name__=='__main__':main()
