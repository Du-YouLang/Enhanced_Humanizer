"""Per-run 30-second local observer. No recovery, providers or ledger writes."""
import hashlib
import json
import os
from pathlib import Path
import threading
import time


def owner_identity(pid):
    p=Path('/proc')/str(pid)
    return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'process_start_ticks':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],
        'command_sha256':hashlib.sha256(p.joinpath('cmdline').read_bytes()).hexdigest()}


class Observer:
    def __init__(self,root,plan,ledger):
        self.root,self.plan,self.ledger=Path(root),plan,Path(ledger)
        self.owner=owner_identity(os.getpid());self.roles={};self.closed=0
        self.state='RUNNING';self.lock=threading.RLock();self.stop=threading.Event()
        self.thread=threading.Thread(target=self.loop,name='refresh-readonly-observer',daemon=True)
    def start(self):
        self.root.mkdir(parents=True,exist_ok=True)
        with (self.root/'owner.json').open('x') as h:json.dump(dict(self.owner,plan_sha256=self.plan['plan_sha256']),h,indent=2)
        self.flush();self.thread.start()
    def role(self,scope,state):
        with self.lock:
            self.roles[scope]={'status':state,'checked_unix':time.time()}
            self.flush()
    def flush(self):
        with self.lock:
            raw=self.ledger.read_bytes();value=json.loads(raw)
            snapshot={'status':self.state,'checked_unix':time.time(),'owner':self.owner,
                'plan_sha256':self.plan['plan_sha256'],'closed_result_cells':self.closed,'expected_result_cells':144,
                'roles':dict(self.roles),'ledger_sha256':hashlib.sha256(raw).hexdigest(),
                'requests':len(value['requests']),'subscription_reservations':len(value['codex_turns']),
                'cash_bound_usd':value['cash_bound_nano']/1e9,'aggregate_caps':value['aggregate_caps'],
                'actual_cash':'unavailable','provider_dispatches_by_observer':0,'automatic_recovery':False}
            p=self.root/'heartbeat.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(snapshot,indent=2));os.replace(tmp,p)
    def loop(self):
        while not self.stop.wait(30):
            try:self.flush()
            except (OSError,ValueError) as error:
                with (self.root/'observer-errors.log').open('a') as h:h.write(str(time.time())+' '+type(error).__name__+'\n')
    def close(self,state):
        self.state=state;self.stop.set();self.thread.join(timeout=2);self.flush()
