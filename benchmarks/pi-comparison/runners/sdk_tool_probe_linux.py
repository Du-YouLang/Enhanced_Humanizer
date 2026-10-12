"""Fenced official Pi SDK tool/transport gate, separate from task acceptance.

Synthetic mode never touches a real key/ledger. Live mode requires a quiet main
controller and the existing aggregate ledger; this does not enable task smoke.
"""
import argparse
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

sys.path.insert(0,'/opt/workbench/source')
from hmz.coganchor.fence import Fence,wrapper
from p1_broker import protect_memory
from p2_candidates import exclusive_json,namespace_command
from p6_main_budget import MainLedger
from p6_network_policy import validate
from p6_network_recovery import RecoveryBroker
from events import summarize

BASE=Path('/opt/workbench/pi-comparison')
LOGIN=BASE/'subscription-login-20261012-v1/auth.json'
LEDGER=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')


def source_hashes(driver):
    files=[Path(__file__),driver]+[Path('/opt/workbench/source')/n for n in
        ('p1_broker.py','p1_budget.py','p6_main_budget.py','p6_network_recovery.py','p6_network_policy.py')]
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def require_sdk_controls(driver):
    hashes=source_hashes(driver);found=set()
    for p in BASE.glob('sdk-probe-fixture-*/receipt.json'):
        row=json.loads(p.read_text())
        if row.get('source_sha256')==hashes and row.get('model_calls')==0:
            found.add(row.get('status'))
    if not {'PASS_SYNTHETIC_SDK_TOOL_METERING','PASS_NEGATIVE_USAGE_CONTROL'}<=found:
        raise RuntimeError('Exact source requires positive and negative SDK/metering controls before live credentials')


def require_quiet_main():
    for p in Path('/opt/workbench/benchmark/private/main-launches').glob('*.json'):
        v=json.loads(p.read_text());stat=Path('/proc')/str(v['pid'])/'stat'
        if stat.exists():
            fields=stat.read_text().split()
            if fields[2]!='Z' and fields[21]==v['process_start_ticks']:
                raise RuntimeError('Live Pi probes are serial with active main experiments')


