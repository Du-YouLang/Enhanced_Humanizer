"""Explicit schema compatibility; never infer missing execution measurements."""
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from decimal import Decimal


def finite(value, label, *, positive=False):
    if type(value) not in (int,float) or not math.isfinite(value) or (value<=0 if positive else value<0):
        raise ValueError('Invalid measured '+label)
    return value


def alias(mapping, names, label):
    values=[mapping[n] for n in names if n in mapping]
    if not values or any(v!=values[0] for v in values[1:]):
        raise ValueError('Missing or conflicting '+label)
    return values[0]


def source_identity(source):
    source=Path(source)
    if source.is_symlink():raise ValueError('Regular frozen source required')
    files={}
    for p in sorted(source.rglob('*')):
        rel=p.relative_to(source)
        if any(n in ('.git','__pycache__') for n in rel.parts) or p.suffix=='.pyc':continue
        if p.is_symlink():raise ValueError('Source link refused')
        if p.is_file():files[rel.as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    if not files:raise ValueError('Empty source snapshot')
    digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'authority':'TRUSTED_PARENT_SOURCE_SNAPSHOT','tree_sha256':digest,'files_sha256':files}


def egl_manifest(manifest,*,reviewed_units=None):
    m=dict(manifest)
    m['files_sha256']=alias(m,('files_sha256','file_sha256','code_sha256'),'code hashes')
    m['python']=alias(m,('python','python_version'),'Python version')
    m['threads']=alias(m,('threads','num_threads','torch_num_threads','cpu_threads'),'CPU threads')
    m['dtype']=alias(m,('dtype','float_dtype','parameter_dtype'),'parameter dtype')
    m['seeds']=alias(m,('seeds','random_seeds'),'seeds')
    if 'dependencies' not in m:
        m['dependencies']={k:m[k+'_version'] for k in ('torch','numpy','matplotlib') if k+'_version' in m}
    memory=[]
    for key,scale in (('peak_rss_kib',1),('peak_rss_bytes',1/1024),('peak_rss_mib',1024)):
        if key in m:memory.append(finite(m[key],key,positive=True)*scale)
    if reviewed_units:
        if reviewed_units!={'peak_memory_mb':'MiB'} or 'peak_memory_mb' not in m:
            raise ValueError('Exact independently reviewed legacy memory unit required')
        memory.append(finite(m['peak_memory_mb'],'legacy peak memory',positive=True)*1024)
    if not memory or any(abs(v-memory[0])>1e-6 for v in memory):raise ValueError('Missing or conflicting peak RSS units')
    m['peak_rss_kib']=memory[0]
    return m


def egl_summary(summary, groups, gains, metrics):
    summary=canonical_egl_summary(summary)
    if summary.get('std_ddof',1)!=1:raise ValueError('Sample standard deviation required')
    actual=summary['groups']
    if len(actual)!=6:raise ValueError('Missing grouped summary')
    for expected in groups:
        matches=[g for g in actual if (g['n'],g['algorithm'])==(expected['n'],expected['algorithm'])]
        if len(matches)!=1:raise ValueError('Duplicate/missing summary group')
        for key,value in expected.items():
            if key in ('n','algorithm'):continue
            if abs(finite(matches[0][key],key)-value)>1e-8:raise ValueError('Summary statistic inconsistent')
    if 'eg_minus_gd_mean_pp' in summary:
        values=summary['eg_minus_gd_mean_pp']
        if set(values)!=set(gains):raise ValueError('Paired group coverage differs')
        for key,value in gains.items():
            if type(values[key]) not in (int,float) or not math.isfinite(values[key]) or abs(values[key]-value)>1e-8:
                raise ValueError('Paired mean inconsistent')
    elif 'paired_differences' not in summary:raise ValueError('Paired group statistics missing')
    if 'paired_differences' in summary:
        pairs=summary['paired_differences']
        if len(pairs)!=3:raise ValueError('Paired group coverage differs')
        for n in (200,2000,20000):
            found=[p for p in pairs if p['n']==n]
            if len(found)!=1:raise ValueError('Paired group duplicate/missing')
            p=found[0];expected=[metrics[n,s,'eg']['curves'][-1]['test_accuracy_pct']-metrics[n,s,'gd']['curves'][-1]['test_accuracy_pct'] for s in (1,2,3)]
            reported=p['per_seed_eg_minus_gd_pp']
            if len(reported)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in reported):raise ValueError('Invalid paired values')
            if any(type(p[k]) not in (int,float) or not math.isfinite(p[k]) for k in ('mean_eg_minus_gd_pp','std_eg_minus_gd_pp')):
                raise ValueError('Invalid paired statistics')
            if (any(abs(a-b)>1e-8 for a,b in zip(reported,expected)) or
                    abs(p['mean_eg_minus_gd_pp']-statistics.mean(expected))>1e-8 or
                    abs(p['std_eg_minus_gd_pp']-statistics.stdev(expected))>1e-8):raise ValueError('Paired statistics inconsistent')


