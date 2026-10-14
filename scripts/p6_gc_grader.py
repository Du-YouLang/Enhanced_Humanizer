"""Independent numeric GC grading; candidate imports happen only in the OS fence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time

from p6_output_data import bounded_json,bounded_npz
from p6_science_sandbox import execute
from p6_gc_dependencies import ensure_gc_threadpool
from p6_gc_source_policy import validate_gc_source,checked_source_review


def material(root,name):
    from workbench.science import normalized_material_path
    parts=normalized_material_path(name).parts
    aliases={'agent_materials':'agent_public','private_evaluation':'judge_private'}
    path=Path(root).joinpath(aliases.get(parts[0],parts[0]),*parts[1:]).resolve()
    if not path.is_relative_to(Path(root).resolve()):raise ValueError('GC material escapes root')
    return path


def grade(source,root,prefix,*,timeout=180,source_review=None):
    import numpy as np
    root=Path(root);source=Path(source)
    text=(source/'gc_cupy.py').read_text()
    if source_review is None:validate_gc_source(text)
    else:checked_source_review(text,source_review)
    threadpool_limits=ensure_gc_threadpool(prefix).threadpool_limits
    manifest=json.loads((root/'judge_private/manifest.json').read_text())
    oracle_path=root/'judge_private/cpu_oracle_frozen.py'
    if hashlib.sha256(oracle_path.read_bytes()).hexdigest()!=manifest['reference_sha256']:
        raise ValueError('Frozen CPU oracle changed')
    spec=importlib.util.spec_from_file_location('private_gc_oracle',oracle_path)
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    inputs={};cases=[];expected={};performance=None
    for index,row in enumerate(manifest['cases']):
        inp=material(root,row['input']);gold=material(root,row['gold'])
        if hashlib.sha256(inp.read_bytes()).hexdigest()!=row['sha256'] or hashlib.sha256(gold.read_bytes()).hexdigest()!=row['gold_sha256']:
            raise ValueError('Frozen GC input/gold changed')
        filename='input_'+str(index)+'.npz';inputs[filename]=inp.read_bytes()
        cases.append({'file':filename,'noncontiguous':row['visibility']=='private' and row['case']=='mixed_lag3',
                      'performance':row['case']=='performance'})
        expected['case_'+str(index)]=bounded_npz(gold,expected_keys={'gc'})['gc']
        if cases[-1]['noncontiguous']:expected['noncontiguous']=expected['case_'+str(index)][:,::-1,::-1]
        if row['case']=='performance':performance=(inp,expected['case_'+str(index)])
    for repeat in range(5):
        for kind in ('repeat_','transfer_'):expected[kind+str(repeat)]=performance[1]
    inputs['cases.json']=json.dumps(cases).encode()
    execution=execute(source,prefix,Path(__file__).with_name('p6_gc_worker.py').read_text(),inputs=inputs,
                      timeout=timeout,gpu=True,rss_limit_mib=8192,cpu_threads=1)
    result={'execution':execution,'verdict':'FAIL','numeric_cases':0,'source_review':'REQUIRED_FOR_SUBSTANTIVE_GPU_ALGORITHM'}
    if execution['status']!='COMPLETED_UNGRADED':return result
    folder=Path(execution['output'])
    try:
        actual=bounded_npz(folder/'actual.npz',expected_keys=expected)
        errors=[]
        for name,gold in expected.items():
            array=actual[name]
            if array.dtype!=np.float64 or array.shape!=gold.shape or not np.isfinite(array).all():raise ValueError('GC shape/dtype/nonfinite output')
            delta=np.abs(array-gold);limit=1e-7+1e-5*np.abs(gold)
            if not np.all(delta<=limit):raise ValueError('GC independent numeric tolerance exceeded: '+name)
            errors.append({'name':name,'elements':gold.size,'max_abs':float(delta.max()) if delta.size else 0.})
        report=bounded_json(folder/'measurements.json')
        if type(report.get('invalid_cases')) is not int or report['invalid_cases']!=13 or report.get('warmups')!=3:
            raise ValueError('GC measurement protocol incomplete')
        if type(report.get('rawkernel_launches')) is not int or report['rawkernel_launches']<=0:raise ValueError('No substantive GPU launch evidence')
        # CPU timing uses the trusted oracle only, outside candidate execution.
        data=bounded_npz(performance[0]);kwargs={n:(int(data[n]) if n=='lag' else float(data[n])) for n in ('lag','ridge','eps')}
        cpu=[]
        with threadpool_limits(limits=1):
            for _ in range(3):
                tick=time.perf_counter();value=oracle.compute_gc_cpu(data['signals'],data['pairs'],data['windows'],**kwargs)
                cpu.append((time.perf_counter()-tick)*1000)
                if not np.allclose(value,performance[1],rtol=1e-5,atol=1e-7):raise ValueError('CPU timing oracle/gold mismatch')
        for field in ('gpu_cuda_event_ms','gpu_resident_wall_ms','gpu_transfer_inclusive_ms'):
            values=report[field]
            if len(values)!=5 or any(type(v) not in (float,int) or not np.isfinite(v) or v<=0 for v in values):
                raise ValueError('Invalid GPU timing evidence')
        timings={'cpu_single_thread_ms':cpu,**{k:report[k] for k in ('gpu_cuda_event_ms','gpu_resident_wall_ms','gpu_transfer_inclusive_ms')}}
        timings.update(same_machine_resident_speedup=statistics.median(cpu)/statistics.median(timings['gpu_resident_wall_ms']),
                       same_machine_transfer_speedup=statistics.median(cpu)/statistics.median(timings['gpu_transfer_inclusive_ms']))
        result.update(verdict='PASS' if source_review else 'PASS_NUMERIC_REVIEW_PENDING',numeric_cases=len(cases)+1,repeat_outputs=10,
                      errors=errors,worker_advisory=report,timings=timings)
        if source_review:result.update(source_review='INDEPENDENT_SOURCE_REVIEW_PASSED',source_review_evidence=source_review)
    except (ValueError,KeyError,TypeError,OSError) as error:
        result.update(reason=str(error)[:500],error_type=type(error).__name__)
    return result
