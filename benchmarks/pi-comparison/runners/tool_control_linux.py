"""Pinned Pi CLI + real file/test/Git tools with a synthetic local HTTP provider.

Zero provider inference. This establishes plumbing, never benchmark quality or
compatibility with the real DeepSeek service and authoritative metering ledger.
"""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import types

sys.path.insert(0,'/opt/workbench/source')
from p2_candidates import namespace_command,exclusive_json
from hmz.coganchor.fence import Fence,wrapper
from events import summarize


def control(root,profile='P0'):
    base=Path('/opt/workbench/pi-comparison')
    if os.getuid()==0 or not root.resolve().is_relative_to(base):raise ValueError('Project-private non-root control required')
    root.mkdir();work=root/'work';work.mkdir();agent=root/'agent';agent.mkdir()
    for name in ('home','tmp','cache'):(root/name).mkdir()
    package=None
    if profile in ('P1','P3'):package=base/'packages'/profile.lower()/'package'
    if profile=='P2':package=next((base/'packages/p2').glob('neuroforge-skills-*'))
    extra=[]
    if package:
        extra+=['--skill',str(package/'skills')]
        if profile in ('P1','P3'):
            extra+=['--extension',str(package/('extensions' if profile=='P1' else 'dist/extension.js'))]
        if profile=='P3':extra+=['--prompt-template',str(package/'prompts')]
    requests=[]
    steps=[('write',{'path':'smoke_value.py','content':'def answer():\n    return 42\n'}),
           ('bash',{'command':'python3 -c "from smoke_value import answer; assert answer() == 42"'}),
           ('bash',{'command':'git add smoke_value.py'}),
           ('bash',{'command':'git -c user.name=WorkbenchFixture -c user.email=fixture@example.invalid commit -m fixture-tool-control'})]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            index=len(requests);requests.append({'keys':sorted(value),'model':value.get('model'),
                      'output_cap':value.get('max_tokens',value.get('max_completion_tokens')),
                      'tool_names':[t['function']['name'] for t in value.get('tools',[])],
                      'path':self.path,'stream_options':value.get('stream_options')})
            if index>len(steps):self.send_error(429,'Synthetic control exhausted');return
            delta={'role':'assistant'}
            if index<len(steps):
                name,args=steps[index];delta['tool_calls']=[{'index':0,'id':'fixture-'+str(index),
                    'type':'function','function':{'name':name,'arguments':json.dumps(args)}}];reason='tool_calls'
            else:delta['content']='Synthetic tool control finished.';reason='stop'
            rows=[{'id':'synthetic-'+str(index),'model':'deepseek-flash','choices':[{'index':0,'delta':delta,'finish_reason':None}]},
                  {'id':'synthetic-'+str(index),'model':'deepseek-flash','choices':[{'index':0,'delta':{},'finish_reason':reason}],
                   'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,'prompt_tokens_details':{'cached_tokens':0}}}]
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Connection','close');self.end_headers()
            for row in rows:self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
    host=socket.gethostname();server=ThreadingHTTPServer((socket.gethostbyname(host),0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    provider={'providers':{'workbench-fixture':{'api':'openai-completions','baseUrl':'http://'+host+':'+str(server.server_port),
              'apiKey':'ZERO_MODEL_NOT_A_CREDENTIAL','models':[{'id':'deepseek-flash','name':'Synthetic fixture, not inference',
              'reasoning':False,'input':['text'],'contextWindow':1048576,'maxTokens':256000,
              'samplingParams':{'max_tokens':256000},'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0},
              'compat':{'maxTokensField':'max_tokens','supportsStore':False}}]}}}
    exclusive_json(agent/'models.json',provider)
    exclusive_json(agent/'settings.json',{'retry':{'enabled':False,'provider':{'maxRetries':0,'timeoutMs':120000}},
                   'compaction':{'enabled':False},'enableAnalytics':False,'enableInstallTelemetry':False})
    subprocess.run(['git','init','-q',str(work)],check=True,capture_output=True)
    node=base/'tools/node-v24.19.0-linux-x64/bin/node';cli=base/'runtime/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js'
    fence=replace(Fence.of(local='all',user='none',system='none',online=False,workdir=work,home=root/'home',
                   read=(base/'runtime',base/'tools/node-v24.19.0-linux-x64',*([package] if package else [])),write=(root/'home',agent,root/'cache'),
                   hosts=(host+':'+str(server.server_port),)),tmp=str(root/'tmp'))
    env={'PATH':str(node.parent)+':/usr/bin:/bin','HOME':str(root/'home'),'LANG':'C.UTF-8','TMPDIR':str(root/'tmp'),
         'PI_CODING_AGENT_DIR':str(agent),'PI_OFFLINE':'1','NODE_USE_ENV_PROXY':'1','GIT_TERMINAL_PROMPT':'0'}
    argv=namespace_command([*wrapper(fence),str(node),str(cli),'--offline','--no-approve','--no-extensions','--no-skills',
                 '--no-context-files','--no-prompt-templates','--no-mcp','--mode','json','--provider','workbench-fixture',
                 '--model','deepseek-flash','--thinking','off',*extra,'Perform the synthetic tool protocol.'])
    tick=time.perf_counter()
    try:
        try:child=subprocess.run(argv,cwd=work,env=env,capture_output=True,timeout=60)
        except subprocess.TimeoutExpired as error:
            child=types.SimpleNamespace(returncode=124,stdout=error.stdout or b'',stderr=error.stderr or b'')
    finally:server.shutdown();server.server_close()
    (root/'events.private.jsonl').write_bytes(child.stdout);(root/'stderr.private.log').write_bytes(child.stderr)
    source=(work/'smoke_value.py').read_text() if (work/'smoke_value.py').exists() else None
    committed=subprocess.run(namespace_command([*wrapper(fence),'git','rev-parse','HEAD']),cwd=work,env=env,capture_output=True)
    try:summary=summarize(child.stdout)
    except (ValueError,UnicodeError) as error:
        summary={'normalization_status':'FAILED','error_type':type(error).__name__}
    passed=(child.returncode==0 and len(requests)==5 and all(r['output_cap']==256000 for r in requests)
            and source=='def answer():\n    return 42\n' and committed.returncode==0
            and summary.get('total_tool_calls')==4 and summary.get('tool_errors')==0 and summary.get('terminal_errors_observed')==0
            and summary.get('agent_settled') and summary.get('provider_retries')==0 and summary.get('context_compactions')==0)
    proof={'status':'PASS_SYNTHETIC_PI_TOOL_CHAIN' if passed else 'FAIL','profile':profile,'exit':child.returncode,'requests':requests,
           'file_write_verified':source is not None,'test_tool_and_commit_verified':committed.returncode==0,
           'elapsed_seconds':time.perf_counter()-tick,'provider_inference_calls':0,'real_api_cash':0,
           'evidence_kind':'ZERO_MODEL_CONTROL','hidden_grade':'NOT_RUN',
           'normalized_trace':summary,'research_loop_background_control':'NOT_RUN' if profile=='P3' else 'N/A',
           'real_deepseek_metering_compatibility':'PENDING','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    exclusive_json(root/'receipt.json',proof);return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--profile',choices=('P0','P1','P2','P3'),default='P0');args=parser.parse_args()
    result=control(args.output,args.profile);print(json.dumps(result));raise SystemExit(0 if result['status'].startswith('PASS') else 1)
