"""Generate PC-ALM cross-seed tables from CSV; this is not an execution oracle."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from workbench.science import grid_summary

DEEP_NARROW=((8,64),(8,128),(16,64),(16,128))


def read_rows(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>20_000_000:
        raise ValueError('Regular, bounded CSV required')
    with path.open(encoding='utf-8',newline='') as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):
            raise ValueError('Distinct CSV columns required')
        required={'dataset','activation','method','width','depth','seed','final_test_acc','grad_cos_to_bp'}
        if not required.issubset(reader.fieldnames):raise ValueError('Required grid columns absent')
        rows=[]
        for row in reader:
            if None in row or any(row.get(k) is None for k in required):raise ValueError('Malformed CSV row')
            for name in ('width','depth','seed'):row[name]=int(row[name])
            for name in ('final_test_acc','grad_cos_to_bp'):row[name]=float(row[name])
            rows.append(row)
            if len(rows)>10000:raise ValueError('Grid row limit exceeded')
    return rows


def statistics_table(rows,*,dataset,activation,widths,depths,seeds):
    summary=grid_summary(rows,dataset=dataset,activation=activation,widths=widths,depths=depths,
                         seeds=seeds,deep_narrow=DEEP_NARROW)
    spread=summary['seed_spread'];table=[]
    for ddof in (0,1):
        key='ddof'+str(ddof)
        for method in ('bp','pc','pcalm'):
            values=spread[method]
            table.append({'method':method,'ddof':ddof,'cells':summary['grid_cells'],
                          'mean_std_pp':values[key+'_mean']*100 if isinstance(values[key+'_mean'],(int,float)) else 'unavailable',
                          'max_std_pp':values[key+'_max']*100 if isinstance(values[key+'_max'],(int,float)) else 'unavailable'})
        group=table[-3:]
        table.append({'method':'all','ddof':ddof,'cells':3*summary['grid_cells'],
                      'mean_std_pp':mean(r['mean_std_pp'] for r in group) if len(seeds)>1 else (0. if ddof==0 else 'unavailable'),
                      'max_std_pp':max(r['max_std_pp'] for r in group) if len(seeds)>1 else (0. if ddof==0 else 'unavailable')})
    return {'dataset':dataset,'activation':activation,'summary':summary,'cross_seed_statistics':table,
            'same_seed_repeat_tolerance':'NOT_ESTIMATED_FROM_CROSS_SEED_VARIANCE',
            'execution_fidelity':'NOT_ESTABLISHED_BY_TABLE_GENERATION'}


def markdown(result):
    lines=['# PC-ALM cross-seed statistics','',
           'Computed from the input CSV. This table does not establish execution fidelity or same-seed tolerance.','',
           '| Method | ddof | Cells | Mean standard deviation (pp) | Maximum standard deviation (pp) |',
           '|---|---:|---:|---:|---:|']
    for row in result['cross_seed_statistics']:
        fmt=lambda value:f'{value:.4f}' if isinstance(value,(int,float)) else str(value)
        lines.append(f"| {row['method']} | {row['ddof']} | {row['cells']} | {fmt(row['mean_std_pp'])} | {fmt(row['max_std_pp'])} |")
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv',required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--dataset',default='fashion_mnist');parser.add_argument('--activation',default='relu')
    parser.add_argument('--widths',default='8,16,32,64,128');parser.add_argument('--depths',default='8,16,32,64,128')
    parser.add_argument('--seeds',default='0,1,2');args=parser.parse_args();tick=time.perf_counter()
    dimensions={k:tuple(int(v) for v in getattr(args,k).split(',')) for k in ('widths','depths','seeds')}
    result=statistics_table(read_rows(args.csv),dataset=args.dataset,activation=args.activation,**dimensions)
    result.update(input_sha256=hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),elapsed_seconds=time.perf_counter()-tick,
                  model_requests=0)
    out=Path(args.out)
    if out.exists():raise ValueError('Preserve earlier tables and choose a new output directory')
    out.mkdir(parents=True)
    (out/'statistics.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    (out/'statistics.md').write_text(markdown(result),encoding='utf-8')
    print(json.dumps({'status':'STATISTICS_GENERATED_NOT_EXECUTION_ACCEPTANCE','output':str(out),'model_requests':0}))


if __name__=='__main__':main()
