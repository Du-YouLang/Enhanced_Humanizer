"""Scoped numerical supplementation of frozen A-F programs; no model dispatch.

Original matrices, program trees and owner oracle files are read-only. The only
new executions are three EGL measured reruns and six STROKE repeat/rejection sets.
"""
import fcntl
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

if os.name=='posix':
    sys.path[:0]=[str(Path(__file__).parent),'/opt/workbench/source','/opt/workbench/source/src',
                  '/opt/workbench/benchmark/envs/science-tms-v1/lib/python3.12/site-packages']

from p6_output_data import bounded_json,bounded_npz
from p6_science_sandbox import execute
from p6_tms_legacy_contract import canonical_views

PROTOCOL='AF_NINE_FROZEN_PROGRAM_SUPPLEMENT_20261016_V1'
ORDER=('EGL-A','EGL-B','EGL-E','STROKE-A','STROKE-B','STROKE-C','STROKE-D','STROKE-E','STROKE-F')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return bounded_json(Path(path))
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def exclusive(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())


def inventory(source):
    source=Path(source)
    return {str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*'))
            if p.is_file() and not any(k in ('.git','__pycache__') for k in p.relative_to(source).parts) and p.suffix!='.pyc'}


def verify(plan):
    body=dict(plan);expected=body.pop('plan_sha256')
    if (digest(body)!=expected or plan['protocol']!=PROTOCOL or list(plan['cases'])!=list(ORDER)
            or plan['model_calls_authorized']!=0 or plan['maximum_seconds']!=10800):
        raise ValueError('Exact nine-case zero-model scope required')
    for path,h in {**plan['source_pins'],**plan['retained_pins']}.items():
        if sha(path)!=h:raise ValueError('Frozen evidence or evaluator changed: '+path)
    for row in plan['cases'].values():
        if inventory(row['source'])!=row['source_inventory']:raise ValueError('Original source inventory changed')
    # Pi legitimately appends/settles its own requests concurrently. Only the
    # immutable, closed prefix is compared, never a moving in-flight snapshot.
    # These are trusted controller-owned ledgers, not candidate JSON output.
    # Their legitimate multi-thousand-request history exceeds the output cap.
    old=json.loads(Path(plan['ledger_archive']).read_bytes())
    current=json.loads(Path(plan['ledger_path']).read_bytes())
    if (current['requests'][:len(old['requests'])]!=old['requests']
            or current['codex_turns'][:len(old['codex_turns'])]!=old['codex_turns']):
        raise ValueError('Original cumulative ledger prefix changed')


def stage(root,name,action):
    start=root/'state'/(name+'.started.json');done=root/'state'/(name+'.completed.json')
    if done.exists():
        row=read(done)
        if row['stage']!=name or digest(row['value'])!=row['value_sha256']:raise ValueError('Completed scientific journal changed')
        return row['value']
    if start.exists():raise RuntimeError('Uncertain scientific execution requires reconciliation: '+name)
    exclusive(start,{'stage':name,'started_unix':time.time(),'model_calls':0,'automatic_replay':False})
    tick=time.perf_counter();value=action();value['supplement_stage_seconds']=time.perf_counter()-tick
    exclusive(done,{'stage':name,'value':value,'value_sha256':digest(value)})
    print(json.dumps({'stage':name,'status':value['status'],'seconds':value['supplement_stage_seconds']}),flush=True)
    return value


