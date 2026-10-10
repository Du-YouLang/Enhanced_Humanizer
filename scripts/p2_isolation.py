"""Negative tests under the exact official runtime fence, in each candidate PID namespace."""

import json
import os
from pathlib import Path
import subprocess
import sys


def auditor(job):
    checked=False
    def audit(fence):
        nonlocal checked
        if checked:return
        from hmz.coganchor.fence import wrapper
        paths=job['denied_paths']
        code='''import json,os
from pathlib import Path
paths=json.loads(os.environ['P2_DENIED_PATHS'])
results=[]
for name in paths:
    try:Path(name).read_bytes()
    except PermissionError:results.append({'path':name,'read':'DENIED'})
    except FileNotFoundError:results.append({'path':name,'read':'MISSING_NOT_PROOF'})
    else:results.append({'path':name,'read':'ALLOWED_FAILURE'})
    try:
        with open(name,'ab'):pass
    except PermissionError:results[-1]['write']='DENIED'
    except FileNotFoundError:results[-1]['write']='MISSING_NOT_PROOF'
    else:results[-1]['write']='ALLOWED_FAILURE'
own=Path('.p2-isolation-probe');own.write_text('local-write');own.unlink()
print(json.dumps({'paths':results,'uid':os.getuid(),'proc_namespace':os.readlink('/proc/self/ns/pid'),
                  'parent_namespace_visible':os.readlink('/proc/self/ns/pid')==os.environ['P2_PARENT_NS']}))
'''
        env=os.environ|{'P2_DENIED_PATHS':json.dumps(paths),'P2_PARENT_NS':job['parent_namespace']}
        p=subprocess.run([*wrapper(fence),sys.executable,'-B','-c',code],cwd=job['work'],env=env,
                         text=True,capture_output=True,timeout=20)
        if p.returncode:raise RuntimeError('Actual runtime fence probe did not execute')
        value=json.loads(p.stdout)
        value['verdict']='PASS' if value['uid']!=0 and not value['parent_namespace_visible'] and all(
            x['read']=='DENIED' and x['write']=='DENIED' for x in value['paths']) else 'FAIL'
        (Path(job['root'])/'isolation.json').write_text(json.dumps(value,indent=2)+'\n')
        if value['verdict']!='PASS':raise RuntimeError('Cross-candidate isolation failed closed before inference')
        checked=True
    return audit
