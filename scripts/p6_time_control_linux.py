"""Zero-model actual role descriptors, Harness limits and OS fence controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import p6_main_runtime_linux as main
import p6_runtime_linux as shared
from p6_main_budget import MainLedger,authorization,task_limits
from p6_gate_policy import GENERATION_RULES
from p2_candidates import exclusive_json


def check(root,budget,manifest):
    if os.getuid()==0 or not root.resolve().is_relative_to(shared.BASE/'private'):
        raise ValueError('Non-root fresh project-private time control required')
    root.mkdir();_,fingerprint=authorization(budget)
    ledger=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
    before=hashlib.sha256(ledger.read_bytes()).hexdigest();results={}
    cases=[('native-ds','dsh','builder','native_driver'),('pool-ds','dsh','builder','flow'),
           ('native-sol','codex','builder','native_driver'),('reviewer','codex','reviewer','flow'),
           ('judge','codex','verifier','flow')]
    for tid in ('BIP-black-2','SCI-GRANGER-GPU'):
        frozen=next(t for t in manifest['tasks'] if t['task_id']==tid)
        payload={'task':frozen,'budget':budget,'manifest':manifest};limits=task_limits(budget,frozen)
        if frozen['family']=='scientific':
            from p6_science_main_linux import task as science_task
            task=science_task(payload);task['prompt']+='\n'+GENERATION_RULES
            if 'limited to 1200 seconds' not in task['prompt']:
                raise ValueError('Scientific prompt still carries an old role cap')
        else:task=main.public_task(payload)
        family_root=root/tid;family_root.mkdir();(family_root/'control').mkdir()
        (family_root/'control/canary').write_text('non-secret controller denial probe')
        shared.ACTIVE.clear()
        shared.ACTIVE.update(root=family_root,task=task,payload=payload,key='offline-no-key',
            ledger=MainLedger(ledger,budget),main_phase=True,defer_hidden=True,
            generation_seconds=limits['role_seconds'],active_seconds=limits['active_seconds'],
            deadline=time.monotonic()+limits['active_seconds'])
        shared.test_source=main.public_test
        with task['fixture_context'] as url:
            shared.ACTIVE['fixture_url']=url;roles={}
            for name,backend,role,mode in cases:
                descriptor,env=main.job(name,backend,role,mode=mode,offline=True)
                worker=shared.launch(descriptor,env)
                isolation=json.loads((Path(worker['root'])/'isolation.json').read_text())
                passed=(descriptor['role_seconds']==limits['role_seconds']
                        and worker['configured_role_seconds']==limits['role_seconds']
                        and worker['effective_harness_turn_seconds']==limits['role_seconds']
                        and worker['status']=='COMPLETED' and worker['kind']=='ZERO_MODEL_CONTROL'
                        and not worker['turns'] and isolation['verdict']=='PASS')
                roles[name]={'status':'PASS' if passed else 'FAIL','role':role,'backend':backend,
                    'descriptor_seconds':descriptor['role_seconds'],
                    'effective_harness_seconds':worker['effective_harness_turn_seconds'],
                    'isolation_verdict':isolation['verdict'],
                    'worker_sha256':hashlib.sha256((Path(worker['root'])/'controller-outcome.json').read_bytes()).hexdigest()}
            shared.ACTIVE['deadline']=time.monotonic()+3
            remainder,_=main.job('remaining-time','dsh','builder',offline=True)
            remaining_ok=1<=remainder['role_seconds']<=3
        results[tid]={'limits':limits,'roles':roles,'remaining_deadline_clamped':remaining_ok}
    after=hashlib.sha256(ledger.read_bytes()).hexdigest()
    passed=(before==after and all(v['remaining_deadline_clamped'] and all(r['status']=='PASS' for r in v['roles'].values()) for v in results.values()))
    names=['p1_drivers.py','p6_worker_linux.py','p6_runtime_linux.py','p6_main_runtime_linux.py',
           'p6_main_budget.py','p6_science_main_linux.py','p6_time_control_linux.py']
    proof={'status':'PASS' if passed else 'FAIL','evidence_kind':'ZERO_MODEL_ACTUAL_HARNESS_LIMIT_AND_FENCE_CONTROL',
           'model_requests':0,'uid':os.getuid(),'budget_authorization_sha256':fingerprint,
           'ledger_sha256_before':before,'ledger_sha256_after':after,'results':results,
           'source_sha256':{n:hashlib.sha256((Path('/opt/workbench/source')/n).read_bytes()).hexdigest() for n in names}}
    exclusive_json(root/'receipt.json',proof);return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();payload=json.load(sys.stdin)
    result=check(args.output,payload['budget'],payload['manifest'])
    print(json.dumps({'status':result['status'],'model_requests':0,'results':result['results'],
                      'ledger_unchanged':result['ledger_sha256_before']==result['ledger_sha256_after']}))
    raise SystemExit(0 if result['status']=='PASS' else 1)
