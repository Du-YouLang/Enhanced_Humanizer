"""Scoped refresh continuation: immutable old groups and one completed DS session."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from p2_candidates import digest

PRIOR='refresh-20261126T043132Z'
LABELS=('GPT61-Sol','GPT62-Sol')


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):
    p=Path(path)
    raw=b'symlink\0'+os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def journal_value(path):
    value=read(path)
    from pi_full_protocol import digest as journal_digest
    if value['value_sha256']!=journal_digest(value['value']):raise ValueError('Retained journal hash mismatch')
    return value['value']


def tree_pins(root):
    root=Path(root);pins={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            target=Path(os.readlink(p))
            if target.is_absolute() or not p.resolve().is_relative_to(root.resolve()):raise ValueError('Retained worktree link escapes its root')
            pins[str(p)]=sha(p)
        elif p.is_file():pins[str(p)]=sha(p)
    return pins


def build_spec(base):
    base=Path(base)
    if base.name!=PRIOR or base.parent!=Path('/opt/workbench/benchmark/private/model-refresh'):
        raise ValueError('Only the explicitly audited score-contract boundary is authorized')
    owner=read(base/'owner.json');proc=Path('/proc')/str(owner['pid'])
    if proc.exists() and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==owner['boot_id']:
        try:alive=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==owner['process_start_ticks']
        except FileNotFoundError:alive=False
        if alive:raise ValueError('Prior exact owner still exists')
    stops=list(base.glob('score-contract-safe-stop-*.json'))
    if len(stops)!=1 or read(stops[0])['open_model_journals'] or read(stops[0])['models_interrupted']!=0:
        raise ValueError('Actual no-open-model stop receipt required')
    completed=list(base.glob('*/*/control/stages/*-model.completed.json'))
    if len(completed)!=17:raise ValueError('Exact seventeen retained model roles required')
    for p in base.glob('*/*/control/stages/*-model.started.json'):
        if not p.with_name(p.name.replace('.started.json','.completed.json')).exists():raise ValueError('Uncertain model cannot replay')
    groups={}
    for label in LABELS:
        p=base/'stages'/('BIP-black-1--'+label+'.completed.json');v=journal_value(p)
        if [(r['method'],r['outcome']) for r in v['rows']]!=[('Direct','PASS'),('Enhanced','INDETERMINATE'),('SingleAgent-MatchedBudget','PASS')]:
            raise ValueError('Unexpected retained result groups')
        groups[label]=str(p)
    partial=base/'BIP-black-1/DS41-Flash1017';worker=journal_value(partial/'control/stages/matched-model.completed.json')
    if worker['status']!='COMPLETED' or worker['model_id']!='deepseek-flash':raise ValueError('Completed original DS session required')
    if (partial/'control/stages/matched-public.completed.json').exists():raise ValueError('Reconcile newly completed public stage before changing scope')
    pins={}
    for pattern in ('*.json','stages/*.json','*/*/control/stages/*.json','*/*/*/worker.json','*/*/*/controller-outcome.json','*/*/*/candidate-private.json'):
        for p in base.glob(pattern):
            if p.name not in ('heartbeat.json','progress.json','score-contract-boundary-guard.private.json'):pins[str(p)]=sha(p)
    for role in base.glob('*/*/*/code'):
        pins.update(tree_pins(role))
    spec={'prior_root':str(base),'prior_run_id':PRIOR,'retained_groups':groups,'partial_model_task':'BIP-black-1/DS41-Flash1017',
          'partial_worker_journal':str(partial/'control/stages/matched-model.completed.json'),'partial_work':str(partial/'matched/code'),
          'partial_worker_sha256':sha(partial/'control/stages/matched-model.completed.json'),
          'supplement_labels':list(LABELS),'retained_model_roles':17,'retained_result_cells':6,'completed_role_replays':0,'retained_sha256':pins}
    spec['recovery_sha256']=digest(spec);return spec


def validate_spec(spec):
    body=dict(spec);h=body.pop('recovery_sha256')
    if digest(body)!=h or body['prior_run_id']!=PRIOR or body['supplement_labels']!=list(LABELS) or body['retained_model_roles']!=17 or body['retained_result_cells']!=6:
        raise ValueError('Recovery authorization or binding differs')
    for p,h in spec['retained_sha256'].items():
        if sha(p)!=h:raise ValueError('Retained result/program changed: '+p)
    return spec


def bootstrap(root,spec):
    from p6_refresh_protocol import complete_group
    root=Path(root);validate_spec(spec)
    for label,p in spec['retained_groups'].items():
        target=root/'stages'/('BIP-black-1--'+label+'.completed.json');target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if journal_value(target)!=journal_value(p):raise ValueError('Reused group differs')
        else:complete_group(target,'BIP-black-1--'+label,journal_value(p))
    return {'retained_cells':6,'retained_models':17,'replayed_models':0}


def seed_partial(journal,dest,spec):
    """Copy only code/Git; never auth/home/session files. Reuse the exact model result."""
    from p6_refresh_protocol import complete_group
    root=journal.root
    if sha(spec['partial_worker_journal'])!=spec['partial_worker_sha256']:raise ValueError('Retained model journal changed')
    if (root/'matched-model.completed.json').exists():
        if not (root/'matched-setup.completed.json').exists():raise ValueError('Interrupted seed requires reconciliation; no dispatch')
        return
    source=Path(spec['partial_work']);target=Path(dest)/'matched';target.mkdir()
    for name in ('home','git-tmp','tmp','cache'):(target/name).mkdir()
    before=tree_pins(source);shutil.copytree(source,target/'code',symlinks=True)
    copied=tree_pins(target/'code')
    if {str(Path(p).relative_to(source)):h for p,h in before.items()}!={str(Path(p).relative_to(target/'code')):h for p,h in copied.items()}:
        raise ValueError('Copied completed program differs')
    worker=copy.deepcopy(journal_value(spec['partial_worker_journal']))
    worker.update(root=str(target),work=str(target/'code'),retained_model_origin_root=str(source.parent),retained_model_journal_sha256=spec['partial_worker_sha256'])
    # A retained-only setup cannot dispatch even after an interrupted seed.
    complete_group(root/'matched-model.completed.json','matched-model',worker)
    complete_group(root/'matched-setup.completed.json','matched-setup',{'descriptor':{'retained_only':True},'env':{}})
    complete_group(root/'retained-matched-program.completed.json','retained-matched-program',{'source':str(source),'copied':str(target/'code'),'files':len(before),'model_replay':False})


def retained_builders(spec,label):
    if label not in LABELS:raise ValueError('No affected Enhanced supplement authorized')
    from p6_guidance_linux import verify
    base=Path(spec['prior_root'])/'BIP-black-1'/label;values=[];workers={}
    for cid in 'ABC':
        name='pool-'+cid;v=journal_value(base/'control/stages'/(name+'-public.completed.json'))
        frozen=journal_value(base/'control/stages'/(name+'-freeze.completed.json'));verify(v,frozen)
        values.append(dict(v,id=cid));workers[name]=journal_value(base/'control/stages'/(name+'-model.completed.json'))
    return values,workers


def actual_recovery_controls(spec):
    """Real old journals and code, zero providers/candidate executions/ledger writes."""
    import tempfile
    from pi_full_protocol import Journal
    from p6_refresh_protocol import refresh_judge_prompt,require_valid_refresh_judgment
    from p2_judges import J3
    validate_spec(spec)
    with tempfile.TemporaryDirectory(prefix='refresh-recovery-control-',dir='/opt/workbench/tmp') as temp:
        root=Path(temp);bootstrap(root,spec)
        links=root/'link-controls';links.mkdir();(links/'internal').symlink_to('not-generated.txt')
        assert len(tree_pins(links))==1
        (links/'escape').symlink_to('../outside.txt')
        try:tree_pins(links)
        except ValueError:pass
        else:raise AssertionError('Escaping link must be denied')
        stage=root/'partial/control/stages';j=Journal(stage)
        seed_partial(j,root/'partial',spec)
        def deny():raise AssertionError('Completed model was replayed')
        w=j.run('matched-model',deny)
        assert w['status']=='COMPLETED' and w['scope'].startswith('REFRESH/'+PRIOR+'/')
        assert len(list((root/'stages').glob('*.completed.json')))==2
        seed_partial(j,root/'partial',spec)  # Exact reuse; no duplicate code/session.
        denied=copy.deepcopy(spec);denied['partial_worker_sha256']='0'*64
        try:seed_partial(Journal(root/'negative/stages'),root/'negative',denied)
        except ValueError:pass
        else:raise AssertionError('Mismatched retained worker must be denied')
        pools=[]
        for label in LABELS:
            values,workers=retained_builders(spec,label)
            pool=journal_value(Path(spec['prior_root'])/'BIP-black-1'/label/'control/stages/public-pool.completed.json')
            prompt=refresh_judge_prompt(pool);raw=json.loads(prompt.split('Required judgment JSON shape: ',1)[1])
            result=J3(lambda _:(raw,{})).judge(pool);require_valid_refresh_judgment(result)
            assert len(values)==3 and len(workers)==3
            pools.append({'label':label,'candidate_ids':[c['id'] for c in values],'actual_J3_status':result['status']})
    return {'status':'PASS_ACTUAL_RETAINED_JOURNAL_CODE_AND_J3_CONTROLS','retained_result_cells':6,
            'retained_model_roles':17,'completed_DS_session_reused':True,'copy_hashes_equal':True,'internal_dangling_link_preserved':True,'escaping_link_denied':True,
            'candidate_executions':0,'provider_calls':0,'real_ledger_writes':0,'pools':pools}
