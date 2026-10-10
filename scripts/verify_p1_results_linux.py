"""Revalidate saved real P1 repositories without any model call or credential input."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from p1_acceptance import DESIGN_CHECK,verification_command
from p1_broker import protect_memory
from p1_experiment_linux import BASE,TESTS,git
from export_codex_usage import collect


def main():
    protect_memory()
    tick=time.perf_counter()
    rows=[]
    for path in sorted((BASE/'evidence').glob('p1-*.json')):
        record=json.loads(path.read_text())
        if record.get('kind')!='REAL_MODEL_EXPERIMENT' or record.get('verdict')!='PASS':continue
        run=record['run_id'];work=BASE/'runs'/run/'worktree'
        checks={'base_commit':record['base_commit']=='561bd401a218246f5a823e8e3e0f0eea374163aa',
                'head_commit':git(work,'rev-parse','HEAD')==record['head_commit'],
                'clean_worktree':not git(work,'status','--porcelain'),
                'frozen_test_unchanged':(work/'test_weighted_stats.py').read_text()==TESTS}
        tested=subprocess.run(verification_command(work,[sys.executable,'-m','unittest','-v'],BASE/'tmp'/('verify-'+run)),
                              cwd=work,text=True,capture_output=True,timeout=15)
        checks['sandboxed_public_tests']=tested.returncode==0
        if record['mode'] in ('flame','relay'):
            design=subprocess.run(verification_command(work,[sys.executable,'-c',DESIGN_CHECK],BASE/'tmp'/('verify-'+run)),
                                  cwd=work,text=True,capture_output=True,timeout=15)
            checks['sandboxed_redesign_tests']=design.returncode==0
        codex=[row for epic in (BASE/'state/humanize/epics').glob('*'+run+'*') for row in collect(epic)]
        if any(t['harness']=='codex' for t in record['turns']):
            checks['observed_codex_model']=bool(codex) and all(c['model_id']=='gpt-6.1-sol' for c in codex)
        if record['mode']=='relay':
            result=record['result'];handoffs=result['result']['handoffs']
            checks['pause_resume']=result['paused'] and result['result']['resumed'] and result['result']['next_step']==2
            checks['distinct_sessions']=len(record['turns'])==2 and record['turns'][0]['session_id']!=record['turns'][1]['session_id']
            checks['commit_handoff_chain']=len(handoffs)==2 and handoffs[0]['base_commit']==record['base_commit'] and handoffs[0]['head_commit']==handoffs[1]['base_commit'] and handoffs[1]['head_commit']==record['head_commit']
        # A second immutable result references the original; no rewrite of historical experiment records.
        rows.append({'run_id':run,'checks':checks,'verdict':'PASS' if all(checks.values()) else 'FAIL',
                     'experiment_record_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'codex_usage':codex,
                     'commits':git(work,'log','--format=%H %s',record['base_commit']+'..HEAD').splitlines(),
                     'public_test_output':tested.stderr,'verification_network':'DENIED','verification_workspace':'READ_ONLY'})
    value={'kind':'INDEPENDENT_REVALIDATION_NO_MODEL_CALL','paid_requests':0,'elapsed_seconds':round(time.perf_counter()-tick,6),
           'results':rows,'verdict':'PASS' if len(rows)==5 and all(r['verdict']=='PASS' for r in rows) else 'FAIL'}
    (BASE/'evidence/p1-independent-verification.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value))
    return 0 if value['verdict']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
