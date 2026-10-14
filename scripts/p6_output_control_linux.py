"""Official installed DSH + real metering HTTP with a synthetic provider stream.

Zero provider calls: proves profile/wire/ledger controls, never model quality.
"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time
import types

from deepseek_harness import DeepSeekHarness
from deepseek_harness_runtime import resolve_bundled_launch_args
from hmz.coganchor.fence import Fence,wrapper
from p1_broker import Broker
from p6_main_budget import MainLedger
from p2_candidates import exclusive_json


def check(root,old,new):
    if os.getuid()==0 or not root.resolve().is_relative_to(Path('/opt/workbench/benchmark/private')):
        raise ValueError('Non-root fresh project-private fixture required')
    root.mkdir();phase=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
    before=hashlib.sha256(phase.read_bytes()).hexdigest();cases={}
    for label,budget,cap,override in [('old4096',old,4096,None),('new256000',new,256000,None),('oversized-sdk',new,256000,384000)]:
        folder=root/label;folder.mkdir();home=folder/'dsh';home.mkdir();tmp=folder/'tmp';tmp.mkdir()
        (home/'settings.yaml').write_text(json.dumps({'llm-deepseek':{'maxTokens':cap}}))
        ledger=MainLedger(folder/'mock-ledger.json',budget);requests=[]
        broker=Broker('mock-no-provider-access',ledger,'ZERO_MODEL_OUTPUT/'+label,time.monotonic()+60)
        async def fixture(self,handler,body,index):
            effective=body['max_tokens'];count=4096 if effective==4096 else 5001
            requests.append({'max_tokens':effective,'keys':sorted(body)})
            handler.send_response(200);handler.send_header('Content-Type','text/event-stream')
            handler.send_header('Connection','close');handler.end_headers()
            chunks=[{'id':'synthetic','model':'deepseek-flash','choices':[{'index':0,'delta':{'role':'assistant','content':'MOCK_OUTPUT_CONTROL_ONLY '*count},'finish_reason':None}]},
                    {'id':'synthetic','model':'deepseek-flash','choices':[{'index':0,'delta':{},'finish_reason':'length' if count==4096 else 'stop'}],
                     'usage':{'prompt_tokens':10,'completion_tokens':count,'total_tokens':10+count,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':10}}]
            for row in chunks:handler.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
            handler.wfile.write(b'data: [DONE]\n\n');handler.wfile.flush()
            self.ledger.settle(index,dict(input_tokens=10,cache_read_input_tokens=0,cache_creation_input_tokens=0,output_tokens=count),
                               {'model_id':'deepseek-flash','protocol':'SYNTHETIC_CONTROL_ONLY','effective_max_output_tokens':effective})
        broker.forward=types.MethodType(fixture,broker);broker.start()
        try:
            fence=Fence.of(local='none',user='none',system='none',online=False,workdir=folder,home=Path.home(),
                           read=('/opt/workbench/.venv-linux',),write=(home,),hosts=(broker.host_port,))
            launch=(*wrapper(replace(fence,tmp=str(tmp))),*resolve_bundled_launch_args(),'--profile','sdk')
            env={'DEEPSEEK_API_KEY':broker.capability,'DEEPSEEK_BASE_URL':broker.url,'DSH_HOME':str(home),
                 'PKG_NATIVE_CACHE_PATH':str(home/'cache'),'TMPDIR':str(tmp),'HUMANIZE_SENTRY':'off'}
            tick=time.perf_counter()
            # max_tokens deliberately omitted, matching the Humanize driver;
            # the official DSH role-private profile must supply the request cap.
            extra={} if override is None else {'max_tokens':override}
            with DeepSeekHarness(_launch_args=launch,dsh_home=str(home),cwd=str(folder),env=env,
                                 model='deepseek-flash',provider='deepseek-official',reasoning_effort='low',
                                 request_timeout_seconds=30,**extra) as harness:
                result=harness.run('Return a short summary; no tools.',session_id='mock-'+label)
            rows=json.loads(ledger.path.read_text())['requests']
            cases[label]={'finish_reason':result.finish_reason,'requests':requests,'elapsed_seconds':time.perf_counter()-tick,
                          'settled_output_tokens':[v.get('usage',{}).get('output_tokens') for v in rows],
                          'request_count':len(rows),'actual_driver':'official installed DSH SDK/runtime',
                          'fixture_kind':'SYNTHETIC_STREAM_NOT_INFERENCE'}
        finally:broker.close()
    after=hashlib.sha256(phase.read_bytes()).hexdigest()
    passed=(before==after and cases['old4096']['finish_reason']=='max-tokens' and cases['new256000']['finish_reason']=='completed'
            and cases['oversized-sdk']['finish_reason']=='completed' and cases['oversized-sdk']['requests'][0]['max_tokens']==256000
            and cases['old4096']['settled_output_tokens']==[4096] and cases['new256000']['settled_output_tokens']==[5001]
            and all(v['request_count']==1 and v['requests'][0]['max_tokens']==cap for v,cap in ((cases['old4096'],4096),(cases['new256000'],256000))))
    names=['p1_broker.py','p2_experiment_linux.py','p2_judges.py','p6_main_budget.py','p6_output_policy.py','p6_output_control_linux.py','p6_worker_linux.py','p6_main_runtime_linux.py']
    proof={'status':'PASS' if passed else 'FAIL','uid':os.getuid(),'provider_requests':0,'cases':cases,
           'ledger_sha256_before':before,'ledger_sha256_after':after,'evidence_kind':'ZERO_MODEL_OFFICIAL_DSH_PROFILE_HTTP_AND_SETTLEMENT_CONTROL',
           'source_sha256':{n:hashlib.sha256((Path('/opt/workbench/source')/n).read_bytes()).hexdigest() for n in names}}
    exclusive_json(root/'receipt.json',proof);return proof


if __name__=='__main__':
    import sys
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    payload=json.load(sys.stdin);result=check(args.output,payload['old'],payload['new'])
    print(json.dumps(result));raise SystemExit(0 if result['status']=='PASS' else 1)
