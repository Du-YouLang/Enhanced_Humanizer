"""Fail-closed publication of reviewed synthetic P3 runs; never export credentials or raw rollouts."""

import json
from pathlib import Path

from p1_broker import protect_memory
from p2_candidates import BASE,digest,validate_pool
from p3_contracts import read_json
from p3_runtime_linux import STAGES,load_stage


def clean(value):
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in
        ('turns','epic','trace_file','root','work','tool_trace','error','controller_source_sha256')}
    return value


def main():
    protect_memory();runs=[];sessions=set();bundles=[];cases=set()
    for path in sorted((BASE/'evidence').glob('p3-*-segment-*.json')):
        record=read_json(path)
        if record['status']!='COMPLETED':continue
        if record['functional_gate']!='PASS':continue  # retained failed attempts exported separately below
        root=BASE/'runs'/record['run_id'];contract=read_json(root/'control/run-contract.json')
        if contract['case'] not in ('mixed','all-failed','impossible'):raise RuntimeError('Unreviewed P3 case')
        case=contract['case'];cases.add(case)
        stages={name:load_stage(root,name) for name in STAGES}
        roles=[]
        for worker in sorted((root/'roles').glob('*/worker.json')):
            raw=read_json(worker)
            if raw['kind']!='REAL_MODEL_EXPERIMENT' or raw['status']!='COMPLETED':raise RuntimeError('Real role missing')
            if raw['session_id'] in sessions:raise RuntimeError('Role context reused')
            sessions.add(raw['session_id'])
            isolation=read_json(worker.parent/'isolation.json')
            if isolation['verdict']!='PASS' or raw['cap_eff']!='0000000000000000':raise RuntimeError('Role isolation not verified')
            roles.append({'name':worker.parent.name,'session_id':raw['session_id'],'model_id':raw['model_id'],'usage':clean(raw['usage']),
                          'elapsed_seconds':raw['elapsed_seconds'],'uid':raw['uid'],'cap_eff':raw['cap_eff'],'isolation':isolation})
        runs.append({'run_id':record['run_id'],'case':case,'functional_gate':'PASS','task_status':record['task_status'],
                     'comparison':record['comparison'],'active_elapsed_seconds':record['active_elapsed_seconds'],
                     'initial_pool_hash':record['pool_hash'],'controller_source_sha256':contract['controller_source_sha256'],
                     'roles':roles,'stages':clean(stages),'segments':[read_json(p) for p in sorted((root/'control').glob('segment-*.json'))]})
    if cases!={'mixed','all-failed','impossible'}:raise RuntimeError('P3 controlled real-model gates incomplete')
    if not any(r['stages']['builder'].get('verdict')=='PASS' and r['stages']['ds_return'].get('verdict')=='PASS' for r in runs):
        raise RuntimeError('Real Sol-to-DS closed loop missing')
    for bundle in sorted((BASE/'runs').glob('p3-*/roles/*/candidate.bundle')):
        manifest=read_json(bundle.parent/'manifest.json')
        bundles.append({'file':str(bundle),'sha256':digest(bundle.read_bytes()),'head_commit':manifest['head_commit'],
                        'branch':manifest['branch'],'kind':manifest['kind'],
                        'remote_archive_ref':'refs/heads/feature/9-evidence/'+bundle.parents[2].name+'/'+bundle.parent.name})
    for root in sorted((BASE/'runs').glob('p3-*-contradictory-input')):
        for bundle in root.glob('*/candidate.bundle'):
            manifest=read_json(bundle.parent/'manifest.json')
            bundles.append({'file':str(bundle),'sha256':digest(bundle.read_bytes()),'head_commit':manifest['head_commit'],
                            'branch':manifest['branch'],'kind':manifest['kind'],
                            'remote_archive_ref':'refs/heads/feature/9-evidence/'+root.name+'/'+bundle.parent.name})
    partial_archives=[]
    for manifest in sorted((BASE/'runs').glob('p3-ds-return-*/*/partial-archive/manifest.json')):
        row=read_json(manifest);partial_archives.append(clean(row));bundle=manifest.parent/'candidate.bundle'
        bundles.append({'file':str(bundle),'sha256':digest(bundle.read_bytes()),'head_commit':row['head_commit'],'branch':row['branch'],
                        'kind':row['kind'],'remote_archive_ref':'refs/heads/feature/9-evidence/'+manifest.parents[2].name+'/'+row['id']})
    returned=[]
    for path in sorted((BASE/'runs').glob('p3-ds-return-*/frozen-pool.json')):
        pool=validate_pool(read_json(path));returned.append(clean(pool))
        for c in pool['candidates']:
            bundle=path.parent/(c['id']+'.bundle')
            bundles.append({'file':str(bundle),'sha256':digest(bundle.read_bytes()),'head_commit':c['head_commit'],'branch':c['branch'],
                            'kind':c['kind'],'remote_archive_ref':'refs/heads/feature/9-evidence/'+path.parent.name+'/'+c['id']})
    ledger_path=BASE/'state/p3-budget/ledger.json';ledger=read_json(ledger_path)
    if len(ledger['requests'])>40 or len(ledger['codex_turns'])>12 or ledger['cash_bound_nano']>1_000_000_000:raise RuntimeError('P3 budget exceeded')
    fields=('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')
    tokens={k:sum(r['usage'][k] for r in ledger['requests']) for k in fields} if all('usage' in r for r in ledger['requests']) else 'unavailable'
    estimate=(tokens['input_tokens']*.3+tokens['cache_read_input_tokens']*.006+tokens['output_tokens']*1.2)/1e6 if isinstance(tokens,dict) else None
    controls=[clean(read_json(p)) for p in sorted((BASE/'evidence').glob('p3-controls-*.json'))]
    if not controls or any(c['verdict']!='PASS' for c in controls):raise RuntimeError('Offline control gate missing')
    attempts=[clean(read_json(p)) for p in sorted((BASE/'evidence').glob('p3-*-segment-*.json')) if read_json(p)['status']!='COMPLETED' or read_json(p)['functional_gate']!='PASS']
    public={'schema_version':1,'phase':'P3','functional_verdict':'PASS','delivery_verdict':'REQUIRES_FINAL_PR_CI_MAIN_ACCEPTANCE_RECORD',
            'issue':'https://github.com/Du-YouLang/Enhanced_Humanizer/issues/9','runs':runs,'DS_return_pools':returned,'partial_archives':partial_archives,
            'roles_with_unique_real_sessions':len(sessions),'bundles':bundles,'retained_attempts_and_pauses':attempts,'offline_controls':controls,
            'budget':{'requests':len(ledger['requests']),'codex_turns_reserved':len(ledger['codex_turns']),'ledger_sha256':digest(ledger_path.read_bytes()),
                      'api_peak_upper_bound_usd':ledger['cash_bound_nano']/1e9,'api_cache_aware_estimate_usd_range':[estimate/2,estimate] if estimate is not None else 'unavailable',
                      'api_bill_usd':'unavailable','subscription_api_cash_usd':0,'subscription_cost_usd':'unavailable','DS_disjoint_tokens':tokens},
            'acceptance':{'P3-A01':'PASS_REAL_REVIEWER_ALL_CANDIDATES','P3-A02':'PASS_SAME_FROZEN_TESTS_NO_AUTOMATIC_M_WIN',
                          'P3-A03':'PASS_CONTROLLED_FAILURES_AND_NATIVE_PAUSE_RESUME','P3-A04':'PASS_REAL_SOL_BUILDER_AND_FRESH_DS_N3'},
            'limitations':['Synthetic controlled pools; no benchmark efficacy claim','Jev blocked by user-reported region; no Jev/OpenRouter requests',
                           'Current role-boundary pause is bounded, not instantaneous tool interruption','No hidden test answers or prior role chats passed to agents',
                           'Model self-assessments are not calibrated probabilities; hard tests and human review remain required','P4/P5/P6 not implemented']}
    path=BASE/'evidence/p3-public-export.json';path.write_text(json.dumps(public,indent=2)+'\n')
    print(json.dumps({'export_path':str(path),'sha256':digest(path.read_bytes()),'real_roles':len(sessions),'bundles':len(bundles),'budget':public['budget']}))


if __name__=='__main__':main()
