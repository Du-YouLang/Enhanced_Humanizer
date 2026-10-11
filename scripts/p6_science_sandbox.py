"""Run scientific submissions without exposing the parent's oracle or credentials.

This is a grading boundary around the existing Humanize fence, not a Coding
Harness. Candidate output is untrusted data; only the separate parent grades it.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import uuid

from p6_prepare_linux import BASE
from p6_evaluate_linux import namespace, task_path, validate_source_links


def process_usage(leader):
    """Observe descendants from the controller's host PID namespace, including threads."""
    rows = {}
    for file in Path('/proc').glob('[0-9]*/status'):
        try:
            fields = dict(line.split(':',1) for line in file.read_text().splitlines() if ':' in line)
            rows[int(file.parent.name)] = (int(fields['PPid']),int(fields.get('VmRSS','0 kB').split()[0]),int(fields.get('Threads','1')))
        except (OSError,KeyError,ValueError): continue
    descendants = {leader}
    while True:
        found = {pid for pid,(parent,_,_) in rows.items() if parent in descendants}
        updated = descendants | found
        if updated == descendants: break
        descendants = updated
    observed = [rows[pid] for pid in descendants if pid in rows]
    return {'rss_kib':sum(r[1] for r in observed),'processes':len(observed),'threads':sum(r[2] for r in observed)}


def stop_tree(process):
    # unshare --kill-child kills the PID namespace init when its wrapper dies;
    # the kernel then kills every member, even descendants that called setsid.
    if process.poll() is not None: return
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: return
    try: process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=5)


def output_inventory(output):
    files={};total=0
    for path in Path(output).rglob('*'):
        if path.is_symlink(): raise ValueError('Scientific output symlinks are refused')
        if path.is_file():
            size=path.stat().st_size;total+=size
            if len(files)>=5000 or size>268435456 or total>512_000_000:
                raise ValueError('Scientific output size/count limit exceeded')
            files[str(path.relative_to(output))]=size
    return files


