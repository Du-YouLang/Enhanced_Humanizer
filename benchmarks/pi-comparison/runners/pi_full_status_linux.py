"""Read-only Pi full-main status. Never imports a model executor or credentials."""
import hashlib
import json
from pathlib import Path
import sys
import time

RUNS=Path('/opt/workbench/benchmark/private/pi-comparison')


def inspect(run_id):
    import re
    if not re.fullmatch(r'formal-full-(?:compare|controls)-[0-9TZ]+',run_id):raise ValueError('Exact full-main run ID required')
    root=RUNS/run_id
    if not root.exists():return {'run_id':run_id,'status':'NOT_CREATED','models_started_by_inspector':0}
    receipts=sorted(root.glob('receipt*.json'),key=lambda p:p.stat().st_mtime)
    receipt=json.loads(receipts[-1].read_bytes()) if receipts else None
    stages=root/'control/stages';completed=list(stages.glob('*-cell.completed.json'))
    uncertain=[p.stem.removesuffix('.started') for p in stages.glob('*.started.json')
               if not p.with_name(p.name.replace('.started.json','.completed.json')).exists()]
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();owners=[]
    for p in Path('/opt/workbench/pi-comparison/formal-launches').glob(run_id+'-*.json'):
        row=json.loads(p.read_bytes());proc=Path('/proc')/str(row['pid']);alive=False;command_verified=False
        try:
            fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
            alive=row['boot_id']==boot and fields[0]!='Z' and row['process_start_ticks']==fields[19]
            command_verified=alive and hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest()==row['command_sha256']
        except OSError:pass
        owners.append({'pid':row['pid'],'alive_exact_boot_ticks':alive,'command_hash_verified':command_verified,
                       'launch':str(p),'log':row.get('log')})
    ledger_path=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json');ledger=json.loads(ledger_path.read_bytes())
    outcomes={}
    for p in completed:
        value=json.loads(p.read_bytes())['value'];key=value['outcome'];outcomes[key]=outcomes.get(key,0)+1
    continuation=read_continuation(root)
    combined=dict(outcomes)
    for key,count in continuation['prior_outcomes'].items():combined[key]=combined.get(key,0)+count
    active=any(r['alive_exact_boot_ticks'] and r['command_hash_verified'] for r in owners)
    failures=[{'path':str(p),'error_type':json.loads(p.read_bytes()).get('error_type')} for p in root.glob('failure-*.json')]
    return {'run_id':run_id,'root':str(root),'status':receipt.get('status') if receipt and not active else 'RUNNING' if active else 'EXIT_WITHOUT_RECEIPT',
            'completed_new_cells':len(completed),'total_new_cells':continuation['total_here'],'outcomes':outcomes,
            'completed_missing_cohort_cells':len(completed)+continuation['prior_cells'],
            'total_missing_cohort_cells':112,'combined_missing_cohort_outcomes':combined,
            'retained_prior_cells':continuation['prior_cells'],'active_or_uncertain_stages':uncertain,
            'owners':owners,'failures':failures,'last_receipt':str(receipts[-1]) if receipts else None,
            'ledger':{'deepseek_requests':len(ledger['requests']),'subscription_reservations':len(ledger['codex_turns']),
                      'api_conservative_bound_usd':ledger['cash_bound_nano']/1e9,'api_cash_actual':'unavailable',
                      'remaining_deepseek_requests':10000-len(ledger['requests']),
                      'remaining_conservative_usd':200-ledger['cash_bound_nano']/1e9,
                      'sha256':hashlib.sha256(ledger_path.read_bytes()).hexdigest()},
            'models_started_by_inspector':0,'ledger_writes':0,'checked_unix':time.time()}


def read_continuation(root):
    path=root/'continuation-plan.json'
    if not path.exists():return {'total_here':112,'prior_cells':0,'prior_outcomes':{}}
    plan=json.loads(path.read_bytes());rows=[];outcomes={}
    roots=plan.get('retained_runs',[plan['original_root']])
    if len(roots)!=len(set(roots)):raise ValueError('Duplicate prior run in status')
    for root in roots:
        prior=Path(root)/'receipt.json'
        if hashlib.sha256(prior.read_bytes()).hexdigest()!=plan['retained_sha256'][str(prior)]:raise ValueError('Original retained receipt changed')
        receipt=json.loads(prior.read_bytes())
        if receipt.get('prior_completed_cells',len(rows))!=len(rows):raise ValueError('Broken status lineage')
        rows.extend(receipt['results'])
    if len(rows)!=plan['retained_cells']:raise ValueError('Retained cell count differs')
    for row in rows:outcomes[row['outcome']]=outcomes.get(row['outcome'],0)+1
    return {'total_here':len(plan['remaining_cells']),'prior_cells':len(rows),'prior_outcomes':outcomes}


if __name__=='__main__':print(json.dumps(inspect(sys.argv[1]),ensure_ascii=False))
