"""Allowlisted synthetic P2 evidence export. Raw sessions, credentials and custom research tasks stay private."""

import json
from pathlib import Path
import sys

from p1_broker import protect_memory
from p2_candidates import BASE,digest,validate_pool


def main():
    protect_memory()
    ledger_path=BASE/'state/p2-budget/ledger.json';ledger=json.loads(ledger_path.read_text())
    usage_fields=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')
    tokens={k:sum(r['usage'][k] for r in ledger['requests']) for k in usage_fields} if all('usage' in r for r in ledger['requests']) else 'unavailable'
    estimate_peak=(tokens['input_tokens']*.3+tokens['cache_read_input_tokens']*.006+tokens['output_tokens']*1.2)/1e6 if isinstance(tokens,dict) else 'unavailable'
    public={'schema_version':1,'phase':'P2','functional_verdict':'PASS','delivery_verdict':'CI_PENDING',
            'issue':'https://github.com/Du-YouLang/Enhanced_Humanizer/issues/7',
            'actual_models':{'DS':'deepseek-flash (DeepSeek V4.1 Flash)','Sol':'gpt-6.1-sol'},
            'budget':{'requests':len(ledger['requests']),'codex_turns_reserved':len(ledger['codex_turns']),
                      'api_peak_upper_bound_usd':ledger['cash_bound_nano']/1e9,'api_bill_usd':'unavailable',
                      'cache_aware_estimate_usd_range':[estimate_peak/2,estimate_peak] if isinstance(estimate_peak,float) else 'unavailable',
                      'deepseek_disjoint_tokens':tokens,'cache_creation_accounting':'not_applicable_in_chat_completions',
                      'ledger_sha256':digest(ledger_path.read_bytes()),'subscription_cost_usd':'unavailable','subscription_api_cash_usd':0,
                      'limits':{'api_cash_usd':2,'requests':100,'codex_turns':6,'per_request_seconds':120,'per_candidate_seconds':600,'per_experiment_seconds':1200},
                      'all_requests_settled':all(r['status']=='SETTLED_USAGE_UPPER_BOUND' for r in ledger['requests'])},
            'pools':[],'judge_attempts':[],'controlled_checks':[],'bundles':[],
            'limitations':['Synthetic smoke only, no efficacy estimate','J2 BLOCKED_CREDENTIAL; zero Jev requests',
                          'K1 LAV with thinking off differs from paper/default configurations',
                          'First failed Codex turn has unavailable token usage; subscriptions are not dollar bills',
                          'Provider queue and tool-only times unavailable; first-patch observation interval 0.5 seconds',
                          'Custom task contract verified offline only; no raw/custom research input exported',
                          'P3 synthesis and P6 scientific/ablation benchmark not run']}
    for path in sorted((BASE/'runs').glob('p2-n*/frozen-pool.json')):
        pool=validate_pool(json.loads(path.read_text()))
        if 'contract_manifest' in pool:raise RuntimeError('Custom task publication requires separate review')
        rows=[]
        for c in pool['candidates']:
            allowed=('id','kind','branch','base_commit','head_commit','env_hash','model_id','harness','prompt_hash','session_id',
                     'patch','source','test_report','verdict','known_failures','tokens','request_count','api_peak_upper_bound_usd',
                     'timeline','queue_seconds','api_seconds_sum','non_api_residual_seconds','api_queue_seconds','tool_seconds',
                     'verification_seconds','outer_retries','retries_observed','bundle_sha256','working_tree','frozen_test_unchanged','independent_object_store')
            row={k:c[k] for k in allowed if k in c}
            row['isolation']={'verdict':c['isolation']['verdict'],'uid':c['isolation']['uid'],
                              'private_pid_namespace':not c['isolation']['parent_namespace_visible'],
                              'denied_read_write_checks':len(c['isolation']['paths'])*2}
            worker=json.loads((path.parent/c['id']/'worker.json').read_text())
            row['isolation']['effective_capabilities_hex']=worker['cap_eff']
            if worker['cap_eff']!='0000000000000000':raise RuntimeError('Recorded worker had effective capabilities')
            row['api_timing']=[{k:r.get(k,'unavailable') for k in ('index','http_status','elapsed_seconds','first_delta_seconds','model_id')}
                               for r in c['requests']]
            rows.append(row)
        record=json.loads((BASE/'evidence'/(path.parent.name+'.json')).read_text())
        public['pools'].append({'run_id':path.parent.name,'n':len(rows),'concurrency':record['concurrency'],
                                'elapsed_seconds':record['elapsed_seconds'],'total_elapsed_seconds':record['total_elapsed_seconds'],
                                'pool_hash':pool['pool_hash'],'rubric_hash':pool['rubric_hash'],'base_commit':pool['base_commit'],
                                'env_hash':pool['env_hash'],'task_hash':pool['task_hash'],'candidates':rows,
                                'failure_report':pool['failure_report']})
    for path in sorted((BASE/'evidence').glob('p2-judge-*.json')):
        record=json.loads(path.read_text());judges=[]
        for j in record['judges']:
            clean={k:v for k,v in j.items() if k not in ('turns','usage')}
            if 'usage' in j:clean['usage']=[{k:r[k] for k in ('session_id','model_id','usage')} for r in j['usage']]
            judges.append(clean)
        public['judge_attempts'].append({'run_id':record['run_id'],'verdict':record['verdict'],'pool_hash':record['pool_hash'],
                                          'elapsed_seconds':record['total_elapsed_seconds'],'judges':judges})
    for pattern in ('p2-independent-*.json','p2-contract-cache-*.json','p2-experiment-cap-*.json'):
        for path in sorted((BASE/'evidence').glob(pattern)):
            record=json.loads(path.read_text());public['controlled_checks'].append(record)
    for root in sorted((BASE/'runs').glob('p2-*')):
        for bundle in sorted(root.glob('*.bundle')):
            cid=bundle.stem
            poolfile=root/'frozen-pool.json'
            if not poolfile.exists():continue
            pool=json.loads(poolfile.read_text());candidate=next(c for c in pool['candidates'] if c['id']==cid)
            public['bundles'].append({'run_id':root.name,'candidate_id':cid,'head_commit':candidate['head_commit'],
                                      'branch':candidate['branch'],'kind':candidate['kind'],
                                      'file':str(bundle),'sha256':digest(bundle.read_bytes()),'size_bytes':bundle.stat().st_size,
                                      'remote_archive_ref':'refs/heads/feature/7-evidence/'+root.name+'/'+cid})
    # Export acceptance is derived from evidence, never from a constant PASS label.
    if sorted(p['n'] for p in public['pools'])!=[1,3,4,5] or any(c['verdict']!='PASS' for p in public['pools'] for c in p['candidates']):
        raise RuntimeError('Real P2 candidate gate is incomplete')
    latest={}
    for attempt in public['judge_attempts']:
        for judgment in attempt['judges']:
            if judgment['status']=='COMPLETED':latest[judgment['judge']]=judgment
    if not {'J0','J1','J3'}<=set(latest):raise RuntimeError('Required real judges missing')
    if len({latest[j]['evidence_hash'] for j in ('J0','J1','J3')})!=1:raise RuntimeError('Judge evidence differs')
    if not latest['J1']['probability_evidence'] or not latest['J3']['usage']:raise RuntimeError('Probability/model evidence missing')
    if not public['controlled_checks'] or any(r['verdict']!='PASS' for r in public['controlled_checks']):
        raise RuntimeError('Offline controls incomplete')
    if not public['budget']['all_requests_settled'] or len(ledger['requests'])>100 or len(ledger['codex_turns'])>6 or ledger['cash_bound_nano']>2_000_000_000:
        raise RuntimeError('P2 budget evidence invalid')
    # All exports are reviewed synthetic tasks: paths here identify private copies, not credentials/transcripts.
    public['acceptance']={'P2-A01':'PASS_REAL_N1_N3_N4_N5','P2-A02':'PASS_REAL_AND_OFFLINE_CONTROLS',
                          'P2-A03':'PASS_J0_J1_J3; J2_BLOCKED_CREDENTIAL','P2-A04':'PASS_CONTROLLED_FAILURES_NOT_MODEL_FAILURES'}
    path=BASE/'evidence/p2-public-export.json';path.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps({'export_path':str(path),'sha256':digest(path.read_bytes()),'budget':public['budget'],
                       'real_pools':len(public['pools']),'bundles':len(public['bundles'])},indent=2))


if __name__=='__main__':main()
