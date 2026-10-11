"""Reuse the frozen TMS numerical judge with isolated candidate execution."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import uuid

from p6_output_data import bounded_json,bounded_npz
from p6_science_sandbox import execute

WORKER='''import sys,runpy
from pathlib import Path
source,inputs,output=map(Path,sys.argv[1:4]);allow=sys.argv[4]=='true'
sys.path.insert(0,str(source))
sys.argv=[str(source/'main.py'),'--input',str(inputs/'input.npz'),'--config',str(inputs/'profile.json'),'--output',str(output/'result')]
if allow:sys.argv.append('--allow-unreviewed')
runpy.run_path(str(source/'main.py'),run_name='__main__')
'''


def grade(source,root,prefix,*,timeout=600,fail_fast=False):
    from p6_prepare_linux import BASE
    root=Path(root);prefix=Path(prefix);source=Path(source)
    folder=BASE/'science/private/tms-grading'/uuid.uuid4().hex;folder.mkdir(parents=True)
    path=root/'judge_private/judge.py'
    # These are owner-frozen dependencies, never candidate modules.
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('owner_tms_judge_'+uuid.uuid4().hex,path)
    judge=importlib.util.module_from_spec(spec);spec.loader.exec_module(judge)
    executions=[]
    def isolated(args,inp,profile,out,allow,workspace):
        result=execute(source,prefix,WORKER,inputs={'input.npz':inp.read_bytes(),'profile.json':profile.read_bytes()},
                       timeout=max(1,min(60,int(args.timeout))),rss_limit_mib=1024,cpu_threads=1,pin_one_cpu=True,
                       arguments=('true' if allow else 'false',))
        executions.append(result);current=Path(result['output'])/'result';invalid_output=None
        if current.exists():
            try:
                for file in current.rglob('*'):
                    if file.suffix=='.json':bounded_json(file)
                    elif file.suffix=='.npz':bounded_npz(file)
                shutil.copytree(current,out)
            except (ValueError,OSError,KeyError,TypeError) as error:invalid_output=type(error).__name__
        limitation=invalid_output or (None if result['status'] in ('COMPLETED_UNGRADED','SUBMISSION_FAILED') else result['status'])
        return {'returncode':result['exit_code'],'seconds':result['elapsed_seconds'],
                'peak_process_mb':result['peak_process_tree']['rss_kib']/1024,'one_cpu_affinity':result['one_cpu_affinity'],
                'limit_failure':limitation,'log_tail':(Path(result['evidence_root'])/'stderr.private.log').read_text(errors='replace')[-1500:]}
    judge.execute=isolated
    previous=sys.argv
    try:
        sys.argv=['owner-tms-judge','--submission',str(source),'--python',str(prefix/'bin/python'),
                  '--report',str(folder/'numeric.private.json'),'--timeout','60','--total-timeout',str(timeout),'--memory-mb','1024']
        if fail_fast:sys.argv.append('--fail-fast')
        try:judge.main()
        except SystemExit as error:
            if error.code not in (0,1):raise
    finally:
        sys.argv=previous;sys.path.remove(str(path.parent))
    numeric=bounded_json(folder/'numeric.private.json')
    result={'verdict':'PASS' if numeric['all_passed'] else 'FAIL','numeric':numeric,'executions':executions,
            'elapsed_seconds':sum(r['elapsed_seconds'] for r in executions),'model_requests':0,
            'memory_measurement':'Controller-observed descendant RSS; private PID namespace killed on timeout',
            'security_boundary':'Candidate imported only inside Humanize file/network fence and private non-root namespace; private gold stays in parent'}
    (folder/'receipt.private.json').write_text(json.dumps(result,indent=2))
    return result
