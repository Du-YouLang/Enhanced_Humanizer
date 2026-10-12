"""Freeze the new main manifest only after actual local per-task controls pass."""
import hashlib
import argparse
import json
from pathlib import Path
import sys

from wsl_project import ROOT,run
sys.path.insert(0,str(ROOT/'src'))
from workbench.benchmark import freeze_manifest

COLLECT=r'''import json,hashlib
from pathlib import Path
b=Path('/opt/workbench/benchmark/science');private=b/'private'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(p):
 return {str(f.relative_to(p)):sha(f) for f in sorted(p.rglob('*')) if f.is_file() and '.git' not in f.parts and '__pycache__' not in f.parts}
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
paths={
 'SCI-PC-ALM':['pc-submission-controls-v1/positive.json','pc-submission-controls-v1/negative.json'],
 'SCI-STROKE':['tms-production-adapter-control-v2.json','tms-local-controls-v1/negative-wrong-lmfp.json'],
 'SCI-EGL':['egl-positive-v3-control-v2.json','egl-negative-sign-v1-control.json'],
 'SCI-GRANGER-GPU':['gc-local-controls-v1/positive.json','gc-local-controls-v1/negative-wrong-number.json','gc-local-controls-v1/negative-cpu-download.json']}
roots={
 'SCI-PC-ALM':(b/'intake/pc-alm/inputs',private/'pc-calibration-20261012-v1'),
 'SCI-STROKE':(b/'intake/tms/judge_private/inputs',b/'intake/tms/judge_private'),
 'SCI-EGL':(b/'intake/egl/agent_public',private/'egl-reference-local-v2'),
 'SCI-GRANGER-GPU':(b/'intake/gc/judge_private/inputs',b/'intake/gc/judge_private')}
tasks={}
for tid,names in paths.items():
 receipts={}
 for index,name in enumerate(names):
  p=private/name;v=json.loads(p.read_text())
  verdict=v.get('verdict')
  if verdict is None and type(v.get('all_passed')) is bool:verdict='PASS' if v['all_passed'] else 'FAIL'
  if index==0 and verdict not in ('PASS','PASS_NUMERIC_REVIEW_PENDING'):raise RuntimeError('Positive control not passed: '+tid)
  if index>0 and verdict=='PASS_NUMERIC_REVIEW_PENDING':raise RuntimeError('Negative control unexpectedly passed: '+tid)
  if index>0 and verdict=='PASS':raise RuntimeError('Negative control unexpectedly passed: '+tid)
  # The GC CPU-download AST refusal has a different envelope; preserve it.
  if index>0 and verdict is None and not (v.get('status') in ('REFUSED','REJECTED') or v.get('error_type')):raise RuntimeError('Unknown negative control: '+tid)
  receipts[name]={'sha256':sha(p),'verdict':verdict or v.get('status') or v.get('error_type')}
 prep=private/'main-science-preparation-v1'/(tid+'.json');r=json.loads(prep.read_text())
 data,gold=roots[tid];di=inventory(data);gi=inventory(gold)
 if not di or not gi:raise RuntimeError('Empty material inventory: '+tid)
 data_contract={'frozen_input_inventory_sha256':digest(di)}
 if tid=='SCI-EGL':
  data_contract={'public_material_sha256':digest(di),'independent_generator_sha256':sha(Path('/opt/workbench/source/p6_egl_replay.py')),
   'synthetic_protocol':{'n':[200,2000,20000],'k':100,'r':50,'seeds':[1,2,3],'train':10000,'validation':1000,'test':1000,'precision':'float32'}}
 tasks[tid]={'base_commit':r['base_commit'],'data_sha256':digest(data_contract),'data_contract':data_contract,'gold_sha256':digest(gi),
  'public_material_sha256':digest(r['public_fingerprint']),'control_receipts':receipts,'preparation_receipt_sha256':sha(prep),
  'environment_sha256':r['environment']['env_sha256']}
public=private/'public-main-controls-frozen-v2.json';v=json.loads(public.read_text())
for r in v['tasks']:
 p=Path(r['receipt']);d=json.loads(p.read_text())
 if sha(p)!=r['receipt_sha256'] or d['results']['buggy']['verdict']!='FAIL' or d['results']['gold']['verdict']!='PASS':raise RuntimeError('Public controls invalid')
print(json.dumps({'scientific':tasks,'public_controls_sha256':sha(public)}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--version',type=int,default=5)
    args=parser.parse_args()
    if args.version not in (3,4,5):raise ValueError('Explicit supported new protocol required')
    result=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',COLLECT],timeout=60)
    if result.returncode:
        raise RuntimeError('Main freeze blocked by local controls: '+result.stderr.decode(errors='replace')[-1000:])
    proof=json.loads(result.stdout)
    from run_p6_main import deploy
    runner=deploy()
    body=json.loads((ROOT/'configs/benchmark-p6-v2.json').read_text());body.pop('manifest_sha256')
    body.update(protocol_version=args.version,common_generation_timeout_seconds=115,
                generation_scope='One actual outer/Harness role turn; no 600s DS-only allowance',
                private_acceptance_policy='Freeze all selections first; separate finite independent acceptance and substantive science review',
                full_tool_trace_policy='Separate metered same-program review; complete calls/results or refuse; explicitly different evidence hash',
                public_controls_sha256=proof['public_controls_sha256'],compute_policy='LOCAL_ONLY_CPU_PROTOCOLS_PRESERVED_GPU_TASKS_SINGLE_LOCAL_GPU',
                runner_source_sha256=runner,entrypoint_sha256=hashlib.sha256((ROOT/'scripts/run_p6_main.py').read_bytes()).hexdigest())
    if args.version>=4:
        body['operational_cap_policy']='Trusted local role-request-cap exhaustion is BUDGET_EXHAUSTED/arm FAIL, not infrastructure; no upstream HTTP-code inference or retry. Caps unchanged. Preserve first v3 attempt separately.'
    config=json.loads((ROOT/('configs/budget-p6-main-v2-approved.json' if args.version>=5 else 'configs/budget-p6-main-approved.json')).read_text())
    if args.version>=5:
        from p6_main_budget import authorization
        body.update(budget_authorization_sha256=authorization(config)[1],
                    aggregate_api_requests=10000,aggregate_api_cash_usd=100,per_role_api_requests=100,
                    operational_output_policy='Structured native DSH max-tokens terminal proof is OUTPUT_LIMIT/arm FAIL; retain original error and trace hash; no automatic retry')
    descriptions={
        'SCI-PC-ALM':('SakanaAI PC-ALM official frozen implementation and owner v1.1 task',
            {'accuracy_pp':.25,'gradient_cosine_abs':.02},
            ['official_source_unchanged','smoke_and_public_anchor','exact_75_native_artifacts','fixed_four_deep_narrow_cells','same_environment_reference','independent_two_cell_replay','science_C1_C5_separate']),
        'SCI-STROKE':('Tscherpel et al. sensor-level TMS-EEG numerical protocols, 2020/2024 owner task',
            {'policy':'Owner-frozen per-field tolerances in exact private judge inventory; no relaxation'},
            ['14_numeric_cases','7_boundary_cases','single_cpu_protocol','healthy_or_synthetic_not_clinical_claim']),
        'SCI-EGL':('Cornford et al. Exponentiated gradient learning; Figure4B r-of-k; owner A1',
            {'curve_rmse_pp':1.,'per_seed_endpoint_pp':1.,'group_mean_pp':.5,'optimizer_float32':2e-6,'optimizer_float64':1e-12},
            ['18_frozen_CPU_runs','signed_optimizer_50_probes','optimizer_training_use','18_saved_weight_replays','31_curve_points','mean_sample_ddof1','source_report_figure_review','local_v2_reference_old_remote_mismatch_preserved']),
        'SCI-GRANGER-GPU':('Owner-frozen ridge target-equation Granger Causality CPU-to-CuPy port',
            {'absolute':1e-7,'relative':1e-5},
            ['27_numeric_cases','13_invalid_cases','10_repeat_outputs','rawkernel_used','no_CPU_download','3_warmups_5_timed_runs','local_GPU_performance_not_biology_claim'])}
    for task in body['tasks']:
        task['preparation_status']='READY'
        if task['family']=='scientific':
            tid=task['task_id'];paper,tolerances,invariants=descriptions[tid]
            task.update(proof['scientific'][tid],paper=paper,tolerances=tolerances,invariants=invariants,
                        license='Private authorized local evaluation; retain source notices; no research-material redistribution',
                        independent_evaluation_timeout_seconds=config['scientific_evaluation_timeout_seconds'][tid])
    path=ROOT/('configs/benchmark-p6-v'+str(args.version)+'.json');frozen=freeze_manifest(body,path)
    (ROOT/('.local-workbench/audits/p6-main-frozen-controls-v'+str(args.version)+'.private.json')).write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps({'status':'FROZEN','manifest_sha256':frozen['manifest_sha256'],'tasks':16,'planned_arms':96,'model_requests':0}))


if __name__=='__main__':main()
