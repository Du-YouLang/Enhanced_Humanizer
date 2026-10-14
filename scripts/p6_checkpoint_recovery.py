"""Conservative, append-only continuation policy for one interrupted P6 role."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def remaining_limits(worker, requests, scope, role_seconds, role_requests,
                     original_activity_upper, activity_cap):
    if worker.get('status') != 'INFRA_RETRY_PENDING':
        raise ValueError('Only the explicitly authorized network interruption may continue')
    spent = max(worker['wall_seconds'], worker['elapsed_seconds'])
    if not math.isfinite(spent) or spent < 0:
        raise ValueError('Missing original role time')
    if type(original_activity_upper) is not int or original_activity_upper < spent:
        raise ValueError('Conservative original activity debit required')
    count = sum(row['experiment'] == scope for row in requests)
    value = {'role_seconds_remaining': math.floor(role_seconds-spent),
             'role_requests_already_reserved': count,
             'role_requests_remaining': role_requests-count,
             'activity_seconds_remaining': activity_cap-original_activity_upper,
             'original_activity_debit_seconds': original_activity_upper,
             'scope': scope, 'recovery_kind': 'WORKSPACE_CHECKPOINT_NEW_DSH_SESSION'}
    if min(value[k] for k in ('role_seconds_remaining', 'role_requests_remaining',
                              'activity_seconds_remaining')) <= 0:
        raise ValueError('No remaining authorized allowance; never reset a role')
    return value


def inventory(root):
    """Hash private original bytes, including Git and trajectories; never write there."""
    root = Path(root)
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and not p.is_symlink()}


class Stages:
    """Completed stages are reused; an uncertain started model is never repeated."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(exist_ok=True)

    def run(self, name, action):
        done = self.root/(name+'.completed.json')
        start = self.root/(name+'.started.json')
        if done.exists():
            return json.loads(done.read_bytes())['value']
        with start.open('x', encoding='utf-8') as f:
            json.dump({'stage': name, 'automatic_model_replay': False}, f)
            f.flush()
            __import__('os').fsync(f.fileno())
        value = action()
        with done.open('x', encoding='utf-8') as f:
            json.dump({'stage': name, 'value': value}, f, sort_keys=True)
            f.flush()
            __import__('os').fsync(f.fileno())
        return value