def execute(source, prefix, worker_program, *, inputs=None, timeout=180,
            gpu=False, rss_limit_mib=10240, cpu_threads=8, pin_one_cpu=False, arguments=()):
    from p1_broker import protect_memory
    from hmz.coganchor.fence import Fence,wrapper
    if os.name != 'posix' or os.getuid() == 0: raise RuntimeError('Native non-root Linux is required')
    protect_memory()
    source,prefix = Path(source).resolve(),Path(prefix).resolve()
    if not source.is_relative_to(BASE) or not prefix.is_relative_to(BASE/'envs'):
        raise ValueError('Scientific source/environment must remain in the project VHD')
    if type(timeout) is not int or not 1<=timeout<=7200 or type(rss_limit_mib) is not int or not 64<=rss_limit_mib<=12288:
        raise ValueError('Finite scientific wall-clock and process-tree RSS limits required')
    if type(cpu_threads) is not int or not 1<=cpu_threads<=8 or type(pin_one_cpu) is not bool:
        raise ValueError('A frozen CPU thread/affinity protocol is required')
    validate_source_links(source)
    root=BASE/'science/private/evaluations'/uuid.uuid4().hex
    root.mkdir(parents=True)
    work=root/'code';shutil.copytree(source,work,symlinks=True,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc'))
    input_dir=root/'inputs';input_dir.mkdir()
    if sum(len(raw) for raw in (inputs or {}).values())>500_000_000: raise ValueError('Input copy limit exceeded')
    for name,raw in (inputs or {}).items():
        target=input_dir/str(task_path(name));target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    output=root/'output';output.mkdir();scratch=root/'tmp';scratch.mkdir();home=root/'home';home.mkdir()
    worker=root/'worker.py';worker.write_text(worker_program)
    canary=root/'withheld-oracle.canary';canary.write_text('non-secret denial probe, outside all candidate grants')
    auth=Path('/opt/workbench/state/codex/auth.json')
    if not auth.is_file(): raise RuntimeError('Existing auth denial target absent; cannot claim tested isolation')
    system_read=tuple(str(p) for p in (Path('/etc/mime.types'),Path('/proc/cpuinfo'),Path('/sys/devices/system/cpu')) if p.exists())
    fence=Fence.of(local='read',user='none',system='none',online=False,workdir=work,home=home,
                   read=(str(prefix),str(input_dir),str(worker),*system_read),write=(str(output),str(scratch)))
    if gpu:
        if not Path('/dev/dxg').exists(): raise RuntimeError('Local WSL GPU device is unavailable')
        fence=replace(fence,read=(*fence.read,'/usr/lib/wsl'),write=(*fence.write,'/dev/dxg'))
    else:
        fence=replace(fence,write=tuple(p for p in fence.write if not p.startswith(('/dev/nvidia','/dev/dri','/dev/dxg'))))
    fence=replace(fence,tmp=str(scratch))
    env={'PATH':str(prefix/'bin')+':/usr/bin:/bin','HOME':str(home),'TMPDIR':str(scratch),
         'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'42','MPLCONFIGDIR':str(scratch/'mpl'),
         'CUDA_CACHE_PATH':str(scratch/'cuda'),'CUPY_CACHE_DIR':str(scratch/'cupy'),
         'JAX_COMPILATION_CACHE_DIR':str(scratch/'jax'),'XLA_PYTHON_CLIENT_PREALLOCATE':'false',
         'OMP_NUM_THREADS':str(cpu_threads),'OPENBLAS_NUM_THREADS':str(cpu_threads),'MKL_NUM_THREADS':str(cpu_threads),
         'CUDA_VISIBLE_DEVICES':'0' if gpu else '', 'WANDB_MODE':'disabled'}
    if gpu:env['LD_LIBRARY_PATH']='/usr/lib/wsl/lib'
    probe='''import json,os,socket,sys
from pathlib import Path
value=json.loads(sys.argv[1]);denied=[];readonly=[]
for p in value['denied']:
 try:Path(p).read_bytes();denied.append('ALLOWED_FAILURE')
 except PermissionError:denied.append('DENIED')
for p in value['readonly']:
 with open(p,'rb') as f:f.read(1)
 try:
  with open(p,'ab'):pass
  readonly.append('ALLOWED_FAILURE')
 except PermissionError:readonly.append('DENIED')
try:socket.create_connection(('127.0.0.1',value['port']),timeout=2).close();network='ALLOWED_FAILURE'
except PermissionError:network='DENIED'
except OSError:network='UNPROVEN'
print(json.dumps({'uid':os.getuid(),'denied':denied,'readonly':readonly,'network':network,
 'cap_eff':next(l.split()[-1] for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('CapEff:')),
 'private_pid_namespace':os.readlink('/proc/self/ns/pid')!=value['parent_namespace']}))
'''
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen(1)
        spec={'denied':[str(canary),str(auth)],'readonly':[str(worker),str(prefix/'conda-meta/history')],
              'port':listener.getsockname()[1],'parent_namespace':os.readlink('/proc/self/ns/pid')}
        checked=subprocess.run(namespace([*wrapper(fence),str(prefix/'bin/python'),'-B','-c',probe,json.dumps(spec)]),
                               cwd=work,env=env,capture_output=True,text=True,timeout=20)
    (root/'probe.private.log').write_text(checked.stdout+checked.stderr)
    if checked.returncode: raise RuntimeError('Scientific fence probe failed: '+str(root))
    isolation=json.loads(checked.stdout)
    if (isolation['uid']==0 or isolation['cap_eff']!='0000000000000000' or not isolation['private_pid_namespace']
            or isolation['denied']!=['DENIED']*2 or isolation['readonly']!=['DENIED']*2 or isolation['network']!='DENIED'):
        raise RuntimeError('Scientific isolation probe did not deny access: '+str(root))
    command=['prlimit','--fsize=268435456','--nofile=1024','--',
             *namespace([*wrapper(fence),str(prefix/'bin/python'),'-B',str(worker),str(work),str(input_dir),str(output),*arguments])]
    if pin_one_cpu:command=['taskset','-c',str(min(os.sched_getaffinity(0))),*command]
    lock_path=BASE/'science/private/gpu-evaluation.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
    peak={'rss_kib':0,'processes':0,'threads':0};reason=None
    import fcntl
    queue_started=time.perf_counter()
    with lock_path.open('a+b') as lock:
        if gpu:
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.perf_counter()-queue_started>7200:raise TimeoutError('Local GPU queue limit (7200 seconds) reached')
                    time.sleep(.2)
        queue_wait_seconds=time.perf_counter()-queue_started
        tick=time.perf_counter()
        with (root/'stdout.private.log').open('wb') as out,(root/'stderr.private.log').open('wb') as err:
            process=subprocess.Popen(command,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
            try:
                while process.poll() is None:
                    usage=process_usage(process.pid)
                    peak={k:max(peak[k],v) for k,v in usage.items()}
                    if usage['rss_kib']>rss_limit_mib*1024:reason='PROCESS_TREE_RSS_LIMIT'
                    elif usage['processes']>64 or usage['threads']>512:reason='PROCESS_TREE_COUNT_LIMIT'
                    elif time.perf_counter()-tick>timeout:reason='TIMEOUT'
                    try:output_inventory(output)
                    except ValueError:reason='OUTPUT_SIZE_OR_LINK_LIMIT'
                    if reason:stop_tree(process);break
                    time.sleep(.1)
            finally:
                stop_tree(process)
        elapsed=time.perf_counter()-tick
    try:inventory=output_inventory(output)
    except ValueError:inventory={};reason=reason or 'OUTPUT_SIZE_OR_LINK_LIMIT'
    result={'status':reason or ('COMPLETED_UNGRADED' if process.returncode==0 else 'SUBMISSION_FAILED'),
            'exit_code':process.returncode,'elapsed_seconds':elapsed,'peak_process_tree':peak,
            'process_tree_rss_limit_mib':rss_limit_mib,'timeout_seconds':timeout,'gpu':gpu,
            'cpu_threads':cpu_threads,'one_cpu_affinity':pin_one_cpu,
            'output':str(output),'output_inventory':inventory,'queue_wait_seconds':queue_wait_seconds,
            'gpu_queue_limit_seconds':7200 if gpu else 0,
            'evidence_root':str(root),'isolation':isolation,'model_requests':0,
            'output_trust':'UNTRUSTED_DATA_ONLY_PARENT_MUST_GRADE'}
    (root/'execution-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
