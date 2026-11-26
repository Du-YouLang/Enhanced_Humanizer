"""Trusted accounting-group setup only. Exec the experiment as workbench, never root."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time
from p6_io_accounting import group_path
from p1_broker import protect_memory


def main(payload):
    if os.getuid()!=0:raise ValueError('Accounting setup needs root; no model is run in this process')
    controls=payload['mode']=='controls';group=group_path(payload['run_id'],controls)
    group.mkdir();account=pwd.getpwnam('workbench')
    for p in (group,group/'cgroup.procs',group/'cgroup.threads',group/'cgroup.subtree_control'):
        os.chown(p,account.pw_uid,account.pw_gid)
    if not (group/'io.pressure').exists():raise ValueError('Per-group IO pressure unavailable')
    def drop():
        (group/'cgroup.procs').write_text(str(os.getpid()))
        os.initgroups(account.pw_name,account.pw_gid);os.setgid(account.pw_gid);os.setuid(account.pw_uid)
    env=os.environ|{'HOME':account.pw_dir,'USER':account.pw_name,'LOGNAME':account.pw_name}
    command=['/opt/workbench/.venv-linux/bin/python','-B',payload['folder']+'/p6_refresh_linux.py']
    if controls:
        child=subprocess.Popen(command,preexec_fn=drop,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out,err=child.communicate(json.dumps(payload).encode())
        sys.stdout.buffer.write(out);sys.stderr.buffer.write(err);return child.returncode
    root=Path('/opt/workbench/benchmark/private/model-refresh/launches');root.mkdir(exist_ok=True);os.chown(root,account.pw_uid,account.pw_gid)
    marker=root/(payload['run_id']+'.json')
    if marker.exists():raise ValueError('Existing launch; reconcile instead of replay')
    with (root/(payload['run_id']+'.private.log')).open('xb') as log:
        os.fchown(log.fileno(),account.pw_uid,account.pw_gid)
        child=subprocess.Popen(command,preexec_fn=drop,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        child.stdin.write(json.dumps(payload).encode());child.stdin.close()
        from p6_refresh_observer import owner_identity
        owner=owner_identity(child.pid)
        status=Path('/proc')/str(child.pid)/'status'
        uid_line=next(r for r in status.read_text().splitlines() if r.startswith('Uid:'))
        if any(int(v)!=account.pw_uid for v in uid_line.split()[1:]):raise ValueError('Controller privileges not dropped')
        value={'status':'DISPATCHED_OWNER_HEARTBEAT_VERIFICATION_REQUIRED','owner':owner,'controller_uid':account.pw_uid,
            'io_accounting_group':str(group),'run_id':payload['run_id'],'folder':payload['folder'],
            'plan_sha256':payload['plan']['plan_sha256'],'started_unix':time.time(),'automatic_model_replay':False,
            'root_setup_model_calls':0,'resource_limits_or_global_settings_changed':False}
        with marker.open('x') as f:json.dump(value,f,indent=2)
        os.chown(marker,account.pw_uid,account.pw_gid);print(json.dumps(value));return 0


if __name__=='__main__':
    protect_memory();sys.exit(main(json.load(sys.stdin)))
