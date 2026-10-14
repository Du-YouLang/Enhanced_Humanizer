"""PC-ALM artifact checks; replay and source review remain separate gates.

Never import a submission. The owner launches training/replay in the existing
science sandbox; only bounded JSON/CSV outputs are inspected here.
"""
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from workbench.science import claim_checks,grid_summary
from p6_output_data import bounded_json
from p6_pc_statistics import DEEP_NARROW,read_rows
from p6_science_contracts import pc_manifest


def regular(root,relative):
    root=Path(root)
    if root.is_symlink():raise ValueError('Artifact directory cannot alias external state')
    root=root.resolve();path=root/relative
    if not path.resolve().is_relative_to(root) or not path.is_file() or any(p.is_symlink() for p in (path,*path.parents) if p.is_relative_to(root)):
        raise ValueError('Regular artifact within the submitted bundle required')
    return path


def run_artifacts(folder,row,eta):
    folder=Path(folder)
    cfg=bounded_json(regular(folder,'config.json'));summary=bounded_json(regular(folder,'summary.json'))
    m,w,d,s=row['method'],row['width'],row['depth'],row['seed']
    sections={
        'model':{'activation':row['activation'],'width':w,'depth':d,'input_dim':784,'output_dim':10},
        'training':{'seed':s,'epochs':1,'batch_size':64,'gamma0':1.,'eta0':.001,
                    'train_subset':60000,'test_subset':10000,'drop_last':True,'learning_rate':None},
        'method':{'name':m,'budget':0 if m=='bp' else 2*d,'rho':1.,'inner_steps':1,
                  'weight_credit_timing':'pre_dual_energy','state_lr':eta[w,d]}}
    if cfg.get('dataset')!=row['dataset']:raise ValueError('Wrong dataset in native run config')
    for section,values in sections.items():
        actual=cfg.get(section,{})
        for key,value in values.items():
            if (key not in actual or actual[key]!=value
                    or (type(value) in (int,float) and type(actual[key]) not in (int,float))
                    or (type(value) is bool and type(actual[key]) is not bool)):
                raise ValueError('Native run config differs from frozen protocol: '+section+'.'+key)
    if m=='pcalm' and cfg['method'].get('alpha')!=1.:raise ValueError('Wrong ALM dual step')
    for key in ('dataset','activation','method','width','depth','seed','final_test_acc','grad_cos_to_bp'):
        if summary.get(key)!=row[key]:raise ValueError('cells.csv differs from native summary: '+key)
    if summary.get('steps')!=60000//64:raise ValueError('Incomplete epoch')
    for key,value in {'epochs':1,'batch_size':64,'gamma0':1.,'eta0':.001,'rho':1.,
                      'train_subset':60000,'test_subset':10000,'budget':0 if m=='bp' else 2*d,
                      'state_lr':eta[w,d]}.items():
        if summary.get(key)!=value:raise ValueError('Native summary protocol differs: '+key)
    path=regular(folder,'metrics.csv')
    if path.stat().st_size>100000:raise ValueError('Oversized native metrics')
    with path.open(encoding='utf-8',newline='') as stream:metrics=list(csv.DictReader(stream))
    if len(metrics)!=1 or int(metrics[0]['epoch'])!=1 or int(metrics[0]['step'])!=60000//64:
        raise ValueError('Native epoch metrics incomplete')
    for field,summary_field in (('test_acc','final_test_acc'),('train_acc','final_train_acc'),
                                ('test_mse','final_test_mse'),('train_mse','final_train_mse')):
        value=float(metrics[0][field]);reported=summary.get(summary_field)
        if not math.isfinite(value) or type(reported) not in (int,float) or not math.isfinite(reported) or abs(value-reported)>1e-12:
            raise ValueError('Native metrics and summary differ')


def validate_grid(folder,eta,*,widths=(8,16,32,64,128),depths=(8,16,32,64,128),seeds=(0,)):
    folder=Path(folder)
    if folder.is_symlink():raise ValueError('Grid directory cannot alias external state')
    rows=read_rows(regular(folder,'cells.csv'))
    if any(r['dataset']!='fashion_mnist' or r['activation']!='relu' for r in rows):
        raise ValueError('Only the declared dataset and activation may appear')
    stats=grid_summary(rows,dataset='fashion_mnist',activation='relu',widths=widths,depths=depths,
                       seeds=seeds,deep_narrow=DEEP_NARROW)
    for row in rows:
        name=f"{row['dataset']}_{row['activation']}_n{row['width']}_l{row['depth']}_seed{row['seed']}_{row['method']}"
        run_artifacts(folder/name,row,eta)
    return stats


def validate_bundle(root,eta,thresholds,*,source=None):
    root=Path(root)
    stats=validate_grid(root/'grid',eta)
    smoke=bounded_json(regular(root,'smoke/summary.json'))
    value=smoke.get('final_test_acc')
    if type(value) not in (float,int) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError('Valid smoke summary required')
    # These anchors are explicitly public in the official README/task card.
    for method,(accuracy,cosine) in {'bp':(.7866,1.),'pc':(.6813,.604),'pcalm':(.7775,.909)}.items():
        folder=root/'anchor'/f'fashion_mnist_relu_n32_l32_seed0_{method}'
        row=bounded_json(regular(folder,'summary.json'))
        for key,expected in {'dataset':'fashion_mnist','activation':'relu','method':method,'width':32,'depth':32,'seed':0}.items():
            if row.get(key)!=expected:raise ValueError('Anchor run identity differs')
        run_artifacts(folder,row,eta)
        if any(type(row.get(k)) not in (int,float) or not math.isfinite(row[k]) for k in ('final_test_acc','grad_cos_to_bp')):
            raise ValueError('Finite anchor metrics required')
        if abs(row['final_test_acc']-accuracy)>.01 or abs(row['grad_cos_to_bp']-cosine)>.05:
            raise ValueError('Public anchor tolerance exceeded')
    manifest=bounded_json(regular(root,'run_manifest.json'))
    if source is not None:
        manifest=pc_manifest(manifest,source)
    for name in (('git_commit','python','packages','gpu','driver','data_sha256','gate_elapsed_seconds') if source is None else
                 ('python','packages','data_sha256','gate_elapsed_seconds','source_provenance')):
        if not manifest.get(name):raise ValueError('Run manifest incomplete: '+name)
    commit=manifest.get('git_commit')
    if source is None and (not isinstance(commit,str) or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit)):
        raise ValueError('Exact source commit required')
    for name in ('smoke','anchor','grid'):
        elapsed=manifest['gate_elapsed_seconds'].get(name)
        if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<=0:
            raise ValueError('Positive measured time for every gate required')
    return {'implementation_gate':'ARTIFACTS_AND_PUBLIC_ANCHOR_PASS_REPLAY_PENDING',
            'independent_replay':'REQUIRED_SAME_ENVIRONMENT_TWO_COMMIT_SELECTED_CELLS',
            'source_and_manifest_attestation':'REVIEW_REQUIRED','manifest_checked':manifest,
            'science_gate':claim_checks(stats,thresholds),'statistics':stats}
