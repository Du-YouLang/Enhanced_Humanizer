"""Explicit P0 Pi tool probe; formal profile/task matrices remain disabled."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from wsl_project import run


def quiet_host():
    if os.name!='nt':raise RuntimeError('Use the approved Windows project controller')
    # Only IDs leave this query; no process environment/auth data is read.
    command=r"@(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -match '\\python(?:3)?\.exe$' -and $_.CommandLine -match 'scripts[/\\]run_p6_main(?:_batch)?\.py' } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,timeout=20)
    if p.returncode:raise RuntimeError('Host experiment ownership query failed')
    raw=p.stdout.decode('utf8').strip()
    if raw and json.loads(raw):raise RuntimeError('Live Pi probe deferred while a Windows main controller is active')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--provider',choices=('fixture','deepseek','subscription'),default='fixture')
    p.add_argument('--execute-real',action='store_true',help='Only after quiet-host/native ownership checks; never enables task smoke')
    p.add_argument('--fixture-fault',choices=('usage',));a=p.parse_args()
    if a.fixture_fault and a.provider!='fixture':raise ValueError('Fault control is synthetic only')
    if a.provider!='fixture':
        if not a.execute_real:raise RuntimeError('Real model execution disabled by default')
        if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip():raise RuntimeError('Commit source before real probe')
        quiet_host()
    payload={'budget':json.loads((ROOT/'configs/budget-p6-main-v5-network-approved.json').read_text()),'fixture_fault':a.fixture_fault}
    source={n:(Path(__file__).parent/n).read_text(encoding='utf8') for n in ('sdk_tool_probe.mjs','sdk_tool_probe_linux.py','events.py')}
    deploy="import json,sys;from pathlib import Path;r=Path('/opt/workbench/pi-comparison/controller-sdk-v2');r.mkdir(exist_ok=True);[(r/n).write_text(s) for n,s in json.load(sys.stdin).items()];print('DEPLOYED')"
    r=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',deploy],input_bytes=json.dumps(source).encode(),timeout=30)
    if r.returncode:raise RuntimeError('Independent Pi probe deployment failed')
    if a.provider!='fixture':
        q=run(['/opt/workbench/.venv-linux/bin/python','-B','-c',"import sys;from pathlib import Path;sys.path.insert(0,'/opt/workbench/pi-comparison/controller-sdk-v2');from sdk_tool_probe_linux import require_quiet_main,require_sdk_controls;require_quiet_main();require_sdk_controls(Path('/opt/workbench/pi-comparison/controller-sdk-v2/sdk_tool_probe.mjs'));print('QUIET')"],timeout=30)
        if q.returncode or q.stdout.strip()!=b'QUIET':raise RuntimeError('Native main experiment ownership query refused')
    if a.provider=='deepseek':
        import yaml
        # Existing single credential source; never written into the probe directory.
        payload['key']=yaml.safe_load((Path(os.environ['USERPROFILE'])/'.dsh/.credentials.yaml').read_text(encoding='utf8'))['refs']['DEEPSEEK_API_KEY']
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name='sdk-probe-'+a.provider+('-negative-usage' if a.fixture_fault else '')+'-'+stamp
    args=['/opt/workbench/.venv-linux/bin/python','-B','/opt/workbench/pi-comparison/controller-sdk-v2/sdk_tool_probe_linux.py',
        '--provider',a.provider,'--output','/opt/workbench/pi-comparison/'+name,'--driver','/opt/workbench/pi-comparison/controller-sdk-v2/sdk_tool_probe.mjs']
    result=run(args,input_bytes=json.dumps(payload).encode(),timeout=960 if a.provider!='fixture' else 90)
    intake=ROOT/'.local-workbench/pi-comparison/intake';intake.mkdir(parents=True,exist_ok=True)
    (intake/(name+'.private.log')).write_bytes(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Probe did not pass; private receipt/log preserved, no automatic replay')
    print(result.stdout.decode('utf8').strip())
    return 0


if __name__=='__main__':raise SystemExit(main())