def control(root,driver,provider,payload):
    protect_memory()
    if os.getuid()==0 or not root.resolve().is_relative_to(BASE) or not root.name.startswith('sdk-probe-'):
        raise ValueError('Fresh project-private non-root probe required')
    if provider not in ('fixture','deepseek','subscription'):raise ValueError('Unknown provider route')
    if payload.get('fixture_fault') and provider!='fixture':raise ValueError('Synthetic faults require synthetic mode')
    if provider!='fixture':require_quiet_main();require_sdk_controls(driver)
    config=payload['budget'];validate(config)
    root.mkdir()
    for n in ('work','agent','home','tmp','cache'):(root/n).mkdir()
    work=root/'work';agent=root/'agent';node=BASE/'tools/node-v24.19.0-linux-x64/bin/node'
    sdk_driver=root/'sdk_tool_probe.mjs';sdk_driver.write_bytes(driver.read_bytes())
    ledger=MainLedger(root/'fixture-ledger.json' if provider=='fixture' else LEDGER,config)
    broker=server=None;seen=[];scope='PI_P0_TOOL_GATE/'+root.name
    if provider=='fixture':
        steps=[('write',{'path':'probe_value.py','content':'def answer():\n    return 42\n'}),
               ('bash',{'command':'python3 -c "from probe_value import answer; assert answer() == 42"'}),
               ('bash',{'command':'git add probe_value.py'}),
               ('bash',{'command':'git commit -m pi-tool-probe'})]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                index=len(seen);seen.append({'max_tokens':body.get('max_tokens'),'keys':sorted(body)})
                if index>len(steps):self.send_error(429);return
                delta={'role':'assistant'};reason='stop'
                if index<len(steps):
                    name,args=steps[index];reason='tool_calls'
                    delta['tool_calls']=[{'index':0,'id':'pi-gate-'+str(index),'type':'function',
                        'function':{'name':name,'arguments':json.dumps(args)}}]
                else:delta['content']='Tool connectivity probe finished.'
                rows=[{'id':'fixture-'+str(index),'model':'deepseek-flash','choices':[{'index':0,'delta':delta,'finish_reason':None}]},
                      {'id':'fixture-'+str(index),'model':'deepseek-flash','choices':[{'index':0,'delta':{},'finish_reason':reason}],
                       'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,
                                'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':10,'prompt_tokens_details':{'cached_tokens':0}}}]
                if payload.get('fixture_fault')=='usage':rows[-1]['usage']['total_tokens']=16
                self.send_response(200);self.send_header('Content-Type','text/event-stream')
                self.send_header('Connection','close');self.end_headers()
                for row in rows:self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        class FixtureBroker(RecoveryBroker):provider_endpoint='http://127.0.0.1:'+str(server.server_port)+'/chat/completions'
        broker=FixtureBroker('ZERO_MODEL_NO_CREDENTIAL',ledger,scope,time.monotonic()+900,config)
    elif provider=='deepseek':broker=RecoveryBroker(payload.pop('key'),ledger,scope,time.monotonic()+900,config)
    subscription=provider=='subscription'
    spec={'root':str(root),'work':str(work),'auth_path':str(LOGIN) if subscription else str(agent/'auth.json'),
          'models_path':None if subscription else str(agent/'models.json'),'provider':'openai' if subscription else 'workbench-bridge',
          'model':'gpt-6.1-sol' if subscription else 'deepseek-flash','role_requests':1000,
          'request_seconds':600,'role_seconds':900,'subscription':subscription}
    if subscription:
        if not LOGIN.is_file():raise RuntimeError('Independent Pi subscription login unavailable')
    else:
        exclusive_json(agent/'models.json',{'providers':{'workbench-bridge':{'api':'openai-completions','baseUrl':broker.url,
            'apiKey':broker.capability,'models':[{'id':'deepseek-flash','name':'Metered bridge' if provider=='deepseek' else 'Synthetic control',
             'reasoning':False,'input':['text'],'contextWindow':1048576,'maxTokens':256000,
             'samplingParams':{'max_tokens':256000},'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0},
             'compat':{'maxTokensField':'max_tokens','supportsStore':False}}]}}})
    exclusive_json(root/'spec.private.json',spec)
    subprocess.run(['git','init','-q',str(work)],capture_output=True,check=True)
    for k,v in [('user.name','WorkbenchProbe'),('user.email','probe@example.invalid'),('core.hooksPath','/dev/null'),('core.fsmonitor','false')]:
        subprocess.run(['git','-C',str(work),'config',k,v],capture_output=True,check=True)
    read=(BASE/'runtime',BASE/'tools/node-v24.19.0-linux-x64',sdk_driver,root/'spec.private.json')+((LOGIN,) if subscription else ())
    hosts=('chatgpt.com','auth.openai.com','api.openai.com') if subscription else (broker.host_port,)
    fence=replace(Fence.of(local='all',user='none',system='none',online=False,workdir=work,home=root/'home',
        read=read,write=(root/'home',agent,root/'cache'),hosts=hosts),tmp=str(root/'tmp'))
    env={'PATH':str(node.parent)+':/usr/bin:/bin','HOME':str(root/'home'),'LANG':'C.UTF-8','TMPDIR':str(root/'tmp'),
         'PI_CODING_AGENT_DIR':str(agent),'PI_OFFLINE':'1','NODE_USE_ENV_PROXY':'1','GIT_TERMINAL_PROMPT':'0'}
    tick=time.perf_counter();child=None
    try:
        if broker:broker.start()
        if subscription:ledger.reserve_codex_turn(scope,'gpt-6.1-sol')
        child=subprocess.run(namespace_command([*wrapper(fence),str(node),str(sdk_driver),str(root/'spec.private.json')]),
            cwd=work,env=env,capture_output=True,timeout=920)
    except subprocess.TimeoutExpired as e:
        child=subprocess.CompletedProcess([],124,e.stdout or b'',e.stderr or b'')
    except Exception as e:
        child=subprocess.CompletedProcess([],1,b'',type(e).__name__.encode())
    finally:
        if broker:broker.close()
        if server:server.shutdown();server.server_close()
    (root/'events.private.jsonl').write_bytes(child.stdout);(root/'stderr.private.log').write_bytes(child.stderr)
    try:summary=summarize(child.stdout)
    except (ValueError,UnicodeError) as e:summary={'normalization_status':'FAILED','error_type':type(e).__name__}
    # Candidate import and Git execution stay fenced without any auth/runtime read grant.
    vf=replace(Fence.of(local='all',user='none',system='none',online=False,workdir=work,home=root/'home'),tmp=str(root/'tmp'))
    check=namespace_command([*wrapper(vf),'python3','-c',"import runpy; assert runpy.run_path('probe_value.py')['answer']()==42"])
    def bounded(argv):
        try:return subprocess.run(argv,cwd=work,env=env,capture_output=True,timeout=20)
        except subprocess.TimeoutExpired as e:return subprocess.CompletedProcess(argv,124,e.stdout or b'',e.stderr or b'')
    value_test=bounded(check)
    commit_test=bounded(namespace_command([*wrapper(vf),'git','log','-1','--format=%H','--','probe_value.py']))
    rows=json.loads(ledger.path.read_text())['requests'] if ledger.path.exists() else []
    rows=[r for r in rows if r['experiment']==scope]
    fields={'input_tokens':'input_tokens','output_tokens':'output_tokens',
            'cache_read_tokens':'cache_read_input_tokens','cache_write_tokens':'cache_creation_input_tokens'}
    usage_ok=all(summary.get('usage',{}).get(k)==sum(r['usage'][v] for r in rows) for k,v in fields.items()) if rows and all('usage' in r for r in rows) else False
    passed=(child.returncode==0 and value_test.returncode==0 and commit_test.returncode==0 and bool(commit_test.stdout.strip())
        and summary.get('agent_settled') and summary.get('total_tool_calls',0)>=2 and not summary.get('tool_errors')
        and not summary.get('terminal_errors_observed') and not summary.get('provider_retries') and (subscription or usage_ok)
        and summary.get('model_ids_observed')==[{'provider':spec['provider'],'id':spec['model']}])
    if provider=='fixture':passed=passed and len(seen)==len(rows)==5 and all(r['max_tokens']==256000 for r in seen)
    negative=bool(payload.get('fixture_fault'))
    negative_pass=(negative and len(rows)==len(seen)==1 and rows[0]['status']=='RESERVED_UNKNOWN_USAGE'
        and summary.get('total_tool_calls')==0 and not (work/'probe_value.py').exists()
        and any(e.get('state')=='NON_RETRYABLE' and e.get('error_type')=='BudgetDenied' for e in broker.network_events))
    status='PASS_NEGATIVE_USAGE_CONTROL' if negative_pass else 'NOT_PASSED' if negative else 'PASS_SYNTHETIC_SDK_TOOL_METERING' if passed and provider=='fixture' else 'PASS_REAL_PROVIDER_TOOL_GATE' if passed else 'NOT_PASSED'
    pending=[e for e in (broker.network_events if broker else []) if e.get('state') in ('NETWORK_CHECK_REQUIRED','RETRY_PENDING')]
    if not passed and not negative and pending:
        status='NETWORK_CHECK_REQUIRED' if pending[-1]['state']=='NETWORK_CHECK_REQUIRED' else 'INFRA_RETRY_PENDING'
    receipt={'status':status,
        'evidence_kind':'ZERO_MODEL_CONTROL' if provider=='fixture' else 'REAL_PROVIDER_TOOL_PROBE','provider_route':provider,
        'normalized_trace':summary,'metered_wire_attempts':len(rows) if not subscription else 'UNVERIFIED_INTERNAL_WIRE_COUNT',
        'wire_output_caps':[r.get('output_token_cap') for r in rows],
        'settled_requests':sum('usage' in r for r in rows),'trace_ledger_usage_match':None if subscription else usage_ok,
        'model_failure':False if status in ('INFRA_RETRY_PENDING','NETWORK_CHECK_REQUIRED') else 'NOT_A_BENCHMARK',
        'elapsed_seconds':time.perf_counter()-tick,'exit':child.returncode,
        'independent_fenced_value_test':value_test.returncode==0,'independent_fenced_commit_test':bool(commit_test.stdout.strip()) and commit_test.returncode==0,
        'model_calls':0 if provider=='fixture' else summary.get('assistant_requests_observed','unavailable'),
        'subscription_turns_reserved':int(subscription),'api_cash_actual':0 if provider!='deepseek' else 'unavailable',
        'network_events':broker.network_events if broker else [],'fixture_fault':payload.get('fixture_fault'),'benchmark_acceptance':'NOT_RUN',
        'private_task_oracle':'NOT_USED','p1_p2_p3_profiles':'NOT_TESTED_BY_THIS_P0_PROBE',
        'own_subscription_auth_read_policy':'EXACT_FILE_READ_ONLY' if subscription else 'NO_REAL_AUTH_IN_AGENT',
        'source_sha256':source_hashes(driver)}
    exclusive_json(root/'receipt.json',receipt);return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--driver',type=Path,required=True)
    p.add_argument('--provider',choices=('fixture','deepseek','subscription'),required=True);a=p.parse_args()
    # Gate before accepting a live payload/key. Never parallelize real comparisons.
    if a.provider!='fixture':require_quiet_main();require_sdk_controls(a.driver)
    protect_memory()
    result=control(a.output,a.driver,a.provider,json.load(sys.stdin))
    print(json.dumps({'status':result['status'],'provider_route':a.provider,'model_calls':result['model_calls'],
        'metered_wire_attempts':result['metered_wire_attempts'],'benchmark_acceptance':'NOT_RUN'}))
    raise SystemExit(0 if result['status'].startswith('PASS') else 1)
