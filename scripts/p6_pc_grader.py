"""PC-ALM execution/numeric gate, independent replay, and separate scientific gate."""
import csv
import hashlib
import json
from pathlib import Path
import time

from p6_output_data import bounded_json
from p6_pc_validation import validate_bundle,run_artifacts
from p6_pc_statistics import read_rows
from p6_science_sandbox import execute
from p6_science_contracts import source_identity


def grade(source,reference,prefix,official,*,timeout=7200):
    started=time.perf_counter();source,reference,prefix,official=map(Path,(source,reference,prefix,official))
    calibration=bounded_json(reference/'status.json')
    if calibration['status']!='PASS_LOCAL_CALIBRATION':raise ValueError('Local tolerance not calibrated')
    for name,sha in calibration['source_fingerprint'].items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=sha:
            return {'verdict':'FAIL','reason':'Frozen official source modified: '+name,'model_requests':0}
    input_root=official.parent.parent/'inputs'
    inputs={str(p.relative_to(input_root)):p.read_bytes() for p in input_root.rglob('*.gz')}
    provenance=source_identity(source)
    inputs['workbench-source-provenance.json']=json.dumps(provenance,sort_keys=True).encode()
    worker='''import subprocess,sys,time,json
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4]);tick=time.perf_counter()
subprocess.run([sys.executable,'-B',str(source/'run_benchmark.py'),'--data-dir',str(inputs),'--output-dir',str(output/'result')],cwd=source,check=True,timeout=6800)
(output/'controller.json').write_text(json.dumps({'wall_seconds':time.perf_counter()-tick}))
'''
    result={'verdict':'FAIL','model_requests':0,'source_and_report_review':'REQUIRED_FOR_EXECUTION_FIDELITY',
            'trusted_source_provenance':provenance}
    execution=execute(source,prefix,worker,inputs=inputs,timeout=timeout-360,gpu=True,rss_limit_mib=10240,cpu_threads=8)
    result['execution']=execution
    if execution['status']!='COMPLETED_UNGRADED':return result
    root=Path(execution['output'])/'result'
    try:
        with (official/'configs/eta_best_by_cell.csv').open() as stream:
            eta={(int(r['N']),int(r['L'])):float(r['eta_best_1_over_lambda_median']) for r in csv.DictReader(stream) if r['dataset']=='fashion_mnist' and r['activation']=='relu'}
        checked=validate_bundle(root,eta,{'C1':.04,'C2':.10,'C3':.10,'C4':.05,'C5':.15},source=source)
        manifest=checked['manifest_checked']
        if manifest['data_sha256']!=calibration['data_fingerprint']:raise ValueError('Input data manifest differs from frozen files')
        actual=read_rows(root/'grid/cells.csv');gold=read_rows(reference/'reference/grid/cells.csv')
        gold={(r['width'],r['depth'],r['method']):r for r in gold}
        deltas=[]
        for row in actual:
            prior=gold[row['width'],row['depth'],row['method']]
            a=100*abs(row['final_test_acc']-prior['final_test_acc']);c=abs(row['grad_cos_to_bp']-prior['grad_cos_to_bp'])
            if a>.25 or c>.02:raise ValueError('Frozen same-environment cell tolerance exceeded')
            deltas.append({'width':row['width'],'depth':row['depth'],'method':row['method'],'accuracy_delta_pp':a,'cosine_delta':c})
        report=root/'REPORT.md'
        if not report.is_file() or not 250<=report.stat().st_size<=100000:raise ValueError('Scientific report missing/oversized')
        # Stable full program identity selects the replay cells before their result
        # is known. The private controller invokes the unchanged official trainer.
        identity=hashlib.sha256()
        for file in sorted(source.rglob('*')):
            if file.is_file() and '.git' not in file.parts:
                identity.update(str(file.relative_to(source)).encode()+b'\0'+file.read_bytes())
        keys=sorted(gold);number=int(identity.hexdigest(),16);selected=[keys[number%len(keys)],keys[(number//len(keys))%len(keys)]]
        if selected[0]==selected[1]:selected[1]=keys[(keys.index(selected[0])+1)%len(keys)]
        worker='''import csv,json,subprocess,sys,time
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4]);cells=CELLS
with (source/'configs/eta_best_by_cell.csv').open() as f:
 eta={(int(r['N']),int(r['L'])):r['eta_best_1_over_lambda_median'] for r in csv.DictReader(f) if r['dataset']=='fashion_mnist' and r['activation']=='relu'}
for w,d,m in cells:
 target=output/f'fashion_mnist_relu_n{w}_l{d}_seed0_{m}'
 subprocess.run([sys.executable,'-B','train.py','--config','configs/headline_fashion.yaml','--width',str(w),'--depth',str(d),'--seed','0','--method',m,'--budget',str(0 if m=='bp' else 2*d),'--state-lr',eta[w,d],'--output-dir',str(target),'--data-dir',str(inputs)],cwd=source,check=True,timeout=600)
'''.replace('CELLS',repr(selected))
        remaining=int(timeout-(time.perf_counter()-started))-5
        if remaining<1:raise ValueError('No time left for independent replay')
        replay=execute(source,prefix,worker,inputs=inputs,timeout=remaining,gpu=True,rss_limit_mib=10240,cpu_threads=8)
        result['independent_replay']=replay
        if replay['status']!='COMPLETED_UNGRADED':raise ValueError('Independent two-cell replay failed')
        by_key={(r['width'],r['depth'],r['method']):r for r in actual}
        for w,d,m in selected:
            folder=Path(replay['output'])/f'fashion_mnist_relu_n{w}_l{d}_seed0_{m}'
            r=bounded_json(folder/'summary.json');run_artifacts(folder,r,eta);prior=by_key[w,d,m]
            if 100*abs(r['final_test_acc']-prior['final_test_acc'])>.25 or abs(r['grad_cos_to_bp']-prior['grad_cos_to_bp'])>.02:
                raise ValueError('Independent replay disagrees with submitted cell')
        result.update(verdict='PASS_NUMERIC_REVIEW_PENDING',implementation_fidelity='ARTIFACTS_AND_ANCHORS_AND_LOCAL_REFERENCE_AND_TWO_CELL_REPLAY_PASS',
                      scientific_claim_supported=checked['science_gate']['claim_supported'],science_gate=checked['science_gate'],
                      statistics=checked['statistics'],cell_deltas=deltas,replay_cells=selected,program_sha256=identity.hexdigest(),
                      elapsed_seconds=time.perf_counter()-started)
    except (ValueError,KeyError,TypeError,OSError) as error:
        result.update(error_type=type(error).__name__,reason=str(error)[:500])
    return result
