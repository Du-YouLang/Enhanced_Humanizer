"""Scientific task adapters for the same main Harness and coding-time protocol."""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from p6_prepare_linux import BASE,seal_environment
from p6_science_sandbox import execute

SCIENCE=BASE/'science'
KINDS={'SCI-PC-ALM':('pc-alm','science-pc-alm-v1','TASK.md'),
       'SCI-STROKE':('tms','science-tms-v1','TASK_AGENT.md'),
       'SCI-EGL':('egl','science-egl-v1','TASK-v1.md'),
       'SCI-GRANGER-GPU':('gc','science-gc-v1','README_AGENT.md')}


def fingerprint(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob('*'))
            if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}


def prepare():
    root=SCIENCE/'private/main-science-preparation-v1'
    if root.exists():raise ValueError('Preserve previous science preparation')
    root.mkdir(parents=True);tasks=[]
    import shutil
    for tid,(kind,env_name,card) in KINDS.items():
        base=root/tid;base.mkdir()
        public=SCIENCE/'intake'/kind/'agent_public'
        selected=public/'upstream' if kind=='pc-alm' else public
        shutil.copytree(selected,base,dirs_exist_ok=True,symlinks=True,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc'))
        if kind=='pc-alm':
            (base/card).write_bytes((SCIENCE/'private/pc-task-main-v1.md').read_bytes())
            (base/'run_benchmark.py').write_text('"""Implement the frozen task orchestration and report; official training files are protected."""\nraise NotImplementedError("Implement run_benchmark.py --data-dir INPUT --output-dir OUT")\n')
        elif kind=='egl':
            (base/'candidate.py').write_text('"""Implement the public CPU training/report interface."""\nraise NotImplementedError("Implement candidate.py --out OUT")\n')
            (base/'candidate_optimizer.py').write_text('def eg_step(weight, gradient, lr):\n    raise NotImplementedError("Implement signed multiplicative update")\n')
        elif kind=='tms':
            (base/'main.py').write_text('"""Implement the public sensor-level numerical protocol."""\nraise NotImplementedError("Implement main.py --input --config --output [--allow-unreviewed]")\n')
        # No owner code, private gold, server paths or credentials are copied.
        env=BASE/'envs'/env_name
        files=fingerprint(base)
        protected=[name for name in files if name not in {'run_benchmark.py','main.py','candidate.py','candidate_optimizer.py','gc_cupy.py'}]
        for args in (['init','-q'],['config','user.name','Workbench Scientific Baseline'],['config','user.email','science@example.invalid'],
                     ['config','core.hooksPath','/dev/null'],['add','.'],['commit','-qm','Freeze public scientific task and interfaces']):
            subprocess.run(['git','-c','core.hooksPath=/dev/null',*args],cwd=base,check=True,capture_output=True,timeout=30)
        commit=subprocess.check_output(['git','-C',str(base),'rev-parse','HEAD'],text=True).strip()
        seal=seal_environment(env,tid+'-main-v1')
        task={'task_id':tid,'kind':kind,'base':str(base),'base_commit':commit,'prefix':str(env),'card':card,
              'public_fingerprint':files,'protected_paths':protected,'environment':seal,'model_requests':0}
        (root/(tid+'.json')).write_text(json.dumps(task,indent=2));tasks.append(task)
    (root/'receipt.json').write_text(json.dumps({'status':'PUBLIC_BASELINES_PREPARED_CONTROLS_REQUIRED','tasks':tasks,'model_requests':0},indent=2))
    return tasks


def task(payload):
    tid=payload['task']['task_id'];kind,env,card=KINDS[tid]
    r=json.loads((SCIENCE/'private/main-science-preparation-v1'/(tid+'.json')).read_text())
    base=Path(r['base']);prefix=Path(r['prefix']);seal=seal_environment(prefix,tid+'-main-v1')
    if fingerprint(base)!=r['public_fingerprint'] or seal['env_sha256']!=r['environment']['env_sha256']:
        raise RuntimeError('Scientific source or environment changed')
    if r['base_commit']!=payload['task']['base_commit']:raise RuntimeError('Science base differs from frozen manifest')
    prompt=(base/card).read_text()+'\nProject execution contract: coding is limited to 115 seconds per independent role. Implement and test the public submission interface, commit cleanly. Full numerical acceptance is performed later by a separate controller; do not wait for full training while coding. Preserve provided input data, official training/configuration files and original tests. No installs, external repositories, credentials, subagents or historical outputs. All compute is local.\n'
    if kind=='pc-alm':prompt+='Offline public data directory: '+str(SCIENCE/'intake/pc-alm/inputs')+'\n'
    # A public syntax/entrypoint check is deliberately weak. It never claims
    # hidden scientific correctness, and does not load any private reference.
    code="import pathlib; files=FILES; [compile(pathlib.Path(p).read_bytes(),p,'exec') for p in files]; print('Public syntax check PASS; full scientific acceptance is separate')"
    names={'pc-alm':['run_benchmark.py'],'tms':['main.py'],'egl':['candidate.py','candidate_optimizer.py'],'gc':['gc_cupy.py']}[kind]
    visible=[str(prefix/'bin/python'),'-B','-c',code.replace('FILES',repr(names))]
    if kind=='gc':visible=[str(prefix/'bin/python'),'-B','public_test.py']
    elif kind=='pc-alm':
        check="import pathlib,pytest,sys;compile(pathlib.Path('run_benchmark.py').read_bytes(),'run_benchmark.py','exec');sys.exit(pytest.main(['-q','-p','no:cacheprovider','tests']))"
        visible=[str(prefix/'bin/python'),'-B','-c',check]
    elif kind=='egl':
        check="import torch;from candidate_optimizer import eg_step\nfor dtype in (torch.float32,torch.float64):\n w=torch.tensor([-1.,0.,1.],dtype=dtype);g=torch.tensor([.1,-.2,.3],dtype=dtype);expected=w*torch.exp(-.75*torch.sign(w)*g);actual=eg_step(w.clone(),g.clone(),.75);torch.testing.assert_close(actual,expected)\nprint('Public signed optimizer checks PASS; full training acceptance is separate')"
        visible=[str(prefix/'bin/python'),'-B','-c',check]
    prompt+='Public check command: '+json.dumps(visible)+'\n'
    return {'id':tid,'kind':kind,'base':str(base),'base_commit':r['base_commit'],'prefix':str(prefix),'seal':seal,
            'prompt':prompt,'visible':visible,'visible_expected':None,'hidden_argv':[],'hidden':{},'expected':None,
            'public_overlays':{},'test_patch':None,'framework':'pytest','fixture_context':nullcontext(None),'fixture_ca':None,
            'protected_paths':r['protected_paths'],'writable_fixture_paths':[],
            'public_read_paths':['/opt/workbench/source/p6_public_visible.py',*([str(SCIENCE/'intake/pc-alm/inputs')] if kind=='pc-alm' else [])],
            'hidden_suite_sha256':payload['task']['gold_sha256'],'gpu_coding':kind in ('pc-alm','gc')}


def test(source,hidden=False):
    import p6_runtime_linux as shared
    task=shared.ACTIVE['task'];kind=task['kind'];prefix=Path(task['prefix']);started=time.perf_counter()
    if not hidden:
        worker='''import sys,subprocess
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4])
subprocess.run(COMMAND,cwd=source,check=True,timeout=30)
'''.replace('COMMAND',repr(task['visible']))
        result=execute(source,prefix,worker,timeout=40,gpu=kind in ('gc','pc-alm'),rss_limit_mib=4096,cpu_threads=1)
        log=Path(result['evidence_root'])/'test.private.log'
        log.write_bytes((log.parent/'stdout.private.log').read_bytes()+(log.parent/'stderr.private.log').read_bytes())
        text=log.read_text(errors='replace')
        import re
        count=re.search(r'(\d+) passed',text) if kind=='pc-alm' else None
        # Count only publicly observed assertions; failed baselines do not
        # inherit the fixture's planned test count.
        observed=int(count.group(1)) if count else ('unavailable' if kind=='gc' else (6 if kind=='egl' and result['status']=='COMPLETED_UNGRADED' else 1 if kind=='tms' else 0))
        return {'verdict':'PASS' if result['status']=='COMPLETED_UNGRADED' else 'FAIL',
                'exit_code':result['exit_code'],'tests_observed':observed,
                'elapsed_seconds':result['elapsed_seconds'],'private_log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
                'evidence_root':result['evidence_root'],'scope':'PUBLIC_CHECKS_NOT_FULL_SCIENTIFIC_ACCEPTANCE'}
    if kind=='pc-alm':
        from p6_pc_grader import grade
        r=grade(source,SCIENCE/'private/pc-calibration-20261012-v1',prefix,SCIENCE/'intake/pc-alm/agent_public/upstream')
    elif kind=='tms':
        from p6_tms_grader import grade
        r=grade(source,SCIENCE/'intake/tms',prefix)
    elif kind=='egl':
        from p6_egl_grader import grade
        r=grade(source,SCIENCE/'private/egl-reference-local-v2',prefix)
    else:
        from p6_gc_grader import grade
        r=grade(source,SCIENCE/'intake/gc',prefix)
    # Pending source/figure/report review is INDETERMINATE, never automatic PASS.
    verdict=r['verdict']
    if kind=='tms' and verdict=='PASS':
        r={**r,'verdict':'PASS_NUMERIC_REVIEW_PENDING','source_and_figure_review':'REQUIRED; healthy/synthetic numerical agreement does not establish clinical validity or plotted-data fidelity'}
        verdict=r['verdict']
    if verdict=='PASS_NUMERIC_REVIEW_PENDING':verdict='INDETERMINATE'
    result={'verdict':verdict,'numeric_verdict':r['verdict'],'detail':r,'elapsed_seconds':time.perf_counter()-started}
    if verdict=='INDETERMINATE':result['reason']='Independent numerical checks passed; substantive source/report/figure review required'
    return result


if __name__=='__main__':print(json.dumps(prepare()))
