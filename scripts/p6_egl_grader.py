"""Independent EGL optimizer, configuration, curves, weights and statistics checks."""
import csv
import hashlib
import io
import json
from pathlib import Path
import statistics
import struct
import time

from p6_output_data import bounded_json,bounded_npy,bounded_npz
from p6_science_sandbox import execute
from p6_science_contracts import alias,egl_manifest,egl_summary


def grade(source,reference,prefix,*,timeout=1800,retained_execution=None,retained_replay=None,reviewed_manifest_units=None):
    import numpy as np
    from p6_prepare_linux import BASE
    if type(timeout) is not int or not 30<=timeout<=1800:raise ValueError('Finite total EGL evaluation deadline required')
    started=time.perf_counter()
    source,reference,prefix=map(Path,(source,reference,prefix))
    if reviewed_manifest_units and retained_execution is None:raise ValueError('Legacy unit review is only for retained historical artifacts')
    rng=np.random.default_rng(20261011);probes=[];data={};expected={}
    for dtype in (np.float32,np.float64):
        for index in range(25):
            number=len(probes);weight=rng.normal(size=17).astype(dtype);weight[:3]=(-1,0,1)
            gradient=rng.normal(0,.1,size=17).astype(dtype);lr=(.003,.75,2.)[index%3]
            data['w'+str(number)]=weight;data['g'+str(number)]=gradient;probes.append({'lr':lr})
            expected['p'+str(number)]=weight*np.exp(-lr*np.sign(weight)*gradient)
    stream=io.BytesIO();np.savez(stream,**data)
    execution=retained_execution if retained_execution is not None else execute(source,prefix,Path(__file__).with_name('p6_egl_worker.py').read_text(),
                      inputs={'probes.json':json.dumps(probes).encode(),'probes.npz':stream.getvalue()},
                      timeout=timeout-min(180,timeout//5)-5,gpu=False,rss_limit_mib=10240,cpu_threads=8)
    result={'verdict':'FAIL','execution':execution,'model_requests':0,
            'source_and_figure_review':'REQUIRED; numerical output alone cannot prove algorithm use or plotted data'}
    if execution['status']!='COMPLETED_UNGRADED':return result
    folder=Path(execution['output']);out=folder/'result';weights={};metrics={};rows=[]
    result['retained_artifacts_only']=retained_execution is not None
    missing_usage=not (folder/'optimizer_usage.json').is_file()
    try:
        actual=bounded_npz(folder/'optimizer_actual.npz',expected_keys=expected)
        for name,value in expected.items():
            limit=2e-6 if value.dtype==np.float32 else 1e-12
            if actual[name].dtype!=value.dtype or actual[name].shape!=value.shape or not np.allclose(actual[name],value,rtol=limit,atol=limit):
                raise ValueError('Signed/zero optimizer probe failed')
        result['training_usage']='unavailable' if missing_usage else bounded_json(folder/'optimizer_usage.json')
        if missing_usage and retained_execution is None:raise ValueError('Training optimizer telemetry missing')
        if not missing_usage:
            usage=result['training_usage']
            if usage['probe_cases']!=50 or type(usage['training_eg_step_calls']) is not int or usage['training_eg_step_calls']<5400:
                raise ValueError('Submitted optimizer was not used in the full training protocol')
        result['check_stage']='curves_and_weights'
        for n in (200,2000,20000):
            for seed in (1,2,3):
                for alg in ('eg','gd'):
                    path=Path(f'N{n}/seed{seed}/{alg}');m=bounded_json(out/path/'metrics.json');gold=bounded_json(reference/path/'metrics.json')
                    lr={'eg':{200:.75,2000:1.,20000:1.},'gd':{200:.5,2000:.01,20000:.01}}[alg][n]
                    contract={'n':n,'k':100,'r':50,'seed':seed,'algorithm':alg,'learning_rate':lr,'weight_decay':0.,'momentum':0.,
                              'epochs':30,'total_updates':600,'batch_size':500,'training_samples':10000,'validation_samples':1000,'test_samples':1000,'initial_weight':100/n}
                    if any(m.get(k)!=v for k,v in contract.items()):raise ValueError('EGL frozen run configuration differs')
                    curves=m['curves']
                    if len(curves)!=31 or [r['update'] for r in curves]!=list(range(0,601,20)):raise ValueError('EGL full curve coverage required')
                    for point in curves:
                        for key in ('val_accuracy_pct','test_accuracy_pct','val_loss','test_loss'):
                            v=point[key]
                            if type(v) not in (float,int) or not np.isfinite(v) or v<0 or (key.endswith('_pct') and v>100):raise ValueError('Invalid EGL curve numeric value')
                    curve_rmse=float(np.sqrt(np.mean([(a['test_accuracy_pct']-b['test_accuracy_pct'])**2 for a,b in zip(curves,gold['curves'])])))
                    if curve_rmse>1 or abs(curves[-1]['test_accuracy_pct']-gold['curves'][-1]['test_accuracy_pct'])>1:
                        raise ValueError('EGL frozen local reference tolerance exceeded')
                    array=bounded_npy(out/path/'final_weights.npy',max_bytes=100000,max_elements=20000)
                    if array.dtype!=np.float32 or array.shape!=(n,) or not np.isfinite(array).all():raise ValueError('Invalid final weight vector')
                    if alg=='eg' and not np.all(array>0):raise ValueError('Main EG weights must remain positive')
                    if (m['final_negative_weight_count']!=int((array<0).sum()) or
                        abs(m['relevant_weight_mean']-float(array[:100].mean()))>1e-6 or
                        abs(m['irrelevant_weight_mean']-float(array[100:].mean()))>1e-6):raise ValueError('Weight statistics differ from saved parameters')
                    weights[f'N{n}_seed{seed}_{alg}.npy']=(out/path/'final_weights.npy').read_bytes()
                    metrics[n,seed,alg]=m;rows.append({'n':n,'seed':seed,'algorithm':alg,'test_accuracy_pct':curves[-1]['test_accuracy_pct'],'curve_rmse_pp':curve_rmse})
        empty=BASE/'science/private/trusted-egl-replay-empty';empty.mkdir(exist_ok=True)
        remaining=int(timeout-(time.perf_counter()-started))-5
        if remaining<1:raise ValueError('Total EGL evaluation deadline reached before independent replay')
        replay=retained_replay if retained_replay is not None else execute(empty,prefix,Path(__file__).with_name('p6_egl_replay.py').read_text(),inputs=weights,
                       timeout=min(180,remaining),gpu=False,rss_limit_mib=10240,cpu_threads=8)
        result['independent_weight_replay']=replay
        result['reused_weight_replay']=retained_replay is not None
        if replay['status']!='COMPLETED_UNGRADED':raise ValueError('Independent weight replay could not complete')
        for row in bounded_json(Path(replay['output'])/'replay.json'):
            point=metrics[row['n'],row['seed'],row['algorithm']]['curves'][-1]
            if abs(row['test_accuracy_pct']-point['test_accuracy_pct'])>1e-8 or abs(row['test_loss']-point['test_loss'])>1e-5:
                raise ValueError('Saved weight replay differs from reported accuracy/loss')
        groups=[];gains={}
        for n in (200,2000,20000):
            means={}
            for alg in ('eg','gd'):
                values=[metrics[n,s,alg]['curves'][-1]['test_accuracy_pct'] for s in (1,2,3)]
                gold_values=[bounded_json(reference/f'N{n}/seed{s}/{alg}/metrics.json')['curves'][-1]['test_accuracy_pct'] for s in (1,2,3)]
                means[alg]=statistics.mean(values)
                if abs(means[alg]-statistics.mean(gold_values))>.5:raise ValueError('Three-seed mean exceeds frozen tolerance')
                groups.append({'n':n,'algorithm':alg,'mean_test_accuracy_pct':means[alg],'std_test_accuracy_pct':statistics.stdev(values)})
            gains[str(n)]=means['eg']-means['gd']
        claim=gains['2000']>=15 and gains['20000']>=35
        result['check_stage']='summary_and_manifest'
        summary=bounded_json(out/'summary.json')
        egl_summary(summary,groups,gains,metrics)
        csv_path=out/'per_seed.csv'
        if csv_path.stat().st_size>100000:raise ValueError('CSV size limit')
        csv_rows=list(csv.DictReader(csv_path.open(newline='')))
        if len(csv_rows)!=18:raise ValueError('CSV must cover all 18 runs')
        for row in rows:
            matches=[r for r in csv_rows if (int(r['n']),int(r['seed']),r['algorithm'])==(row['n'],row['seed'],row['algorithm'])]
            if len(matches)!=1:raise ValueError('CSV run duplicate/missing')
            value=float(alias(matches[0],('test_accuracy_pct','final_test_accuracy_pct'),'CSV final accuracy'))
            if not np.isfinite(value) or abs(value-row['test_accuracy_pct'])>1e-8:raise ValueError('CSV differs from run records')
        manifest=egl_manifest(bounded_json(out/'run_manifest.json'),reviewed_units=reviewed_manifest_units)
        if manifest.get('device')!='cpu' or manifest.get('dtype')!='float32' or manifest.get('threads')!=8 or manifest.get('seeds')!=[1,2,3]:raise ValueError('Manifest does not attest the frozen execution protocol')
        for name in ('candidate.py','candidate_optimizer.py'):
            if manifest.get('files_sha256',{}).get(name)!=hashlib.sha256((source/name).read_bytes()).hexdigest():raise ValueError('Manifest code hash mismatch')
        for key in ('python','dependencies','command','elapsed_seconds','peak_rss_kib'):
            if key not in manifest:raise ValueError('Manifest measurement incomplete')
        if type(manifest['elapsed_seconds']) not in (int,float) or not 0<manifest['elapsed_seconds']<=timeout:raise ValueError('Invalid self-reported elapsed time')
        if (out/'figure4b_cpu.png').stat().st_size>20_000_000:raise ValueError('Plot byte limit')
        png=(out/'figure4b_cpu.png').read_bytes()
        if len(png)<24 or png[:8]!=b'\x89PNG\r\n\x1a\n' or png[12:16]!=b'IHDR':raise ValueError('Missing valid plot artifact')
        width,height=struct.unpack('>II',png[16:24])
        if not 1<=width<=4096 or not 1<=height<=4096:raise ValueError('Plot dimension limit')
        report=(out/'REPORT.md').read_text()
        if not 250<=len(report)<=100000:raise ValueError('Scientific report incomplete or oversized')
        if time.perf_counter()-started>timeout:raise ValueError('Total EGL evaluation deadline exceeded')
        result.update(verdict='INDETERMINATE_TRAINING_USAGE' if missing_usage else 'PASS_NUMERIC_REVIEW_PENDING',runs=rows,groups=groups,gains_pp=gains,
                      scientific_claim_supported=claim,implementation_fidelity='NUMERIC_PASS',plot_review='PENDING',
                      elapsed_seconds=execution['elapsed_seconds']+replay['elapsed_seconds'],
                      controller_wall_seconds=time.perf_counter()-started,total_timeout_seconds=timeout)
    except (ValueError,KeyError,TypeError,OSError) as error:
        result.update(error_type=type(error).__name__,reason=str(error)[:500])
    return result
