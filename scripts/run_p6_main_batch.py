"""Finite serial main matrix and same-pool reviews; stop on infrastructure failure.

This is a current authorized experiment controller, never a scheduler or retry
service. Its attempt index is authoritative even when a task does not finish.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from wsl_project import ROOT,run

QUERY=r'''import json,sys
from pathlib import Path
name=sys.argv[1];base=Path('/opt/workbench/benchmark/private');launch=json.loads((base/'main-launches'/(name+'.json')).read_text())
root=base/'main-runs'/name;stat=Path('/proc/'+str(launch['pid'])+'/stat');alive=False
if stat.exists():
 fields=stat.read_text().split();alive=fields[2]!='Z' and fields[21]==launch['process_start_ticks']
status='RUNNING' if alive else 'EXIT_WITHOUT_RECEIPT';details={}
if (root/'failure.json').exists():status='INFRA_FAIL';details={'error_type':json.loads((root/'failure.json').read_text())['error_type']}
elif (root/'receipt.json').exists():
 v=json.loads((root/'receipt.json').read_text());status=v['status'];details={k:v[k] for k in ('task_id','judgments','controller_end_to_end_seconds','model_activity_seconds') if k in v}
 details['arms']={p.stem[4:]:json.loads(p.read_text())['outcome'] for p in root.glob('arm-*.json')}
print(json.dumps({'run_id':name,'alive':alive,'status':status,**details}))
'''


def snapshot(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(path)


def continuation_attempts(previous, manifest, launch_log):
    """Only resume a refused, zero-model dirty-source launch; never a failed role."""
    if (previous['status']!='STOPPED_PRESERVED_NO_AUTOMATIC_RETRY' or
        previous['manifest_sha256']!=manifest['manifest_sha256'] or previous['automatic_retry'] is not False):
        raise ValueError('Explicit unchanged stopped batch required')
    attempts=previous['attempts']
    if not attempts or attempts[-1].get('run_id') or attempts[-1]['status']!='LAUNCHING':
        raise ValueError('A started or infrastructure-failed model attempt cannot be replayed by continuation')
    if 'RuntimeError: Commit and validate source before paid execution' not in launch_log:
        raise ValueError('Missing exact pre-spend dirty-source refusal evidence')
    modes=previous.get('execution_modes',['execute','sensitivity'])
    expected=[(tid,mode) for tid in previous['planned_tasks'] for mode in modes]
    reused=previous.get('reused_attempts',[])+attempts[:-1]
    actual=[(a['task_id'],a['mode']) for a in reused+[attempts[-1]]]
    if actual!=expected[:len(actual)] or len(actual)>len(expected):
        raise ValueError('Continuation must preserve the exact task/mode prefix without replay')
    for a in reused:
        wanted='MAIN_TASK_COMPLETED' if a['mode']=='execute' else 'FULL_TOOL_TRACE_SENSITIVITY_COMPLETED'
        if not a.get('run_id') or a['status']!=wanted or a.get('alive') is not False:
            raise ValueError('Only verified completed, inactive runs can be reused')
    return copy.deepcopy(reused)


def launch(mode,task,source_run,folder,manifest_path):
    argv=[sys.executable,'scripts/run_p6_main.py',mode,'--task',task,'--detach','--manifest',str(manifest_path)]
    if source_run:argv+=['--reuse-run',source_run]
    result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=120)
    (folder/(task+'-'+mode+'-launch.private.log')).write_bytes(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Launch refused; no automatic replay: '+task+' '+mode)
    return json.loads(result.stdout)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tasks',nargs='+');p.add_argument('--execute-only',action='store_true')
    p.add_argument('--manifest',type=Path,default=ROOT/'configs/benchmark-p6-v9.json')
    p.add_argument('--continue-batch',type=Path,help='Explicit continuation of a preserved pre-spend dirty-source refusal; reuses completed candidates')
    args=p.parse_args();manifest=json.loads(args.manifest.read_text())
    tasks=args.tasks or manifest['smoke_tasks']+[t['task_id'] for t in manifest['tasks'] if t['task_id'] not in manifest['smoke_tasks']]
    if len(tasks)!=len(set(tasks)) or not set(tasks)<={t['task_id'] for t in manifest['tasks']}:raise ValueError('Distinct frozen task identities required')
    modes=['execute'] if args.execute_only else ['execute','sensitivity']
    reused=[];continuation=None
    if args.continue_batch:
        path=args.continue_batch.resolve()
        if not path.is_relative_to((ROOT/'.local-workbench/benchmark/main-batches').resolve()):raise ValueError('Continuation evidence must stay in project batch state')
        raw=path.read_bytes();previous=json.loads(raw)
        if tasks!=previous['planned_tasks'] or modes!=previous.get('execution_modes',['execute','sensitivity']):raise ValueError('Task order/modes cannot change in continuation')
        tail=previous['attempts'][-1]
        if tail['task_id'] not in tasks or tail['mode'] not in modes:raise ValueError('Unknown refused task/mode')
        log=path.parent/(tail['task_id']+'-'+tail['mode']+'-launch.private.log')
        log_bytes=log.read_bytes();reused=continuation_attempts(previous,manifest,log_bytes.decode('utf-8'))
        for a in reused:
            query=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',QUERY,a['run_id']],timeout=30)
            if query.returncode:raise RuntimeError('Cannot independently verify preserved run')
            actual=json.loads(query.stdout)
            if actual['alive'] or actual['status']!=a['status']:raise RuntimeError('Preserved completion no longer matches authoritative evidence')
        continuation={'batch_index':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(raw).hexdigest(),'refused_launch_log_sha256':hashlib.sha256(log_bytes).hexdigest(),'reason':'EXPLICIT_ZERO_MODEL_DIRTY_SOURCE_CONTINUATION_NO_CANDIDATE_REPLAY'}
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():raise RuntimeError('Commit source before starting a finite batch')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    folder=ROOT/'.local-workbench/benchmark/main-batches'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');folder.mkdir(parents=True)
    value={'status':'RUNNING','manifest_sha256':manifest['manifest_sha256'],'manifest_file':str(args.manifest.resolve().relative_to(ROOT)),'source_commit':head,'planned_tasks':tasks,'attempts':[],
           'automatic_retry':False,'model_identity_substitution':False,'started_unix':time.time(),'execution_modes':modes,'reused_attempts':reused,'continuation_of':continuation}
    path=folder/'batch-index.private.json';snapshot(path,value)
    try:
        for task in tasks:
            source_run=next((a['run_id'] for a in reused if a['task_id']==task and a['mode']=='execute'),None)
            for mode in modes:
                if any(a['task_id']==task and a['mode']==mode for a in reused):continue
                if json.loads(args.manifest.read_text())['manifest_sha256']!=manifest['manifest_sha256']:raise RuntimeError('Main manifest changed during the frozen batch')
                # The entry verifies exact executable/entrypoint hashes before
                # spending. Documentation-only commits and identical-tree Git
                # merges may advance HEAD without changing this protocol.
                if shutil.disk_usage(ROOT).free<8*1024**3:raise RuntimeError('Less than 8 GiB host project disk remains; stop before another model role')
                attempt={'task_id':task,'mode':mode,'status':'LAUNCHING'};value['attempts'].append(attempt);snapshot(path,value)
                receipt=launch(mode,task,source_run,folder,args.manifest);attempt.update(receipt);snapshot(path,value)
                if mode=='execute':source_run=receipt['run_id']
                while True:
                    query=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',QUERY,receipt['run_id']],timeout=30)
                    if query.returncode:raise RuntimeError('Unable to verify owned controller; stop without retry')
                    status=json.loads(query.stdout);attempt.update(status);snapshot(path,value)
                    if not status['alive']:
                        expected='MAIN_TASK_COMPLETED' if mode=='execute' else 'FULL_TOOL_TRACE_SENSITIVITY_COMPLETED'
                        if status['status']!=expected:raise RuntimeError('Preserved failed attempt stops batch: '+task+' '+mode+' '+status['status'])
                        print(json.dumps({'task_id':task,'mode':mode,'run_id':receipt['run_id'],'status':status['status'],'arms':status.get('arms',{})}),flush=True)
                        break
                    time.sleep(5)
        value['status']='FINITE_BATCH_COMPLETED'
    except BaseException as error:
        value.update(status='STOPPED_PRESERVED_NO_AUTOMATIC_RETRY',error_type=type(error).__name__)
        raise
    finally:
        value['finished_unix']=time.time();snapshot(path,value)
        print(json.dumps({'batch_index':str(path),'status':value['status']}),flush=True)


if __name__=='__main__':main()
