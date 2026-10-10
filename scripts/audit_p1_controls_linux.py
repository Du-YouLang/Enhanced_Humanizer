"""Offline control checks. The model/API transport is replaced; no billable requests."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from hmz.coganchor.fence import Fence, wrapper
from p1_broker import Broker, protect_memory
from p1_budget import Ledger


def main():
    protect_memory()
    root=Path('/opt/workbench/runs/p1-controls-'+str(time.time_ns()))
    root.mkdir()
    ledger=Ledger(root/'mock-only-ledger.json',requests=1)
    broker=Broker('mock-not-a-provider-credential',ledger,'OFFLINE_CONTROL_TEST',time.monotonic()+60)
    calls=[]
    async def fake_forward(handler,body,index):
        value=json.loads(ledger.path.read_text())
        assert len(value['requests'])==1 and value['requests'][0]['status']=='RESERVED_UNKNOWN_USAGE'
        calls.append(index)
        ledger.settle(index,{'input_tokens':1,'cache_read_input_tokens':0,'cache_creation_input_tokens':0,'output_tokens':1},
                      {'kind':'MOCK_TRANSPORT_ONLY'})
        handler.send_response(200);handler.end_headers();handler.response_started=True
    broker.forward=fake_forward
    broker.start()
    opener=build_opener(ProxyHandler({}))
    body={'model':'deepseek-flash','stream':True,'stream_options':{'include_usage':True},'max_tokens':10,'messages':[]}
    def request(route='/chat/completions',auth=True,data=None):
        headers={'Content-Type':'application/json'}
        if auth:headers['Authorization']='Bearer '+broker.capability
        req=Request(broker.url+route,data=json.dumps(body if data is None else data).encode(),headers=headers)
        try:
            with opener.open(req,timeout=3) as response:return response.status
        except HTTPError as error:return error.code
    checks={}
    try:
        checks['unauthorized_client_denied']=request(auth=False)==403
        checks['alternate_route_denied']=request('/v1/messages')==403
        checks['other_model_denied']=request(data=body|{'model':'deepseek-v4-pro'})==402
        checks['billed_server_tools_denied']=request(data=body|{'tools':[{'type':'web_search'}]})==402
        checks['no_reservation_for_policy_rejections']=not ledger.path.exists()
        checks['request_reserved_before_transport']=request()==200 and calls==[1]
        checks['next_request_denied_before_transport']=request()==402 and calls==[1]
        broker.deadline=time.monotonic()-1
        checks['expired_experiment_denied_before_transport']=request()==402 and calls==[1]
        protected=root/'synthetic-credential.txt';protected.write_text('synthetic-canary-only')
        work=root/'candidate';work.mkdir();scratch=work/'tmp';scratch.mkdir()
        targets=[str(protected),f'/proc/{os.getpid()}/environ',f'/proc/{os.getpid()}/mem',f'/proc/{os.getpid()}/fd/0']
        program='''import json,sys
out=[]
for path in sys.argv[1:]:
    try:
        with open(path,'rb'):pass
    except PermissionError:out.append(True)
    except OSError:out.append(False)
    else:out.append(False)
print(json.dumps(out))
'''
        fence=Fence.of(local='none',user='none',system='none',online=False,workdir=work,home=Path.home(),
                       read=('/opt/workbench/.venv-linux',),write=(work,),hosts=(broker.host_port,))
        result=subprocess.run([*wrapper(replace(fence,tmp=str(scratch))),sys.executable,'-c',program,*targets],capture_output=True,text=True,timeout=15)
        denied=json.loads(result.stdout) if result.returncode==0 else [False]*4
        for label,value in zip(('credential_file_denied','controller_environ_denied','controller_mem_denied','controller_fd_denied'),denied):checks[label]=value
    finally:broker.close()
    record={'kind':'OFFLINE_CONTROL_TEST','paid_requests':0,'checks':checks,'verdict':'PASS' if all(checks.values()) else 'FAIL'}
    Path('/opt/workbench/evidence/p1-controls.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
    return 0 if record['verdict']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
