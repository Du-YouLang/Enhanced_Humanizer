"""Independent frozen P5 replay and session accounting; no model requests."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from wsl_project import run

CODE=r'''
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,'/opt/workbench/source')
from p1_broker import protect_memory
from p2_candidates import BASE,digest,safe_git,run_tests,validate_pool
from p3_contracts import read_json,validate_checkpoint
from p3_runtime_linux import load_stage,candidate_work
from p3_worker_linux import completed_session
from export_codex_usage import collect
protect_memory();tick=time.perf_counter();root=BASE/'runs'/sys.argv[1]
assert os.getuid()!=0
ledger=BASE/'state/p5-budget/ledger.json';before=digest(ledger.read_bytes())
prior={p:digest((BASE/'state'/(p+'-budget/ledger.json')).read_bytes()) for p in ('p1','p2','p3')}
assert prior=={'p1':'6f4d808ba13b259de0afb67e0d3f80c4c328125947c044801a7dcedcb0ed3643',
 'p2':'760385b37cd6246be664c0d33aae3eb9b351a5badfcdee02650241a111b74dea',
 'p3':'212e47dde838c7805f664d54f1ab25cf6d132e65bc81b8fb329a2ec310cdd586'}
contract=read_json(root/'control/run-contract.json');body=dict(contract);claimed=body.pop('contract_hash');assert digest(body)==claimed
resume=read_json(root/'control/resume.json');assert resume['status']=='COMPLETED' and resume['task_verdict']=='PASS'
checkpoint=validate_checkpoint(read_json(root/'control/checkpoint-7.json'),claimed);assert checkpoint['next_step']==7
for row in checkpoint['stages']:assert load_stage(root,row['name'])['record_sha256']==row['result_sha256']
for source,expected in contract['source_sha256'].items():
 path=BASE/'source'/(source.removeprefix('scripts/') if source.startswith('scripts/') else source.replace('.hmz/',''))
 assert digest(path.read_bytes())==expected
pool_path=load_stage(root,'candidates')['pool_path'];pool=validate_pool(read_json(pool_path));assert pool['contract_manifest']==contract['task_contract']
tests=[]
for c in pool['candidates']:
 work=candidate_work(pool_path,c['id']);replay=run_tests(work,independent=True,contract=pool['contract_manifest'])
 assert replay['suite_sha256']==c['test_report']['suite_sha256'] and replay['verdict']==c['test_report']['verdict']
 assert safe_git(work,'rev-parse','HEAD')==c['head_commit'] and not safe_git(work,'status','--porcelain')
 tests.append({'id':c['id'],'head_sha':c['head_commit'],'verdict':replay['verdict'],'suite_sha256':replay['suite_sha256']})
for stage,role in (('verify_m','reviewer'),('builder','builder')):
 value=load_stage(root,stage);work=root/'roles'/role/'worktree'
 replay=run_tests(work,independent=True,contract=pool['contract_manifest'])
 assert value['verdict']==replay['verdict']=='PASS' and replay['suite_sha256']==value['test_report']['suite_sha256']
 assert value['frozen_test_unchanged'] and value['independent_object_store']
 assert safe_git(work,'rev-parse','HEAD')==value['head_commit'] and not safe_git(work,'status','--porcelain')
 assert value['head_commit']!=value['base_commit']
 tests.append({'id':value['id'],'head_sha':value['head_commit'],'verdict':'PASS','suite_sha256':replay['suite_sha256']})
coverage=load_stage(root,'reviewer')['answer']['decision']['considered_candidates']
assert sorted(coverage)==sorted(c['id'] for c in pool['candidates'])
sessions=[];denials=0
for name in ('verifier_input','reviewer','verifier_m','builder','verifier_builder'):
 path=root/'roles'/name;worker=read_json(path/'worker.json')
 assert worker['status']=='COMPLETED' and worker['kind']=='REAL_MODEL_EXPERIMENT'
 assert worker['uid']!=0 and worker['cap_eff']=='0000000000000000'
 selected=completed_session(collect(Path(worker['epic'])),worker['turns'])
 assert selected['session_id']==worker['session_id'] and selected['model_id']==worker['model_id']=='gpt-6.1-sol'
 assert selected['session_id'] not in [s['session_id'] for s in sessions]
 sessions.append({'role':name,**{k:selected[k] for k in ('session_id','model_id','usage')}})
 view=read_json(root/'inputs'/(name+'.json'));assert digest(view)==worker['input_sha256']
 assert 'acceptance_test_program' not in json.dumps(view)
 isolation=read_json(path/'isolation.json');assert isolation['verdict']=='PASS'
 assert isolation['private_pid_namespace'] and all(r['read']==r['write']=='DENIED' for r in isolation['paths'])
 assert all(r['write']=='DENIED' for r in isolation['readonly'])
 denials+=2*len(isolation['paths'])+len(isolation['readonly'])
for name in ('verifier_input','verifier_m','verifier_builder'):assert load_stage(root,name)['status']=='COMPLETED'
assert load_stage(root,'verifier_builder')['eligible_selected']=='S'
segments=[read_json(p) for p in sorted((root/'control').glob('segment-*.json'))]
assert len(segments)>=2 and any(s['status']=='PAUSED' for s in segments) and segments[-1]['status']=='COMPLETED'
assert resume['active_elapsed_seconds']<=contract['settings']['experiment_seconds']
assert before==digest(ledger.read_bytes())
all_sessions={}
for path in (BASE/'runs').glob('p5-*/roles/*/humanize'):
 for row in collect(path):
  if row['session_id']!='unavailable':all_sessions[row['session_id']]={k:row[k] for k in ('session_id','model_id','usage')}
visible={k:sum(s['usage'].get(k,0) for s in all_sessions.values() if isinstance(s['usage'],dict)) for k in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')}
ledger_value=read_json(ledger)
value={'kind':'INDEPENDENT_NATIVE_ZERO_MODEL_LIVE_REPLAY','verdict':'PASS','run_id':root.name,'new_model_requests':0,
 'new_subscription_turns':0,'api_cash_usd':0,'replays':tests,'completed_sessions':sessions,
 'actual_runtime_denials':denials,'segments':segments,'checkpoint_sha256':digest(checkpoint),'contract_hash':claimed,
 'frozen_source_sha256':contract['source_sha256'],'ledger_sha256':before,'prior_ledger_sha256':prior,
 'reviewer_considered_candidates':coverage,'comparison':load_stage(root,'verifier_m')['comparison'],
 'all_p5_sessions':list(all_sessions.values()),'subscription_visible_tokens':visible,
 'subscription_unknown_sessions':sum(s['usage']=='unavailable' for s in all_sessions.values()),
 'ds_requests':len(ledger_value['requests']),'codex_turns_reserved':len(ledger_value['codex_turns']),
 'cash_upper_bound_usd':ledger_value['cash_bound_nano']/1e9,'elapsed_seconds':time.perf_counter()-tick}
print(json.dumps(value))
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run_id');args=parser.parse_args()
    if not re.fullmatch('p5-[a-z0-9-]+',args.run_id):raise ValueError('Explicit registered P5 run required')
    result=run(['python','-B','-c',CODE,args.run_id],timeout=120)
    if result.returncode:
        print(result.stderr.decode(errors='replace')[-2000:]);return result.returncode
    value=json.loads(result.stdout);target=ROOT/'.local-workbench/audits'/('p5-live-'+args.run_id+'.json')
    target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:value[k] for k in ('verdict','run_id','elapsed_seconds','ds_requests','codex_turns_reserved','cash_upper_bound_usd')}))
    return 0

if __name__=='__main__':sys.exit(main())