def load_owner(plan):
    owner=Path(plan['stroke_root'])/'judge_private';sys.path.insert(0,str(owner))
    try:
        spec=importlib.util.spec_from_file_location('af_owner_stroke_judge_v3',owner/'judge.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    finally:sys.path.remove(str(owner))


def compare_existing(judge,actual,gold):
    actual,gold=Path(actual),Path(gold)
    bounded_npz(actual/'arrays.npz');bounded_npz(gold/'arrays.npz')
    a,r,changes=canonical_views(read(actual/'metrics.json'),read(gold/'metrics.json'))
    original=judge.read_json
    def view(path):
        p=Path(path)
        if p==actual/'metrics.json':return a
        if p==gold/'metrics.json':return r
        return original(path)
    # Only the parent's immutable JSON views vary. Arrays, original files and
    # every tolerance/type/shape/mask check remain with the original owner judge.
    with patch.object(judge,'read_json',new=view):judge.compare_output(actual,gold)
    return changes


def egl_case(plan,case):
    from p6_egl_grader import grade
    result=grade(case['source'],plan['egl_reference'],plan['egl_prefix'],timeout=1800)
    out=Path(result['execution']['output'])/'result'
    completed=sum((out/f'N{n}/seed{s}/{alg}/metrics.json').is_file() for n in (200,2000,20000) for s in (1,2,3) for alg in ('eg','gd'))
    status=result['verdict'] if result['execution']['status']=='COMPLETED_UNGRADED' else 'INDETERMINATE_EVALUATION_INFRASTRUCTURE'
    return {'status':status,'detail':result,'original_arm':case['arm'],
            'original_program_sha256':case['program_identity'],'new_full_training_runs_completed':completed,
            'old_training_telemetry':'UNAVAILABLE_NOT_BACKFILLED','model_calls':0,
            'timing_policy':'NEW_MEASURED_SUPPLEMENT_NOT_HISTORICAL_END_TO_END'}


def stroke_case(root,plan,case):
    import numpy as np
    judge=load_owner(plan);base=Path(plan['stroke_root']);index=read(base/'judge_private/case_index.json')
    prior=case['original_acceptance']['acceptance']['detail'];retained={};comparisons=[]
    for outcome,execution in zip(prior['numeric']['outcomes'],prior['executions']):
        if outcome['kind']!='numeric':continue
        key=outcome['case'];retained[key]=Path(execution['output'])/'result'
    if set(retained)!=set(index):raise ValueError('Exactly the original14 numeric outputs required')
    for key,spec in index.items():
        try:
            views=compare_existing(judge,retained[key],base/spec['gold'])
            comparisons.append({'case':key,'pass':True,'representation_changes':views})
        except (AssertionError,ValueError,KeyError,TypeError) as error:
            comparisons.append({'case':key,'pass':False,'reason':str(error)[:700]})
    tick=time.perf_counter();executions=[]
    from p6_tms_grader import WORKER
    def call(inp,profile,allow):
        remaining=600-(time.perf_counter()-tick)
        if remaining<2:raise TimeoutError('STROKE supplemental600-second deadline')
        execution=execute(case['source'],plan['stroke_prefix'],WORKER,
                          inputs={'input.npz':inp,'profile.json':profile},arguments=('true' if allow else 'false',),
                          timeout=min(180,int(remaining)),rss_limit_mib=4096,cpu_threads=1,pin_one_cpu=True,python_hash_seed=0)
        executions.append(execution);return execution,Path(execution['output'])/'result'
    first=next(k for k,spec in index.items() if spec['public'])
    spec=index[first]
    repeat,actual=call((base/spec['input']).read_bytes(),(base/spec['profile']).read_bytes(),spec['allow_unreviewed'])
    repeat_ok=False;repeat_error=None
    try:
        if repeat['status']!='COMPLETED_UNGRADED':raise AssertionError('Repeat process did not complete')
        judge.compare_output(actual,retained[first])
        if read(actual/'metrics.json')!=read(retained[first]/'metrics.json'):raise AssertionError('Repeated JSON values differ')
        aa=bounded_npz(actual/'arrays.npz');bb=bounded_npz(retained[first]/'arrays.npz')
        if any(not np.array_equal(aa[k],bb[k],equal_nan=True) for k in judge.ARRAY_UNITS):raise AssertionError('Repeat arrays differ exactly')
        repeat_ok=True
    except (AssertionError,ValueError,KeyError,TypeError,OSError) as error:repeat_error=str(error)[:700]
    original_npz=bounded_npz(base/'agent_public/inputs/toy_complex.npz')
    negatives=[]
    labels=('bad_unit','nan_data','missing_roi','bad_time_grid','single_trial','unreviewed_without_opt_in',
            'artifact_reviewed_string_false','artifact_reviewed_numeric_zero','artifact_reviewed_missing',
            'synthetic_string_false','synthetic_numeric_zero','synthetic_missing')
    for label in labels:
        values={k:v.copy() for k,v in original_npz.items()};profile=base/'agent_public/profiles/toy_2024.json'
        if label=='bad_unit':values['unit']=np.array('mV')
        elif label=='nan_data':values['data'].flat[0]=np.nan
        elif label=='missing_roi':values['ch_names'][0]='NO_SUCH_CHANNEL'
        elif label=='bad_time_grid':values['times']*=1000
        elif label=='single_trial':values['data']=values['data'][:1]
        elif label=='unreviewed_without_opt_in':
            values=bounded_npz(base/'agent_public/inputs/healthy_m1_mini.npz');profile=base/'agent_public/profiles/healthy_2024.json'
        else:
            metadata=json.loads(str(values['metadata_json'].item()))
            key='artifact_reviewed' if label.startswith('artifact_reviewed') else 'synthetic'
            if label.endswith('missing'):metadata.pop(key,None)
            elif label.endswith('numeric_zero'):metadata[key]=0
            else:metadata[key]='false'
            values['metadata_json']=np.array(json.dumps(metadata))
        stream=io.BytesIO();np.savez_compressed(stream,**values)
        execution,output=call(stream.getvalue(),profile.read_bytes(),False)
        good=(execution['status']=='SUBMISSION_FAILED' and execution['exit_code']!=0 and not (output/'metrics.json').exists())
        negatives.append({'case':label,'pass':good,'kind':'original_six' if label in labels[:6] else 'explicit_boolean_schema',
                          'execution':execution,'successful_metrics_left':(output/'metrics.json').exists()})
    # Trusted public renderer, not candidate code; only retained arrays from
    # numeric cases accepted under the explicitly frozen comparison are plotted.
    renderer=base/'agent_public/render_figure.py'
    spec=importlib.util.spec_from_file_location('owner_public_stroke_renderer',renderer)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    figures=[]
    for item in comparisons:
        key=item['case'];spec=index[key]
        if not item['pass'] or not spec['public']:continue
        image=root/'figures'/('STROKE-'+case['arm'])/(key+'.png');image.parent.mkdir(parents=True,exist_ok=True)
        module.render(retained[key]/'arrays.npz',base/spec['profile'],image)
        figures.append({'case':key,'path':str(image),'sha256':sha(image),'arrays_sha256':sha(retained[key]/'arrays.npz'),
                        'profile_sha256':sha(base/spec['profile']),'renderer_sha256':sha(renderer)})
    numeric_ok=all(r['pass'] for r in comparisons);negative_ok=all(r['pass'] for r in negatives)
    status=('FAIL_NUMERIC' if not numeric_ok else 'FAIL_REPEATABILITY' if not repeat_ok else
            'FAIL_INPUT_CONTRACT' if not negative_ok else 'PASS_CHECKS_SOURCE_REPORT_FIGURE_REVIEW_PENDING')
    return {'status':status,'original_arm':case['arm'],'original_program_sha256':case['program_identity'],
            'retained_numeric':comparisons,'new_numeric_main_replays':0,
            'repeat':{'pass':repeat_ok,'error':repeat_error,'execution':repeat},'negative_checks':negatives,
            'figures':figures,'executions':executions,'supplement_wall_seconds':time.perf_counter()-tick,
            'source_report_figure_review':'PENDING_SOL','model_calls':0,'clinical_validity':'NOT_ASSESSED'}


def run(root):
    from p6_prepare_linux import BASE
    root=Path(root).resolve()
    if not root.is_relative_to(BASE/'science/private'):raise ValueError('Private local scientific root required')
    if os.getuid()==0:raise ValueError('Native non-root only')
    plan=read(root/'plan.json');verify(plan)
    control=read(root/'controls-receipt.json')
    if (control.get('status')!='PASS_AF_NINE_ACTUAL_ZERO_MODEL_CONTROLS'
            or control.get('plan_sha256')!=plan['plan_sha256'] or control.get('source_pins')!=plan['source_pins']
            or control.get('model_calls')!=0 or not all(c['pass'] for c in control['controls'])):
        raise ValueError('Actual exact-source zero-model controls must pass before any original-program execution')
    with (root/'owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'receipt.json').exists():raise ValueError('Closed scientific supplement cannot replay')
        started=time.perf_counter();results={}
        for name in ORDER:
            if time.perf_counter()-started>plan['maximum_seconds']:raise TimeoutError('Finite supplement deadline')
            case=plan['cases'][name]
            results[name]=stage(root,name,lambda n=name,c=case:egl_case(plan,c) if n.startswith('EGL-') else stroke_case(root,plan,c))
            verify(plan)
        receipt={'status':'NINE_NUMERICAL_SUPPLEMENTS_CLOSED_SOL_REVIEW_REQUIRED','results':results,
                 'model_calls':0,'candidate_code_edits':0,'old_results_overwritten':0,
                 'new_egl_training_runs_completed':sum(v.get('new_full_training_runs_completed',0) for v in results.values()),
                 'new_stroke_numeric_main_replays':0,
                 'elapsed_seconds':time.perf_counter()-started,'plan_sha256':plan['plan_sha256'],
                 'original_ledger_prefix_preserved':True,'external_release_authorized':False}
        exclusive(root/'receipt.json',receipt)
        print(json.dumps({'status':receipt['status'],'receipt_sha256':sha(root/'receipt.json')}),flush=True)


if __name__=='__main__':run(sys.argv[1])
