"""Trusted fixture setup and independent acceptance, not a Coding Harness."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from hmz.sdk import Hmz


def main():
    run_id = sys.argv[1]
    root = Path('/opt/workbench/runs') / run_id
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.STDOUT).decode().strip()
    git('init','-b','run/p0/codex')
    git('config','user.name','Workbench Demo')
    git('config','user.email','demo@example.invalid')
    (root/'calc.py').write_text('def subtract(a, b):\n    return a + b\n')
    (root/'test_calc.py').write_text('import unittest\nfrom calc import subtract\nclass TestCalc(unittest.TestCase):\n    def test_subtract(self):\n        self.assertEqual(subtract(5, 3), 2)\n        self.assertEqual(subtract(-2, 4), -6)\n        self.assertEqual(subtract(2.5, 1.5), 1.0)\n')
    (root/'.gitignore').write_text('__pycache__/\n.hmz/\n')
    git('add','calc.py','test_calc.py','.gitignore')
    git('commit','-m','Synthetic P0 fixture, failing subtract')
    base = git('rev-parse','HEAD')
    task = 'Fix subtract in calc.py. Read the existing files, edit calc.py, run python -m unittest -v, and create a Git commit with the fix. Do not change test_calc.py. Do not install dependencies or spawn subagents. Finish within one turn; give the commit and test result.'
    tests_hash = hashlib.sha256((root/'test_calc.py').read_bytes()).hexdigest()
    tick=time.perf_counter()
    record={'run_id':run_id,'kind':'REAL_MODEL_CODING','observed_at':datetime.now(timezone.utc).isoformat(),
            'base_commit':base,'model_requested':'gpt-6.1-sol','harness':'Codex via Humanize',
            'cash_api_usd':0,'subscription_usage':'separately metered; unavailable cash conversion',
            'prompt_sha256':hashlib.sha256(task.encode()).hexdigest()}
    try:
        hmz = Hmz(workspace=root)
        result = hmz.run('/opt/workbench/source/flows/p0_coding_demo',task,
                         agents={'builder':'codex/gpt-6.1-sol:low'},
                         budget={'duration':timedelta(seconds=115),'graceful':False}).run()
        record['result']=result
        tested=subprocess.run([sys.executable,'-m','unittest','-v'],cwd=root,capture_output=True,text=True,timeout=10)
        head=git('rev-parse','HEAD')
        record.update(head_commit=head,test_exit_code=tested.returncode,test_stdout=tested.stdout,
                      test_stderr=tested.stderr,test_unchanged=tests_hash==hashlib.sha256((root/'test_calc.py').read_bytes()).hexdigest(),
                      changed_files=git('diff','--name-only',base,head).splitlines(),
                      working_tree=git('status','--porcelain'))
        record['verdict']='PASS' if tested.returncode==0 and head!=base and record['test_unchanged'] and record['changed_files']==['calc.py'] and not record['working_tree'] else 'FAIL'
    except Exception as error:
        record.update(verdict='INFRA_FAIL',error_type=type(error).__name__,error=str(error))
    record['elapsed_seconds']=round(time.perf_counter()-tick,6)
    (Path('/opt/workbench/evidence')/(run_id+'.json')).write_text(json.dumps(record,default=str,indent=2)+'\n')
    print(json.dumps(record,default=str),flush=True)
    return 0 if record['verdict']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
