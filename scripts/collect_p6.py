"""Read-only P6 report collection: allowlisted public metadata, no trace/data export."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

from wsl_project import ROOT,run


def collect(output):
    output=Path(output).resolve();private=(ROOT/'.local-workbench').resolve()
    if not output.is_relative_to(private) or output.exists():raise ValueError('New project-private report directory required')
    code='''from pathlib import Path
import json,hashlib
base=Path('/opt/workbench/benchmark/private/runs');runs=[];workers={}
for root in sorted(base.glob('p6-*')):
 if not any(t+'-' in root.name for t in ('BIP-black-2','SWEL-psf__requests-1963')):continue
 receipt=root/'receipt.json';failure=root/'failure.json';contract=root/'control/run-contract.json'
 value={'run_id':root.name,'status':'NO_FINAL_RECEIPT','arms':[]}
 if root.name.startswith('p6-offline-'):
  controls=[json.loads(q.read_text()) for q in root.glob('*/worker.json')]
  if len(controls)==3 and all(c.get('kind')=='ZERO_MODEL_CONTROL' and c.get('status')=='COMPLETED' for c in controls):value['status']='ZERO_MODEL_CONTROL_VERIFIED'
 if receipt.exists():
  r=json.loads(receipt.read_text());value.update(status=r['status'],arms=r.get('results',[]),receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest())
  for k in ('source_run','candidate_model_replays','new_merge_generation','carried_activity_seconds','scope','requests'):
   if k in r:value[k]=r[k]
 if failure.exists():
  f=json.loads(failure.read_text());value.update(status=f['status'],error_type=f['error_type'])
 if contract.exists():value['contract_sha256']=hashlib.sha256(contract.read_bytes()).hexdigest()
 if (root/'judgments.json').exists():
  j=json.loads((root/'judgments.json').read_text());value['judgments']={k:{s:d.get(s,'unavailable') for s in ('status','pool_hash','rubric_hash','evidence_hash','ranking','eligible_selected','requests','algorithm')} for k,d in j.items()}
 for q in root.glob('*/controller-outcome.json'):
  w=json.loads(q.read_text());row={k:w.get(k,'unavailable') for k in ('scope','status','error_type','model_id','session_id','elapsed_seconds','wall_seconds','input_sha256')}
  isolation=q.parent/'isolation.json'
  if isolation.exists():row['isolation']=json.loads(isolation.read_text())
  row['broker_denials']=[x['reason'] for x in w.get('broker_denials',[])]
  row['native_usage']=[{k:r.get(k,'unavailable') for k in ('session_id','model_id','status','usage')} for r in w.get('usage',[])]
  workers[w['scope']]=row
 runs.append(value)
ledger_path=Path('/opt/workbench/state/p6-budget/ledger.json');ledger=json.loads(ledger_path.read_text())
api={'requests':len(ledger['requests']),'subscription_turns':len(ledger['codex_turns']),'api_upper_bound_usd':ledger['cash_bound_nano']/1e9,
     'api_bill_usd':'unavailable','subscription_cost_usd':'unavailable','unknown_api_usage_count':sum(r.get('usage') is None for r in ledger['requests']),
     'known_api_tokens':{k:sum((r.get('usage') or {}).get(k,0) for r in ledger['requests']) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')},
     'ledger_sha256':hashlib.sha256(ledger_path.read_bytes()).hexdigest()}
prior={}
for phase in ('p1','p2','p3','p5'):
 p=Path('/opt/workbench/state')/(phase+'-budget/ledger.json');prior[phase]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'runs':runs,'workers':list(workers.values()),'budget':api,'prior_ledgers':prior}))
'''
    p=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',code],timeout=30)
    if p.returncode:raise RuntimeError('P6 report collection failed')
    data=json.loads(p.stdout);completed={}
    for r in data['runs']:
        if r['status']=='SMOKE_COMPLETED':
            for row in r['arms']:completed[(row['task_id'],row['arm'])]=(r['run_id'],row)
    rows=[];normalizations=[]
    for (task,arm),(rid,raw) in sorted(completed.items()):
        row=copy.deepcopy(raw)
        worker=next((w for w in data['workers'] if w['scope']==rid+'/relay-native'),{})
        if task=='BIP-black-2' and arm=='E' and row['outcome']=='INFRA_FAIL' and worker.get('error_type')=='DurationExceeded':
            row['outcome']='TIMEOUT'
            normalization={'run_id':rid,'task_id':task,'arm':arm,'source_evidence_sha256':raw['evidence_sha256'],
                           'reason':'Preserved relay-native worker reports DurationExceeded; earlier worker classified timeout as infrastructure failure'}
            row['evidence_sha256']=hashlib.sha256(json.dumps(normalization,sort_keys=True).encode()).hexdigest()
            normalizations.append(normalization)
        row['source_run_id']=rid;row['measurement_scope']='Native arm activity; engineering repair/downtime and additional source audit accounted separately'
        rows.append(row)
    output.mkdir(parents=True)
    (output/'audit.private.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    (output/'results.json').write_text(json.dumps({'results':rows,'normalizations':normalizations},indent=2),encoding='utf8')
    preparations={row['task_id']:{'status':'READY','task_id':row['task_id'],**{k:row[k] for k in ('env_sha256','hardware_sha256','permissions_sha256','base_commit','hidden_suite_sha256')}} for row in rows}
    (output/'preparations.json').write_text(json.dumps(preparations,indent=2),encoding='utf8')
    return {'results':len(rows),'budget':data['budget'],'prior_ledgers':data['prior_ledgers'],'output':str(output)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(collect(args.output),indent=2))
