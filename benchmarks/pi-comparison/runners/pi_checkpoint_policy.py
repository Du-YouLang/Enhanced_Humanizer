"""Reconcile one interrupted acceptance without replaying model stages."""
import json
from pathlib import Path

AUTHORIZATION='USER_APPROVED_2026-10-15_PC_ACCEPTANCE_THEN_UNSTARTED'


def checkpoint_cells(plan,rows,interrupted):
    cells=plan['remaining_cells']
    if not rows or [r['cell'] for r in rows]!=cells[:len(rows)]:
        raise ValueError('Exact completed continuation prefix required')
    if len(rows)!=61 or interrupted!=cells[61] or interrupted!={
            'task_id':'SCI-PC-ALM','profile':'P0','provider':'deepseek','repetition':0}:
        raise ValueError('Only the explicitly reconciled PC acceptance is authorized')
    if len(cells)!=85 or len(cells[62:])!=23:raise ValueError('Exact85/61/one/23 partition required')
    return cells[62:]


def retained_value(path,name):
    from pi_full_protocol import digest
    row=json.loads(Path(path).read_bytes())
    if row['stage']!=name or row['value_sha256']!=digest(row['value']):
        raise ValueError('Retained stage receipt changed')
    return row['value']


class AcceptanceJournal:
    """Only acceptance may execute. Completed model/public/setup/freeze are data."""
    def __init__(self,original,recovery,name):
        from pi_full_protocol import Journal
        self.original=Path(original);self.new=Journal(recovery);self.name=name

    def run(self,name,action):
        if name==self.name+'-acceptance':return self.new.run(name,action)
        if name not in [self.name+'-'+s for s in ('setup','model','public','freeze')]:
            raise ValueError('Recovery cannot execute another role or stage')
        return retained_value(self.original/(name+'.completed.json'),name)


def cached_training_runner(real_run,cache,output,events):
    """Inside the existing fence: reuse only exact path-bound completed runs."""
    import subprocess
    output=Path(output).resolve()
    def run(argv,*args,**kwargs):
        if not isinstance(argv,(list,tuple)) or '--output-dir' not in argv or not any(
                str(v).endswith('/train.py') or str(v)=='train.py' for v in argv):
            return real_run(argv,*args,**kwargs)
        target=Path(argv[argv.index('--output-dir')+1]).resolve()
        if not target.is_relative_to(output):raise ValueError('Training output escapes recovery root')
        relative=target.relative_to(output).as_posix();entry=cache.get(relative)
        if entry is None:return real_run(argv,*args,**kwargs)
        config=next((str(argv[i+1]) for i,v in enumerate(argv[:-1]) if v=='--config'),None)
        overrides={str(v)[2:].replace('-','_'):str(argv[i+1]) for i,v in enumerate(argv[:-1])
                   if str(v).startswith('--') and v not in ('--config','--output-dir','--data-dir')}
        if Path(config or '').name!=entry['config_name'] or overrides!=entry['overrides']:
            raise ValueError('Cached training command differs from frozen invocation')
        target.mkdir(parents=True,exist_ok=True)
        for name,text in entry['files'].items():
            if name not in ('config.json','summary.json','metrics.csv'):raise ValueError('Unknown cached artifact')
            with (target/name).open('x',encoding='utf8') as f:f.write(text)
        events.append(relative)
        return subprocess.CompletedProcess(argv,0,stdout='',stderr='')
    return run
