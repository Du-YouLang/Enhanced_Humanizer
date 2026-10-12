"""Controlled, zero-model PC-ALM recovery and same-environment calibration.

The original attempt is immutable. Recovery trains only its missing cells in
the existing scientific fence; the assembled reference records every origin.
The supplied owner repeat script runs unchanged, in three separate processes.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
import traceback

from p6_pc_validation import validate_grid
from p6_science_sandbox import execute

ROOT = Path('/opt/workbench/benchmark/science')
SOURCE = ROOT/'intake/pc-alm/agent_public/upstream'
PREFIX = Path('/opt/workbench/benchmark/envs/science-pc-alm-v1')
CELLS = ((8,16),(8,128),(32,32),(64,64))
METHODS = ('bp','pc','pcalm')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)):digest(p) for p in sorted(Path(root).rglob('*')) if p.is_file()}


def write_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


def repeat_statistics(groups, reference):
    """Exact configuration/repetition coverage; accuracy deltas are in pp."""
    expected = {(w,d,m) for w,d in CELLS for m in METHODS}
    refs = {(int(r['width']),int(r['depth']),r['method']):r for r in reference}
    samples = {}
    for label, repeats, rows in groups:
        seen = set()
        for r in rows:
            key = (int(r['width']),int(r['depth']),r['method'])
            rep = int(r['repeat']); identity = (*key,rep)
            if key not in expected or not 0 <= rep < repeats or identity in seen:
                raise ValueError('Duplicate or undeclared repeat configuration')
            a,c = float(r['test_acc']),float(r['grad_cos'])
            if not math.isfinite(a) or not math.isfinite(c) or not 0 <= a <= 1 or not -1.000001 <= c <= 1.000001:
                raise ValueError('Invalid repeat measurement')
            seen.add(identity);samples.setdefault(key,[]).append((label,rep,a,c))
        if seen != {(*k,r) for k in expected for r in range(repeats)}:
            raise ValueError('Incomplete repeat coverage')
    if [(label,reps) for label,reps,_ in groups] != [('same-process',3),('cross-process-1',1),('cross-process-2',1)]:
        raise ValueError('The predeclared three-process protocol is required')
    details=[]
    for key in sorted(expected):
        values=samples[key];same=[v for v in values if v[0]=='same-process']
        a=[v[2] for v in values];c=[v[3] for v in values];r=refs[key]
        details.append({'width':key[0],'depth':key[1],'method':key[2],
                        'same_process_accuracy_spread_pp':100*(max(v[2] for v in same)-min(v[2] for v in same)),
                        'same_process_cosine_spread':max(v[3] for v in same)-min(v[3] for v in same),
                        'all_process_accuracy_spread_pp':100*(max(a)-min(a)),
                        'all_process_cosine_spread':max(c)-min(c),
                        'max_reference_accuracy_delta_pp':100*max(abs(v-float(r['final_test_acc'])) for v in a),
                        'max_reference_cosine_delta':max(abs(v-float(r['grad_cos_to_bp'])) for v in c)})
    maximum=lambda name:max(r[name] for r in details)
    acc=max(maximum('all_process_accuracy_spread_pp'),maximum('max_reference_accuracy_delta_pp'))
    cosine=max(maximum('all_process_cosine_spread'),maximum('max_reference_cosine_delta'))
    passed=acc <= .25 and cosine <= .02
    return {'status':'PASS_LOCAL_CALIBRATION' if passed else 'FAIL_LOCAL_CALIBRATION',
            'configurations':12,'training_runs':60,'details':details,
            'max_accuracy_delta_pp':acc,'max_cosine_delta':cosine,
            'accuracy_tolerance_pp':.25,'cosine_tolerance':.02,
            'tolerances_frozen_before_candidate_generation':passed,
            'scope':'SAMPLED_SAME_ENVIRONMENT_NOT_UNIVERSAL_HARDWARE_GUARANTEE',
            'model_requests':0,'api_cash_usd':0,'tokens':'not_applicable'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-output',required=True)
    parser.add_argument('--owner-repeat',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    old=Path(args.previous_output).resolve();out=Path(args.out).resolve();owner=Path(args.owner_repeat).resolve()
    private=ROOT/'private'
    if not all(p.is_relative_to(private) for p in (old,out,owner)) or out.exists():
        raise ValueError('Use a new private project output directory')
    out.mkdir(parents=True)
    started=time.perf_counter()
    state={'status':'RUNNING','pid':os.getpid(),'model_requests':0,'started_unix':time.time(),
           'previous_output':str(old),'old_fingerprint':inventory(old),
           'source_fingerprint':inventory(SOURCE),'data_fingerprint':inventory(ROOT/'intake/pc-alm/inputs'),
           'owner_repeat_sha256':digest(owner),'controller_sha256':digest(__file__),
           'interrupted_attempt_cause':'UNESTABLISHED_NO_EXIT_RECEIPT',
           'maximum_compute_seconds':6300,'automatic_model_continuation':False}
    write_json(out/'status.json',state)
    try:
        with (old/'cells.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
        seen={(int(r['width']),int(r['depth']),r['method']) for r in rows}
        expected={(w,d,m) for w in (8,16,32,64,128) for d in (8,16,32,64,128) for m in METHODS}
        if len(seen)!=len(rows) or seen-expected:raise ValueError('Invalid previous grid')
        missing=sorted(expected-seen)
        if missing != [(128,128,'pcalm')]:raise ValueError('Recovery is approved only for the observed single missing cell')
        inputs={str(p.relative_to(ROOT/'intake/pc-alm/inputs')):p.read_bytes() for p in (ROOT/'intake/pc-alm/inputs').rglob('*.gz')}
        worker='''import csv,json,os,subprocess,sys,time
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4]);os.chdir(source)
with (source/'configs/eta_best_by_cell.csv').open() as f:
 eta=next(r['eta_best_1_over_lambda_median'] for r in csv.DictReader(f) if r['dataset']=='fashion_mnist' and r['activation']=='relu' and int(r['N'])==128 and int(r['L'])==128)
target=output/'fashion_mnist_relu_n128_l128_seed0_pcalm';tick=time.perf_counter()
with (output/'training.log').open('wb') as log:
 subprocess.run([sys.executable,'-B','train.py','--config','configs/headline_fashion.yaml','--width','128','--depth','128','--seed','0','--method','pcalm','--budget','256','--state-lr',eta,'--output-dir',str(target),'--data-dir',str(inputs)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
print(json.dumps({'completed':1,'wall_seconds':time.perf_counter()-tick}),flush=True)
'''
        recovery=execute(SOURCE,PREFIX,worker,inputs=inputs,timeout=630,gpu=True,rss_limit_mib=10240,cpu_threads=8)
        state['recovery']=recovery;write_json(out/'status.json',state)
        if recovery['status']!='COMPLETED_UNGRADED':raise RuntimeError('Recovery did not complete')
        grid=out/'reference/grid';grid.mkdir(parents=True)
        origins={}
        for r in rows:
            name=f"fashion_mnist_relu_n{r['width']}_l{r['depth']}_seed0_{r['method']}"
            shutil.copytree(old/name,grid/name);origins[name]=str(old/name)
        name='fashion_mnist_relu_n128_l128_seed0_pcalm'
        fresh=Path(recovery['output'])/name;shutil.copytree(fresh,grid/name);origins[name]=str(fresh)
        rows.append(json.loads((fresh/'summary.json').read_text()))
        with (grid/'cells.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        with (SOURCE/'configs/eta_best_by_cell.csv').open() as stream:
            eta={(int(r['N']),int(r['L'])):float(r['eta_best_1_over_lambda_median']) for r in csv.DictReader(stream) if r['dataset']=='fashion_mnist' and r['activation']=='relu'}
        state['reference_statistics']=validate_grid(grid,eta)
        write_json(out/'reference/origins.json',origins)
        # Preserve the owner's program byte-for-byte; execute it only in the fence.
        repeat_worker='''import json,subprocess,sys,time
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4])
owner=output/'owner_repeat_check.py';owner.write_text(OWNER_CODE)
receipts=[]
for label,repeats in [('same-process',3),('cross-process-1',1),('cross-process-2',1)]:
 tick=time.perf_counter()
 with (output/(label+'.log')).open('wb') as log:
  subprocess.run([sys.executable,'-B',str(owner),'--repo',str(source),'--data-dir',str(inputs),'--out-dir',str(output/label),'--repeats',str(repeats)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
 receipts.append({'mode':label,'wall_seconds':time.perf_counter()-tick,'repeats':repeats,'configs':12})
 (output/'repeat-protocol.json').write_text(json.dumps(receipts,indent=2))
 print(json.dumps(receipts[-1]),flush=True)
'''.replace('OWNER_CODE',repr(owner.read_text()))
        state['stage']='REPEAT_CALIBRATION';write_json(out/'status.json',state)
        repeat=execute(SOURCE,PREFIX,repeat_worker,inputs=inputs,timeout=5400,gpu=True,rss_limit_mib=10240,cpu_threads=8)
        state['repeat_execution']=repeat;write_json(out/'status.json',state)
        if repeat['status']!='COMPLETED_UNGRADED':raise RuntimeError('Repeat calibration did not complete')
        groups=[]
        for label,reps in [('same-process',3),('cross-process-1',1),('cross-process-2',1)]:
            with (Path(repeat['output'])/label/'repeat_runs.csv').open(newline='') as stream:
                groups.append((label,reps,list(csv.DictReader(stream))))
        state['calibration']=repeat_statistics(groups,rows)
        state['old_artifacts_unchanged']=inventory(old)==state['old_fingerprint']
        state['source_and_data_unchanged']=(inventory(SOURCE)==state['source_fingerprint'] and inventory(ROOT/'intake/pc-alm/inputs')==state['data_fingerprint'])
        if not state['old_artifacts_unchanged'] or not state['source_and_data_unchanged']:
            raise RuntimeError('Frozen input or historical result changed')
        state['status']=state['calibration']['status']
        state['formal_model_benchmark']='NOT_RUN_BY_THIS_CONTROLLER'
        state['reference_fingerprint']=inventory(out/'reference')
    except BaseException:
        state['status']='FAILED_PRESERVED';state['error']=traceback.format_exc()
        raise
    finally:
        state['elapsed_seconds']=time.perf_counter()-started;state['finished_unix']=time.time()
        write_json(out/'status.json',state)


if __name__=='__main__':main()
