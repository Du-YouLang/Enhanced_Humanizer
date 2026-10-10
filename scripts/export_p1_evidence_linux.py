"""Export reviewed synthetic evidence fields; keep logs, ledgers and Git bundles private."""

import hashlib
import json
from pathlib import Path
import subprocess

from p1_experiment_linux import BASE,git


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    verification=json.loads((BASE/'evidence/p1-independent-verification.json').read_text())
    ledger_path=BASE/'state/p1-budget/ledger.json'
    ledger=json.loads(ledger_path.read_text())
    report={'schema_version':1,'phase':'P1','date':'2026-10-10','functional_verdict':verification['verdict'],
            'delivery_verdict':'CI_PENDING','issue':'https://github.com/Du-YouLang/Enhanced_Humanizer/issues/5',
            'baseline_commit':'561bd401a218246f5a823e8e3e0f0eea374163aa',
            'experiments':[],'failed_attempts':[],'controls':{},'budget':{},'private_bundles':[]}
    bundle_root=BASE/'evidence/p1-bundles';bundle_root.mkdir(exist_ok=True)
    for path in sorted((BASE/'evidence').glob('p1-*.json')):
        value=json.loads(path.read_text())
        if value.get('kind')!='REAL_MODEL_EXPERIMENT':continue
        run=value['run_id'];work=BASE/'runs'/run/'worktree'
        bundle=bundle_root/(run+'.bundle')
        if not bundle.exists():git(work,'bundle','create',str(bundle),'--all')
        subprocess.run(['git','bundle','verify',str(bundle)],cwd=work,check=True,capture_output=True)
        report['private_bundles'].append({'run_id':run,'sha256':digest(bundle),'size_bytes':bundle.stat().st_size})
        if value['verdict']!='PASS':
            report['failed_attempts'].append({k:value[k] for k in ('run_id','mode','verdict','elapsed_seconds')})
            report['failed_attempts'][-1].update(record_sha256=digest(path),paid_requests=len(value['requests']),
                                                diagnosis={'p1-native-20261010T092353Z':'Unsupported --dsh-home flag; fixed in launch args',
                                                           'p1-native-20261010T092426Z':'DSH bypassed loopback proxy; transport failure before upstream request',
                                                           'p1-humanize-20261010T094121Z':'Adapter subclass lost backend metadata; fixed before any model turn'}[run])
            continue
        independent=next(r for r in verification['results'] if r['run_id']==run)
        row={k:value[k] for k in ('run_id','mode','base_commit','head_commit','verdict','model_and_tools_seconds','elapsed_seconds','child_resources','runtime_lock_sha256','prompt_sha256')}
        row.update(record_sha256=digest(path),independent_checks=independent['checks'],commits=independent['commits'])
        row['turns']=[{k:t[k] for k in ('role','harness','model_requested','session_id','elapsed_seconds','status','prompt_sha256')} for t in value['turns']]
        row['deepseek_requests']=len(value['requests'])
        row['deepseek_usage']={k:sum(r['usage'][k] for r in value['requests']) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')}
        row['deepseek_request_elapsed_seconds']=sum(r['elapsed_seconds'] for r in value['requests'])
        row['api_peak_upper_bound_usd']=sum(r['charge_bound_nano'] for r in value['requests'])/1e9
        row['codex_usage']=[{k:c[k] for k in ('session_id','model_id','usage')} for c in independent['codex_usage']]
        row['tests_passed']=value['test_log'].split('Ran ')[-1].split(' tests')[0]
        if value['mode']=='relay':
            result=value['result']
            row.update(paused=result['paused'],checkpoint_commit=result['checkpoint_commit'],handoffs=result['result']['handoffs'],
                       resumed=result['result']['resumed'],completed_steps=result['result']['next_step'])
        report['experiments'].append(row)
    for name in ('transport','controls'):
        control=BASE/'evidence'/('p1-'+name+'.json')
        value=json.loads(control.read_text())
        report['controls'][name]={'kind':value['kind'],'verdict':value['verdict'],'paid_requests':value['paid_requests'],'sha256':digest(control)}
        if name=='controls':report['controls'][name]['checks']=value['checks']
    report['controls']['independent_revalidation']={'verdict':verification['verdict'],'elapsed_seconds':verification['elapsed_seconds'],
                                                 'paid_requests':0,'sha256':digest(BASE/'evidence/p1-independent-verification.json')}
    usage={k:sum(r['usage'][k] for r in ledger['requests']) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')}
    cache_aware_peak=(usage['input_tokens']*300+usage['cache_read_input_tokens']*6+usage['output_tokens']*1200)/1e9
    codex=[c for row in report['experiments'] for c in row['codex_usage']]
    report['budget']={'deepseek_requests':len(ledger['requests']),'codex_subscription_turns':len(ledger['codex_turns']),
                      'api_peak_upper_bound_usd':ledger['cash_bound_nano']/1e9,'api_cache_aware_estimate_range_usd':[cache_aware_peak/2,cache_aware_peak],
                      'api_bill_usd':'unavailable','deepseek_usage_disjoint':usage,'cache_creation_accounting':'not_applicable_in_chat_completions',
                      'codex_usage':{k:sum(c['usage'][k] for c in codex) for k in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','total_tokens')},
                      'codex_subscription_cost_usd':'unavailable','codex_api_cash_usd':0,'ledger_sha256':digest(ledger_path)}
    relay=next(e for e in report['experiments'] if e['mode']=='relay')
    work=BASE/'runs'/relay['run_id']/'worktree'
    ds=relay['checkpoint_commit']
    snapshots={'after-ds/weighted_stats.py':git(work,'show',ds+':weighted_stats.py')+'\n'}
    for name in ('weighted_stats.py','test_weighted_stats.py','test_accumulator.py'):
        snapshots['after-sol/'+name]=(work/name).read_text()
    print(json.dumps({'report':report,'synthetic_snapshots':snapshots}))


if __name__=='__main__':main()