def canonical_egl_summary(summary):
    if 'groups' in summary:
        if any(k in summary for k in ('per_n_algorithm','per_n','aggregates')):raise ValueError('Conflicting summary representations')
        return summary
    containers=[k for k in ('per_n_algorithm','per_n','aggregates') if k in summary]
    if len(containers)!=1:raise ValueError('Explicit grouped summary required')
    container=containers[0];data=summary[container]
    if set(data)!={'200','2000','20000'}:raise ValueError('Summary dimension coverage differs')
    groups=[];pairs=[]
    for key in ('200','2000','20000'):
        row=data[key]
        for alg in ('eg','gd'):
            s=row[alg]
            if container=='per_n_algorithm':mean,std=s['mean_test_accuracy_pct'],s['std_test_accuracy_pct']
            elif container=='aggregates':mean,std=s['mean'],s['std_ddof1']
            elif isinstance(s.get('final_test_accuracy_pct'),dict):mean,std=s['final_test_accuracy_pct']['mean'],s['final_test_accuracy_pct']['std']
            else:mean,std=s['final_test_accuracy_pct_mean'],s['final_test_accuracy_pct_std']
            groups.append({'n':int(key),'algorithm':alg,'mean_test_accuracy_pct':mean,'std_test_accuracy_pct':std})
        if container=='per_n_algorithm':
            p=summary['eg_minus_gd_mean_pp'][key];values,mean,std=p['per_seed_pp'],p['mean_pp'],p['std_pp']
        elif container=='aggregates':
            p=row['paired_eg_minus_gd'];values,mean,std=p['per_seed_pp'],p['mean_pp'],p['std_ddof1_pp']
        elif 'paired_eg_minus_gd_test_accuracy_pp' in row:
            p=row['paired_eg_minus_gd_test_accuracy_pp'];values,mean,std=p['per_seed'],p['mean'],p['std']
        else:
            values,mean=row['eg_minus_gd_per_seed_pp'],row['eg_minus_gd_mean_pp'];std=statistics.stdev(values)
        pairs.append({'n':int(key),'per_seed_eg_minus_gd_pp':values,'mean_eg_minus_gd_pp':mean,'std_eg_minus_gd_pp':std})
    return {'groups':groups,'paired_differences':pairs,'std_ddof':summary.get('std_ddof',1)}


def pc_manifest(manifest, source):
    """Resolve public semantic fields; source authority stays outside submission."""
    env=manifest.get('environment',manifest.get('versions',{}))
    python=pc_python_version(manifest)
    packages=manifest.get('packages',env.get('packages'))
    if not python or not isinstance(packages,dict) or not packages:raise ValueError('Python/package measurements required')
    gates=manifest.get('gate_elapsed_seconds')
    if gates is None:
        stages=manifest.get('stages',manifest.get('gates',{}))
        if isinstance(stages,list):
            names=[s['name'] for s in stages]
            if len(names)!=len(set(names)):raise ValueError('Duplicate stage')
            stages={s['name']:s for s in stages}
        gates={}
        for name in ('smoke','anchor','grid'):
            stage=stages[name]
            if name=='smoke' and 'smoke' in stage:stage=stage['smoke']
            gates[name]=alias(stage,('wall_seconds','seconds','elapsed_seconds','elapsed_s','wall_s'),name+' elapsed')
    for name in ('smoke','anchor','grid'):finite(gates[name],name+' time',positive=True)
    variants=[manifest[k] for k in ('data_sha256','data_files','input_files') if k in manifest]
    variants += [manifest[k]['files'] for k in ('data','inputs') if isinstance(manifest.get(k),dict) and 'files' in manifest[k]]
    normalized=[input_hashes(raw) for raw in variants]
    if not normalized or any(value!=normalized[0] for value in normalized[1:]):raise ValueError('Missing or conflicting input hashes')
    return {'python':python,'packages':packages,'gate_elapsed_seconds':gates,'data_sha256':normalized[0],
            'source_provenance':source_identity(source),'gpu_measurement':manifest.get('gpu',env.get('gpu','unavailable')),
            'driver_measurement':'unavailable' if not manifest.get('driver') else manifest['driver']}


def pc_python_version(manifest):
    """Recognize measured version aliases, rejecting conflicting declarations."""
    values=[]
    for mapping in (manifest,manifest.get('environment',{}),manifest.get('versions',{})):
        if not isinstance(mapping,dict):raise ValueError('Python measurement container must be a mapping')
        for name in ('python','python_version'):
            if name not in mapping:continue
            value=mapping[name]
            if isinstance(value,dict):value=value.get('version')
            if not isinstance(value,str) or not value.strip():raise ValueError('Measured Python version required')
            values.append(value)
    if not values or any(v!=values[0] for v in values[1:]):raise ValueError('Missing or conflicting Python measurements')
    return values[0]


def pc_within_tolerance(actual_accuracy,reference_accuracy,actual_cosine,reference_cosine):
    """Compare saved decimal measurements against the exact frozen boundaries."""
    values=(actual_accuracy,reference_accuracy,actual_cosine,reference_cosine)
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):return False
    a,b,c,d=(Decimal(str(v)) for v in values)
    return 100*abs(a-b)<=Decimal('0.25') and abs(c-d)<=Decimal('0.02')


def input_hashes(raw):
    if isinstance(raw,list):
        pairs=[(row['path'],row) for row in raw]
        if len({k for k,v in pairs})!=len(pairs):raise ValueError('Duplicate input file')
        raw=dict(pairs)
    if not isinstance(raw,dict) or not raw:raise ValueError('Input hashes required')
    data={}
    for name,row in raw.items():
        value=row.get('sha256') if isinstance(row,dict) else row
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('Exact input hash required')
        if name in data:raise ValueError('Duplicate input')
        data[name]=value
    return data
