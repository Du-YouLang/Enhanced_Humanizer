"""Accounting setup only; all continuation/model code runs as workbench."""
import os,pwd,json,sys,subprocess
from pathlib import Path
from p6_io_accounting import group_path
from p6_refresh_observer import owner_identity

def main(v):
    if os.getuid()!=0:raise ValueError('Root only for accounting setup')
    rid=v['continuation_id'];root=Path('/opt/workbench/benchmark/private/model-refresh')/rid
    d=json.loads((root/'continuation.json').read_bytes())
    if d['continuation_id']!=rid:raise ValueError('Checkpoint identity mismatch')
    group=group_path('refresh-20261126T060538Z');group.mkdir(exist_ok=True);u=pwd.getpwnam('workbench')
    for p in (group,group/'cgroup.procs',group/'cgroup.threads',group/'cgroup.subtree_control'):os.chown(p,u.pw_uid,u.pw_gid)
    def drop():
        (group/'cgroup.procs').write_text(str(os.getpid()));os.initgroups(u.pw_name,u.pw_gid);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
    if v['action']=='controls':
        env=os.environ|{'HOME':u.pw_dir,'USER':u.pw_name,'LOGNAME':u.pw_name}
        child=subprocess.Popen(['/opt/workbench/.venv-linux/bin/python','-B',str(Path(__file__).with_name('p6_refresh_continue_linux.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,preexec_fn=drop,env=env)
        out,err=child.communicate(json.dumps(v).encode());sys.stderr.buffer.write(err)
        if child.returncode:raise RuntimeError('Actual accounting-group resume controls failed')
        return json.loads(out)
    marker=root/'launch.json'
    if marker.exists():raise ValueError('Existing launch must be reconciled, never replayed')
    env=os.environ|{'HOME':u.pw_dir,'USER':u.pw_name,'LOGNAME':u.pw_name}
    with (root/'controller.private.log').open('xb')as log:
        os.fchown(log.fileno(),u.pw_uid,u.pw_gid)
        child=subprocess.Popen(['/opt/workbench/.venv-linux/bin/python','-B',str(Path(__file__).with_name('p6_refresh_continue_linux.py'))],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,preexec_fn=drop,env=env,start_new_session=True)
        child.stdin.write(json.dumps(v).encode());child.stdin.close()
    uid=next(x for x in Path('/proc',str(child.pid),'status').read_text().splitlines()if x.startswith('Uid:'))
    if any(int(x)!=u.pw_uid for x in uid.split()[1:]):raise ValueError('Root privileges not dropped')
    value={'status':'DISPATCHED_LIVE_VERIFICATION_REQUIRED','owner':owner_identity(child.pid),'controller_uid':u.pw_uid,'continuation_id':rid,'original_run':'refresh-20261126T060538Z','automatic_replay':False,'root_model_calls':0}
    with marker.open('x')as f:json.dump(value,f,indent=2)
    os.chown(marker,u.pw_uid,u.pw_gid);return value
if __name__=='__main__':
    from p1_broker import protect_memory
    protect_memory();print(json.dumps(main(json.load(sys.stdin))))
