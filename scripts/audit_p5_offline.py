"""Independent P5 native tests and frozen code replay, with zero inference requests."""
import io
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from wsl_project import run

CODE=r'''
import hashlib,json,os,subprocess,sys,time,zipfile,io
from pathlib import Path
root=Path('/opt/workbench/p5-offline-qa');root.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as archive:archive.extractall(root)
known={'p1':'6f4d808ba13b259de0afb67e0d3f80c4c328125947c044801a7dcedcb0ed3643',
       'p2':'760385b37cd6246be664c0d33aae3eb9b351a5badfcdee02650241a111b74dea',
       'p3':'212e47dde838c7805f664d54f1ab25cf6d132e65bc81b8fb329a2ec310cdd586'}
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior={phase:digest('/opt/workbench/state/'+phase+'-budget/ledger.json') for phase in known}
assert prior==known,'Earlier phase ledger changed'
ledger=Path('/opt/workbench/state/p5-budget/ledger.json');before=digest(ledger)
env=dict(os.environ,PYTHONPATH=str(root/'src')+':'+str(root/'scripts')+':'+str(root/'tests'))
command=[sys.executable,'-B','-m','unittest','test_p1_budget','test_p2','test_p3','test_memory','test_ui','-v']
test=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=90)
(root/'unittest.private.log').write_text(test.stdout+test.stderr)
sys.path.insert(0,'/opt/workbench/source')
from p2_candidates import validate_pool,run_tests
pool=validate_pool(json.loads(Path('/opt/workbench/runs/p5-20261010155100-13a14339-pool/frozen-pool.json').read_text()))
replays={}
for row in pool['candidates']:
 work=Path('/opt/workbench/runs/p5-20261010155100-13a14339-pool')/row['id']/'worktree'
 replays[row['id']]=run_tests(work,independent=True,contract=pool['contract_manifest'])
result={'kind':'INDEPENDENT_NATIVE_NO_MODEL_REPLAY','uid':os.getuid(),'native_tests_exit':test.returncode,
        'native_tests_summary':test.stderr.splitlines()[-5:],'replays':replays,'pool_hash':pool['pool_hash'],
        'previous_phase_ledger_sha256':prior,'p5_ledger_before':before,'p5_ledger_after':digest(ledger),
        'new_model_requests':0,'new_subscription_turns':0,'api_cash_usd':0}
result['verdict']='PASS' if test.returncode==0 and before==result['p5_ledger_after'] and all(r['verdict']=='PASS' for r in replays.values()) else 'FAIL'
print(json.dumps(result));sys.exit(0 if result['verdict']=='PASS' else 1)
'''

def main():
    tick=time.perf_counter();data=io.BytesIO()
    sys.path.insert(0,str(ROOT/'src'))
    from workbench.memory import Memory
    memory=Memory(ROOT/'.local-workbench/workbench')
    if any(r.get('phase')=='P5' and r['status'] in ('RUNNING','PAUSE_REQUESTED','STOP_REQUESTED') for r in memory.list('run')):
        raise RuntimeError('Independent no-model ledger comparison requires an inactive controller')
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as archive:
        for directory in ('scripts','src','tests','configs'):
            for file in (ROOT/directory).rglob('*'):
                if file.is_file() and '__pycache__' not in file.parts and file.suffix in ('.py','.json','.lock','.js','.html','.css'):
                    archive.write(file,file.relative_to(ROOT).as_posix())
    result=run(['python','-B','-c',CODE],input_bytes=data.getvalue(),timeout=115)
    if result.stdout:
        value=json.loads(result.stdout);value['audit_wall_seconds']=time.perf_counter()-tick
        path=ROOT/'.local-workbench/audits/p5-offline.json';path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in value.items() if k!='replays'}))
    else:print('Offline audit failed: '+result.stderr.decode(errors='replace')[:1200])
    return result.returncode

if __name__=='__main__':sys.exit(main())
