"""Installed DSH and real HTTP reconnect control; no provider inference."""
import argparse
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time

from deepseek_harness import DeepSeekHarness
from deepseek_harness_runtime import resolve_bundled_launch_args
from hmz.coganchor.fence import Fence,wrapper
from p6_main_budget import MainLedger
from p6_network_recovery import RecoveryBroker
from p2_candidates import exclusive_json


def check(root,config):
    if os.getuid()==0 or not root.resolve().is_relative_to(Path('/opt/workbench/benchmark/private')):
        raise ValueError('Fresh non-root project-private control required')
    root.mkdir();phase=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
    before=hashlib.sha256(phase.read_bytes()).hexdigest();cases={}
    for label,failures,partial in [('four-reconnects',4,False),('five-failures',5,False),('partial-stream',1,True)]:
        folder=root/label;folder.mkdir();home=folder/'dsh';home.mkdir();tmp=folder/'tmp';tmp.mkdir()
        (home/'settings.yaml').write_text(json.dumps({'llm-deepseek':{'maxTokens':256000}}))
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append({'max_tokens':body['max_tokens']})
                if len(seen)<=failures and not partial:
                    self.send_response(503);self.send_header('Connection','close');self.end_headers();return
                self.send_response(200);self.send_header('Content-Type','text/event-stream')
                self.send_header('Connection','close');self.end_headers()
                if len(seen)<=failures:
                    row={'id':'fixture','model':'deepseek-flash','choices':[{'index':0,'delta':{
                        'tool_calls':[{'index':0,'id':'do-not-deliver','type':'function','function':{'name':'bash','arguments':'PARTIAL_TOOL_MUST_NOT_REACH_HARNESS'}}]},'finish_reason':None}]}
                    self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode());self.wfile.flush();return
                rows=[{'id':'fixture','model':'deepseek-flash','choices':[{'index':0,'delta':{'role':'assistant','content':'CONTROL_COMPLETE_ONLY'},'finish_reason':None}]},
                      {'id':'fixture','model':'deepseek-flash','choices':[{'index':0,'delta':{},'finish_reason':'stop'}],
                       'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':10}}]
                for row in rows:self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        class FixtureBroker(RecoveryBroker):
            provider_endpoint='http://127.0.0.1:'+str(server.server_port)+'/chat/completions'
        ledger=MainLedger(folder/'mock-ledger.json',config)
        broker=FixtureBroker('ZERO_MODEL_NO_CREDENTIAL',ledger,'ZERO_MODEL_NETWORK/'+label,time.monotonic()+55,config)
        broker.start();tick=time.perf_counter();result=None;error=None
        try:
            fence=replace(Fence.of(local='none',user='none',system='none',online=False,workdir=folder,home=Path.home(),
                          read=('/opt/workbench/.venv-linux',),write=(home,),hosts=(broker.host_port,)),tmp=str(tmp))
            launch=(*wrapper(fence),*resolve_bundled_launch_args(),'--profile','sdk')
            env={'DEEPSEEK_API_KEY':broker.capability,'DEEPSEEK_BASE_URL':broker.url,'DSH_HOME':str(home),
                 'PKG_NATIVE_CACHE_PATH':str(home/'cache'),'TMPDIR':str(tmp),'HUMANIZE_SENTRY':'off'}
            try:
                with DeepSeekHarness(_launch_args=launch,dsh_home=str(home),cwd=str(folder),env=env,
                         model='deepseek-flash',provider='deepseek-official',reasoning_effort='low',request_timeout_seconds=40) as harness:
                    result=harness.run('Return a short summary, no tools.',session_id='network-'+label)
            except Exception as exc:error=type(exc).__name__
        finally:broker.close();server.shutdown();server.server_close()
        rows=json.loads(ledger.path.read_text())['requests']
        terminal=getattr(result,'finish_reason',None)
        transcript='\n'.join(p.read_text(errors='replace') for p in home.rglob('*.jsonl'))
        cases[label]={'wire_attempts':len(seen),'wire_caps':[r['max_tokens'] for r in seen],
            'reservations':len(rows),'settled':sum(r['status']=='SETTLED_USAGE_UPPER_BOUND' for r in rows),
            'request_timeout_seconds':[r.get('request_timeout_seconds') for r in rows if r['status']=='SETTLED_USAGE_UPPER_BOUND'],
            'events':broker.network_events,'finish_reason':terminal,'error_type':error,'circuit_open':broker.circuit_open,
            'partial_tool_delivered':'PARTIAL_TOOL_MUST_NOT_REACH_HARNESS' in transcript,
            'elapsed_seconds':time.perf_counter()-tick}
    a,b,c=(cases[k] for k in ('four-reconnects','five-failures','partial-stream'))
    after=hashlib.sha256(phase.read_bytes()).hexdigest()
    passed=(before==after and a['finish_reason']=='completed' and a['wire_attempts']==a['reservations']==5 and a['settled']==1
        and b['wire_attempts']==b['reservations']==5 and b['settled']==0 and b['circuit_open']
        and b['events'][-1]['state']=='NETWORK_CHECK_REQUIRED'
        and c['finish_reason']=='completed' and c['wire_attempts']==c['reservations']==2 and c['settled']==1
        and not c['partial_tool_delivered'] and a['request_timeout_seconds']==c['request_timeout_seconds']==[600]
        and all(all(cap==256000 for cap in v['wire_caps']) for v in cases.values()))
    names=['p1_broker.py','p1_budget.py','p2_judges.py','p6_network_policy.py','p6_network_recovery.py',
           'p6_network_control_linux.py','p6_main_budget.py','p6_main_contract.py','p6_main_runtime_linux.py','p6_runtime_linux.py']
    proof={'status':'PASS' if passed else 'FAIL','uid':os.getuid(),'provider_requests':0,'cases':cases,
        'ledger_sha256_before':before,'ledger_sha256_after':after,'evidence_kind':'ZERO_MODEL_INSTALLED_DSH_HTTP_NETWORK_RECOVERY',
        'source_sha256':{n:hashlib.sha256((Path('/opt/workbench/source')/n).read_bytes()).hexdigest() for n in names}}
    exclusive_json(root/'receipt.json',proof);return proof


if __name__=='__main__':
    import sys
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    value=check(args.output,json.load(sys.stdin));print(json.dumps(value));raise SystemExit(0 if value['status']=='PASS' else 1)
