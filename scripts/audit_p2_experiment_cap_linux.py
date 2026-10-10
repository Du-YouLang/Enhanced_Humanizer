"""Actual controller-wide cancellation preserves every candidate; zero inference fault fixture."""

import json
import time
from pathlib import Path

from p1_broker import protect_memory
from p1_budget import Ledger
from p2_candidates import BASE,digest,exclusive_json
from p2_experiment_linux import pool_run


def main():
    protect_memory();real=BASE/'state/p2-budget/ledger.json';before=digest(real.read_bytes())
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());run_id='p2-control-experiment-cap-'+stamp
    lock=json.loads(next((BASE/'runs').glob('p2-n1-*/frozen-pool.json')).read_text())['env_hash']
    mock=Ledger(BASE/'state'/run_id/'offline-only-ledger.json',phase='P2',requests=1,cash_nano=2_000_000_000)
    record=pool_run({'run_id':run_id,'n':3,'concurrency':1,'runtime_lock_sha256':lock,'offline_control':'sleep'},
                    'NO_REAL_API_TRANSPORT',mock,time.monotonic()+1.5)
    pool=json.loads(Path(record['pool_path']).read_text())
    assert record['flow_stop']['state']=='TIMEOUT' and len(pool['candidates'])==3
    assert all(c['verdict']=='TIMEOUT' for c in pool['candidates'])
    assert not mock.path.exists() and digest(real.read_bytes())==before
    report={'verdict':'PASS','kind':'ZERO_MODEL_CONTROLLER_EXPERIMENT_CAP','run_id':run_id,
            'preserved_candidates':3,'candidate_statuses':record['candidate_verdicts'],'flow_stop':record['flow_stop'],
            'model_requests_added':0,'real_ledger_sha256_before':before,'real_ledger_sha256_after':digest(real.read_bytes()),
            'elapsed_seconds':record['elapsed_seconds']}
    exclusive_json(BASE/'evidence'/('p2-experiment-cap-'+stamp+'.json'),report);print(json.dumps(report))


if __name__=='__main__':main()
