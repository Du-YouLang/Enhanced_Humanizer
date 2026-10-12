"""Finite serial main matrix and same-pool reviews; stop on infrastructure failure.

This is a current authorized experiment controller, never a scheduler or retry
service. Its attempt index is authoritative even when a task does not finish.
"""
import argparse
from datetime import datetime,timezone
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


def launch(mode,task,source_run,folder,manifest_path):
    argv=[sys.executable,'scripts/run_p6_main.py',mode,'--task',task,'--detach','--manifest',str(manifest_path)]
    if source_run:argv+=['--reuse-run',source_run]
    result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=120)
    (folder/(task+'-'+mode+'-launch.private.log')).write_bytes(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Launch refused; no automatic replay: '+task+' '+mode)
    return json.loads(result.stdout)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tasks',nargs='+');p.add_argument('--execute-only',action='store_true')
    p.add_argument('--manifest',type=Path,default=ROOT/'configs/benchmark-p6-v5.json')
    args=p.parse_args();manifest=json.loads(args.manifest.read_text())
    tasks=args.tasks or manifest['smoke_tasks']+[t['task_id'] for t in manifest['tasks'] if t['task_id'] not in manifest['smoke_tasks']]
    if len(tasks)!=len(set(tasks)) or not set(tasks)<={t['task_id'] for t in manifest['tasks']}:raise ValueError('Distinct frozen task identities required')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    folder=ROOT/'.local-workbench/benchmark/main-batches'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');folder.mkdir(parents=True)
    value={'status':'RUNNING','manifest_sha256':manifest['manifest_sha256'],'manifest_file':str(args.manifest.resolve().relative_to(ROOT)),'source_commit':head,'planned_tasks':tasks,'attempts':[],
           'automatic_retry':False,'model_identity_substitution':False,'started_unix':time.time()}
    path=folder/'batch-index.private.json';snapshot(path,value)
    try:
        for task in tasks:
            source_run=None
            for mode in ('execute',) if args.execute_only else ('execute','sensitivity'):
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
