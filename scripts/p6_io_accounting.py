"""Scoped kernel PSI accounting; raw elapsed remains the primary time metric."""
import os
from pathlib import Path
import re
import time


def group_path(run_id,controls=False):
    if not re.fullmatch(r'refresh-[0-9]{8}T[0-9]{6}Z',run_id):raise ValueError('Exact fresh run required')
    return Path('/sys/fs/cgroup/non-systemd')/('eh-'+run_id+('-controls' if controls else ''))


def pressure(text):
    rows={}
    for line in text.splitlines():
        parts=line.split();kind=parts[0] if parts else ''
        if kind in ('some','full'):
            fields=dict(p.split('=',1) for p in parts[1:])
            if not fields.get('total','').isdigit():raise ValueError('Finite microsecond counter required')
            rows[kind]=int(fields['total'])
    if set(rows)!=set(('some','full')) or rows['full']>rows['some']:raise ValueError('Incomplete PSI counter')
    return rows


def correction(start,end,elapsed_seconds):
    some=(end['some']-start['some'])/1e6;full=(end['full']-start['full'])/1e6
    if not 0<=full<=some or full>elapsed_seconds:raise ValueError('Counter/window mismatch; do not clamp or invent zero')
    return {'raw_elapsed_seconds':elapsed_seconds,'full_local_io_stall_seconds':full,
        'some_local_io_stall_seconds':some,'io_adjusted_elapsed_estimate_seconds':elapsed_seconds-full,
        'counter_start_microseconds':start,'counter_end_microseconds':end,
        'subtracts_only_full_not_some_or_summed_process_delays':True,
        'parallel_stalls_deduplicated_by_kernel':True,'primary_metric':'RAW_ELAPSED',
        'interpretation':'Observed local full-stall adjustment; NOT a causal zero-IO counterfactual. Remote generation/network can overlap local stalls.',
        'source':'https://docs.kernel.org/accounting/psi.html'}


def require_group(run_id,controls=False):
    root=group_path(run_id,controls)
    expected='0::'+str(root).removeprefix('/sys/fs/cgroup')
    if os.getuid()==0 or Path('/proc/self/cgroup').read_text().strip()!=expected:
        raise ValueError('Non-root controller must already be in its exact accounting-only group')
    if not (root/'io.pressure').exists():raise ValueError('Per-group PSI unavailable')
    return root


class Epoch:
    def __init__(self,root,name):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',name):raise ValueError('Safe unique epoch name required')
        self.root,self.group=Path(root),Path(root)/name;self.measurement=None
    def __enter__(self):
        self.group.mkdir();(self.group/'cgroup.procs').write_text(str(os.getpid()))
        self.wall_start=time.time_ns();self.tick=time.perf_counter_ns();self.start=pressure((self.group/'io.pressure').read_text());return self
    def __exit__(self,kind,error,tb):
        try:
            end=pressure((self.group/'io.pressure').read_text());end_tick=time.perf_counter_ns();end_wall=time.time_ns();elapsed=(end_tick-self.tick)/1e9
            self.measurement=correction(self.start,end,elapsed)
            self.measurement.update(cgroup=str(self.group),partial_epoch=kind is not None,monotonic_ns_start=self.tick,monotonic_ns_end=end_tick,wall_ns_start=self.wall_start,wall_ns_end=end_wall,wall_minus_monotonic_seconds=(end_wall-self.wall_start)/1e9-elapsed)
        finally:(self.root/'cgroup.procs').write_text(str(os.getpid()))
        # Keep empty accounting groups/counters for audit; no process is killed.
        self.measurement['remaining_process_ids']=(self.group/'cgroup.procs').read_text().split()
        return False


def actual_controls(root):
    import tempfile
    rows=[]
    with tempfile.TemporaryDirectory(prefix='refresh-io-control-',dir='/opt/workbench/tmp') as temp:
        for name in ('cpu','fsync'):
            with Epoch(root,'io-control-'+name) as epoch:
                if name=='cpu':
                    until=time.perf_counter()+.5
                    while time.perf_counter()<until:sum(range(1000))
                else:
                    with (Path(temp)/'four-mib.tmp').open('wb') as f:
                        for _ in range(16):f.write(b'x'*262144);f.flush();os.fsync(f.fileno())
            rows.append({'kind':name,**epoch.measurement})
    if rows[1]['full_local_io_stall_seconds']<=0:raise ValueError('Synchronous I/O control produced no measurable stall; calibration incomplete')
    return {'status':'PASS_ACTUAL_CGROUP_IO_CONTROLS','uid':os.getuid(),'rows':rows,'providers':0,'candidate_executions':0,'global_kernel_settings_changed':False}
