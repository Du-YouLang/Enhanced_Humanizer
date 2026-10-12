"""Zero-inference HTTPS check through the unchanged Humanize network fence."""
import subprocess
import time
import uuid
import json
from pathlib import Path


def probe():
    from hmz.coganchor.fence import Fence,wrapper
    from p2_candidates import namespace_command
    root=Path('/opt/workbench/checks/connectivity')/uuid.uuid4().hex
    root.mkdir(parents=True)
    fence=Fence.of(local='none',user='none',system='none',online=False,workdir=root,home=root,
                   hosts=('chatgpt.com','auth.openai.com','api.openai.com'))
    tick=time.perf_counter()
    result=subprocess.run(namespace_command([*wrapper(fence),'curl','--max-time','12','--silent','--output','/dev/null',
                          '--write-out','%{http_code}','https://chatgpt.com/robots.txt']),cwd=root,capture_output=True,text=True,timeout=20)
    return {'kind':'ZERO_MODEL_FENCED_CONNECTIVITY','model_requests':0,'elapsed_seconds':time.perf_counter()-tick,
            'http_status':result.stdout.strip(),'exit':result.returncode,'observed_unix':time.time(),
            'verdict':'PASS' if result.returncode==0 and result.stdout.strip()=='200' else 'FAIL'}


def reconnect_probe():
    """Five actual, zero-model, unchanged-fence connection attempts at most."""
    attempts=[]
    for n in range(5):
        try:value=probe()
        except subprocess.TimeoutExpired:
            value={'kind':'ZERO_MODEL_FENCED_CONNECTIVITY','model_requests':0,'verdict':'FAIL',
                   'error_type':'TimeoutExpired','http_status':'unavailable','observed_unix':time.time()}
        attempts.append(value)
        if value['verdict']=='PASS':
            return {'verdict':'PASS','model_requests':0,'attempts':attempts,'consecutive_failures':0}
        value['state']='SHOULD_RETRY' if n<4 else 'NETWORK_CHECK_REQUIRED'
        if n<4:time.sleep((1,2,4,8)[n])
    return {'verdict':'NETWORK_CHECK_REQUIRED','model_requests':0,'attempts':attempts,'consecutive_failures':5}
