"""Serial Pi comparator using the official SDK and existing P6 oracle/fences.

Controls and experiments have separate receipts. The original P6 runtime is
imported read-only, never deployed over. All model use shares its original ledger.
"""
import argparse
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

sys.path[:0]=[str(Path(__file__).parent),'/opt/workbench/source','/opt/workbench/source/src']
from hmz.coganchor.fence import Fence,wrapper
from p1_broker import protect_memory
from p2_candidates import exclusive_json,namespace_command,digest
from p2_experiment_linux import ScopedLedger
from p6_main_budget import MainLedger,task_limits
from p6_network_recovery import RecoveryBroker
from p6_checkpoint_recovery import Stages,sha
from events import summarize,records
from pi_protocol import validate_plan,settled_usage_match,zero_numeric_returns,validate_deepseek_roles
import p6_main_runtime_linux as main
import p6_runtime_linux as shared

BASE=Path('/opt/workbench/pi-comparison')
RUNS=Path('/opt/workbench/benchmark/private/pi-comparison')
LOGIN=BASE/'subscription-login-20261012-v1/auth.json'
NODE=BASE/'tools/node-v24.19.0-linux-x64/bin/node'
LEDGER=Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')


def read(path):return json.loads(Path(path).read_bytes())


def quiet():
    for path in Path('/opt/workbench/benchmark/private/main-launches').glob('*.json'):
        row=read(path);proc=Path('/proc')/str(row['pid'])
        if row.get('boot_id') and row['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():continue
        if (proc/'stat').exists():
            fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
            if fields[0]!='Z' and fields[19]==row['process_start_ticks']:
                raise RuntimeError('Pi paid work is serial after active P6 work')


def resources(profile):
    packages={'P1':BASE/'packages/p1/package','P2':next((BASE/'packages/p2').glob('neuroforge-skills-*')),
              'P3':BASE/'packages/p3/package'}
    package=packages.get(profile)
    return {'extensions':[str(package/('extensions' if profile=='P1' else 'dist/extension.js'))] if profile in ('P1','P3') else [],
            'skills':[str(package/'skills')] if package else [],
            'prompts':[str(package/'prompts')] if profile=='P3' else [],
            'package':package,'other_packages':[str(p/('README.md' if key=='P2' else 'package.json')) for key,p in packages.items() if key!=profile]}


def execute(root,work,profile,provider,budget,prompt,role_seconds,driver,*,key=None,
            mode='task',fixture_fault=None,prefix=None,public_reads=(),gpu=False,denied=()):
    """One bounded official SDK session. Auth is only passed over private pipes."""
    r=resources(profile)
    for name in ('home','agent','tmp','cache'):(root/name).mkdir(exist_ok=True)
    scope='PI_FORMAL/'+root.parent.name+'/'+root.name
    ledger=MainLedger(root/'fixture-ledger.json' if provider=='fixture' else LEDGER,budget)
    ledger_before=read(LEDGER)
    ledger.validate(ledger_before)
    broker=None;server=None;seen=[];policies=[]
    deadline=time.monotonic()+role_seconds
    if mode not in ('auth-control','prl-control'):
        if provider=='fixture':
            steps=[('write',{'path':'probe_value.py','content':'def answer():\n    return 42\n'}),
                   ('bash',{'command':'python3 -c "from probe_value import answer; assert answer()==42"'}),
                   ('bash',{'command':'git add probe_value.py'}),('bash',{'command':'git commit -m pi-tool-control'})]
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_POST(self):
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    i=len(seen);seen.append({'max_tokens':body.get('max_tokens'),'thinking':body.get('thinking'),'reasoning_effort':body.get('reasoning_effort'),
                                            'message_roles':[m.get('role') for m in body.get('messages',[])]})
                    if i>len(steps):self.send_error(429);return
                    delta={'role':'assistant'};reason='stop'
                    if i<len(steps):
                        tool,args=steps[i];reason='tool_calls';delta['tool_calls']=[{'index':0,'id':'control-'+str(i),'type':'function','function':{'name':tool,'arguments':json.dumps(args)}}]
                    else:delta['content']='Synthetic control finished.'
                    usage={'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':10}
                    if fixture_fault=='usage':usage['total_tokens']=16
                    rows=[{'id':'fixture-'+str(i),'model':'deepseek-flash','choices':[{'index':0,'delta':delta,'finish_reason':None}]},
                          {'id':'fixture-'+str(i),'model':'deepseek-flash','choices':[{'index':0,'delta':{},'finish_reason':reason}],'usage':usage}]
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Connection','close');self.end_headers()
                    for row in rows:self.wfile.write(('data: '+json.dumps(row)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
        if provider in ('fixture','deepseek'):
            class Metered(RecoveryBroker):
                async def exchange(self,body,index,seconds):
                    policy={k:body.get(k) for k in ('max_tokens','thinking','reasoning_effort','model')}
                    policies.append(policy)
                    validate_deepseek_roles(body)
                    if policy!={'max_tokens':256000,'thinking':{'type':'enabled'},'reasoning_effort':'low','model':'deepseek-flash'}:
                        raise ValueError('Prospective DeepSeek model/output/reasoning wire gate failed before provider access')
                    return await super().exchange(body,index,seconds)
            if server:Metered.provider_endpoint='http://127.0.0.1:'+str(server.server_port)+'/chat/completions'
            broker=Metered('ZERO_PROVIDER_FIXTURE' if provider=='fixture' else key,
                ScopedLedger(ledger,scope,request_cap=1000,cash_cap=None),scope,deadline,budget)
            broker.start()
    subscription=provider=='subscription' and mode not in ('auth-control','prl-control')
    models=root/'agent/models.json'
    if broker:
        exclusive_json(models,{'providers':{'workbench-bridge':{'api':'openai-completions','baseUrl':broker.url,'apiKey':broker.capability,
            'models':[{'id':'deepseek-flash','name':'Explicit metered DeepSeek' if provider=='deepseek' else 'ZERO_PROVIDER_SYNTHETIC',
                'reasoning':True,'input':['text'],'contextWindow':1048576,'maxTokens':256000,
                'samplingParams':{'max_tokens':256000},'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0},
                'compat':{'maxTokensField':'max_tokens','supportsStore':False,'thinkingFormat':'deepseek',
                          'supportsDeveloperRole':fixture_fault=='developer'}}]}}})
    spec={'root':str(root),'work':str(work),'profile':profile,'mode':mode,'role_seconds':role_seconds,'request_seconds':600,'role_requests':1000,
          'parent_namespace':os.readlink('/proc/self/ns/pid'),
          'provider':'openai' if subscription else 'workbench-bridge','model':'gpt-6.1-sol' if subscription else 'deepseek-flash',
          'models_path':None if subscription or mode in ('auth-control','prl-control') else str(models),'subscription':subscription,
          **{k:r[k] for k in ('extensions','skills','prompts')},'tool_names':['read','bash','edit','write',*(['sci_find'] if profile=='P1' else ['prl_*'] if profile=='P3' else [])],
          'prompt':prompt,'denied':[str(LOGIN),'/opt/workbench/state/codex/auth.json',*map(str,denied),*r['other_packages']]}
    path=root/'spec.private.json';exclusive_json(path,spec)
    reads=[BASE/'runtime',BASE/'tools/node-v24.19.0-linux-x64',driver,path,*public_reads]
    if r['package']:reads.append(r['package'])
    if prefix:reads.append(prefix)
    if gpu:reads.append('/usr/lib/wsl')
    writes=[root/'home',root/'agent',root/'cache']+(['/dev/dxg'] if gpu else [])
    hosts=('chatgpt.com','auth.openai.com','api.openai.com') if subscription else (broker.host_port,) if broker else ()
    fence=replace(Fence.of(local='all',user='none',system='none',online=False,workdir=work,home=root/'home',
        read=tuple(reads),write=tuple(writes),hosts=hosts),tmp=str(root/'tmp'))
    env={'PATH':(str(prefix)+'/bin:' if prefix else '')+str(NODE.parent)+':/usr/bin:/bin','HOME':str(root/'home'),'LANG':'C.UTF-8',
         'TMPDIR':str(root/'tmp'),'XDG_CACHE_HOME':str(root/'cache'),'PI_CODING_AGENT_DIR':str(root/'agent'),'PI_OFFLINE':'1',
         'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_NOSYSTEM':'1','GIT_TERMINAL_PROMPT':'0','PYTHONHASHSEED':'42','HUMANIZE_SENTRY':'off'}
    if gpu:env.update(LD_LIBRARY_PATH='/usr/lib/wsl/lib',CUPY_CACHE_DIR=str(root/'cache/cupy'),CUDA_CACHE_PATH=str(root/'cache/cuda'))
    auth=read(LOGIN) if subscription else {'openai':{'type':'api_key','key':'NONSECRET_PIPE_CONTROL'}} if mode in ('auth-control','prl-control') else {}
    auth_source_sha256=sha(LOGIN) if subscription else None
    refresh_read,refresh_write=os.pipe();refresh=[]
    def drain():
        with os.fdopen(refresh_read,'rb') as f:refresh.append(f.read(1_000_001))
    reader=threading.Thread(target=drain,daemon=True);reader.start()
    tick=time.perf_counter();peak={'rss_kib':0,'processes':0,'threads':0};stopped=None
    try:
        if subscription:ledger.reserve_codex_turn(scope,'gpt-6.1-sol')
        with (root/'events.private.jsonl').open('xb') as out,(root/'stderr.private.log').open('xb') as err:
            child=subprocess.Popen(namespace_command([*wrapper(fence),str(NODE),str(driver),str(path)]),cwd=work,env=env,
                stdin=subprocess.PIPE,stdout=out,stderr=err,pass_fds=(refresh_write,),start_new_session=True)
            child.stdin.write(json.dumps({'credentials':auth,'credential_fd':refresh_write}).encode());child.stdin.close()
            auth={};os.close(refresh_write);refresh_write=None
            from p6_science_sandbox import process_usage
            while child.poll() is None:
                usage=process_usage(child.pid);peak={k:max(peak[k],v) for k,v in usage.items()}
                if usage['rss_kib']>8192*1024 or usage['processes']>64 or usage['threads']>512:stopped='ROLE_RESOURCE_LIMIT'
                if time.monotonic()>=deadline:stopped='ROLE_TIMEOUT'
                if stopped:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=3)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                    break
                time.sleep(.1)
    finally:
        if refresh_write is not None:os.close(refresh_write)
        if 'child' in locals() and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        if broker:broker.close()
        if server:server.shutdown();server.server_close()
    reader.join(timeout=5)
    auth_pipe_ok=bool(refresh and len(refresh[0])<=1_000_000)
    if auth_pipe_ok:
        updated=json.loads(refresh[0]);auth_pipe_ok=set(updated)=={'openai'}
        if subscription and updated['openai'] is not None:
            # Preserve the sole project-owned original before official OAuth refresh.
            old=read(LOGIN)
            if old.get('openai')!=updated['openai']:
                if sha(LOGIN)!=auth_source_sha256:
                    raise RuntimeError('Independent login changed during this session; refuse overwriting it')
                backup=LOGIN.parent/('auth-before-'+root.name+'.private.json')
                with backup.open('xb') as f:f.write(LOGIN.read_bytes())
                old['openai']=updated['openai'];temp=LOGIN.with_name('auth-refresh.tmp')
                temp.write_text(json.dumps(old),encoding='utf-8');temp.chmod(0o600);os.replace(temp,LOGIN)
    refresh=[]
    raw=(root/'events.private.jsonl').read_bytes()
    try:summary=summarize(raw);events=list(records(raw))
    except (ValueError,UnicodeError):summary={'normalization_status':'FAILED'};events=[]
    isolation=next((e for e in events if e['type']=='credential_isolation'),{})
    isolated=isolation.get('denied')==['DENIED']*len(spec['denied'])
    finish=next((e for e in events if e['type']=='formal_finished'),None)
    if mode in ('auth-control','prl-control'):
        passed=child.returncode==0 and isolated and auth_pipe_ok and any(e['type']=='auth_control_pass' for e in events)
        status='PASS_AUTH_MEMORY_AND_RESOURCE_CONTROL' if passed else 'CONTROL_FAILED'
    else:
        passed=child.returncode==0 and bool(finish) and isolated and auth_pipe_ok and summary.get('agent_settled') and not summary.get('terminal_errors_observed')
        passed=passed and summary.get('model_ids_observed')==[{'provider':spec['provider'],'id':spec['model']}]
        status='COMPLETED' if passed else 'TIMEOUT' if stopped else 'INFRA_FAIL'
    rows=[r for r in read(ledger.path)['requests'] if r['experiment']==scope] if ledger.path.exists() else []
    settled=[r for r in rows if 'usage' in r]
    usage_match=settled_usage_match(summary,rows)
    if mode=='task' and provider in ('deepseek','fixture') and status=='COMPLETED' and not usage_match:status='INFRA_FAIL'
    if any(e['type']=='message_end' and e.get('message',{}).get('role')=='assistant' and e['message'].get('stopReason')=='length' for e in events):status='OUTPUT_LIMIT'
    if broker and any(e.get('state') in ('NETWORK_CHECK_REQUIRED','RETRY_PENDING') for e in broker.network_events):status='INFRA_RETRY_PENDING'
    worker={'status':status,'root':str(root),'work':str(work),'scope':scope,'wall_seconds':time.perf_counter()-tick,
        'elapsed_seconds':time.perf_counter()-tick,'usage':[],'provider':provider,'profile':profile,'summary':summary,
        'sdk_dispatches':finish.get('transport_dispatches') if finish else 'unavailable',
        'wire_count':len(rows) if not subscription else 'UNVERIFIED_INTERNAL_WIRE_COUNT',
        'wire_policies':policies,'auth_memory_pipe_verified':auth_pipe_ok,'auth_file_reads_denied':isolated,
        'known_trace_ledger_usage_match':usage_match if provider in ('deepseek','fixture') and mode=='task' else None,
        'unknown_wire_usage_reservations':len(rows)-len(settled),
        'controller_peak_process_tree':peak,'controller_stop_reason':stopped,
        'network_events':broker.network_events if broker else [],'fixture_http':seen,'fixture_fault':fixture_fault,
        'network_recovery_events':broker.network_events if broker else [],'broker_denials':broker.denials if broker else [],
        'api_cash_actual':'unavailable' if provider=='deepseek' else 0,'model_identity':spec['model'],
        'resource_observations':[e for e in events if e['type'] in ('resources_observed','session_bound')],
        'prl_control':[e for e in events if e['type']=='prl_control_pass'],
        'evidence_kind':'ZERO_MODEL_CONTROL' if provider=='fixture' or mode=='auth-control' else 'REAL_MODEL'}
    from p6_main_contract import classify_role_completion
    worker=classify_role_completion(worker)
    exclusive_json(root/'controller-outcome.json',worker)
    return worker


def fixture_controls(payload):
    root=RUNS/payload['run_id'];root.mkdir(parents=True);results={};driver=Path(__file__).with_name('pi_session.mjs')
    canary=root/'control-canary';canary.write_text('not for model tools')
    for profile in ('P0','P1','P2','P3'):
        dest=root/(profile+'-auth');dest.mkdir();(dest/'code').mkdir()
        results[profile]=execute(dest,dest/'code',profile,'fixture',payload['budget'],'No models.',900,driver,
                                mode='auth-control',denied=[canary])
    for label,fault in [('positive',None),('negative-usage','usage'),('negative-developer','developer')]:
        dest=root/label;dest.mkdir();work=dest/'code';work.mkdir()
        shared.trusted_git(work,'init','-q')
        shared.trusted_git(work,'config','user.name','Pi control');shared.trusted_git(work,'config','user.email','control@example.invalid')
        results[label]=execute(dest,work,'P0','fixture',payload['budget'],
            'Create probe_value.py defining answer() returning 42. Use write, then bash to test and commit it. No installs or other directories.',
            900,driver,fixture_fault=fault,denied=[canary])
    dest=root/'P3-background';dest.mkdir();work=dest/'code';work.mkdir()
    shared.trusted_git(work,'init','-q')
    shared.trusted_git(work,'config','user.name','Pi control');shared.trusted_git(work,'config','user.email','control@example.invalid')
    (work/'control.txt').write_text('zero model control')
    shared.trusted_git(work,'add','.');shared.trusted_git(work,'commit','-qm','Control baseline')
    results['P3-background']=execute(dest,work,'P3','fixture',payload['budget'],'No models.',900,driver,
                                     mode='prl-control',denied=[canary])
    oracles=oracle_controls(root,payload)
    positive=results['positive'];negative=results['negative-usage']
    developer=results['negative-developer']
    good=(all(results[p]['status']=='PASS_AUTH_MEMORY_AND_RESOURCE_CONTROL' for p in ('P0','P1','P2','P3'))
          and positive['status']=='COMPLETED' and positive['wire_count']==5 and positive['summary']['total_tool_calls']==4
          and negative['status']!='COMPLETED' and negative['wire_count']==1 and not negative['summary'].get('total_tool_calls')
          and developer['status']!='COMPLETED' and developer['wire_count']==1 and not developer['summary'].get('total_tool_calls')
          and developer['fixture_http']==[]
          and results['P3-background']['status']=='PASS_AUTH_MEMORY_AND_RESOURCE_CONTROL' and bool(results['P3-background']['prl_control'])
          and oracles['status']=='PASS_PUBLIC_PRIVATE_ORACLES'
          and all(r['status']=='RESERVED_UNKNOWN_USAGE' for r in read(root/'negative-usage/fixture-ledger.json')['requests']))
    receipt={'status':'PASS_FORMAL_SDK_CONTROLS' if good else 'CONTROL_FAILED','model_calls':0,'results':results,
        'source_sha256':payload['source_sha256'],'p3_background_checkpoint_control':results['P3-background']['prl_control'],
        'oracle_controls':oracles}
    exclusive_json(root/'receipt.json',receipt)
    return {'status':receipt['status'],'model_calls':0,'profiles':{p:results[p]['status'] for p in ('P0','P1','P2','P3')},
            'positive':positive['status'],'negative':negative['status'],'root':str(root)}


def oracle_controls(root,payload):
    """Actual original Black/GC oracles; gold/review data never enter an agent."""
    import ast,copy,shutil
    manifest=read('/opt/workbench/benchmark/private/main-runs/p6-main-execute-SCI-GRANGER-GPU-20261013T060508Z/control/run-contract.json')['manifest']
    task_row=next(t for t in manifest['tasks'] if t['task_id']=='BIP-black-2')
    task=main.public_task({'task':task_row})
    shared.ACTIVE.clear();shared.ACTIVE.update(task=task,fixture_url=None)
    controls=read(main.BASE/'science/private/public-main-controls-frozen-v2.json')
    ref=next(t for t in controls['tasks'] if t['task_id']=='BIP-black-2')
    gold=read(ref['receipt'])['gold']
    black={'positive':main.public_test(gold,True),'negative':main.public_test(task['base'],True)}
    sys.path.insert(0,'/opt/workbench/benchmark/envs/science-tms-v1/lib/python3.12/site-packages')
    from p6_gc_grader import grade
    from p6_gc_source_policy import validate_gc_source
    old=main.BASE/'private/main-runs/p6-main-execute-SCI-GRANGER-GPU-20261013T060508Z'
    review_path=Path('/opt/workbench/recovery/p6-granger-acceptance-20261013-v3/state/plan.json')
    if sha(review_path)!='7387534a205d50419768fdfe1cdd94e38555c607cd9932a0b64364960c6826f1':raise ValueError('Original GC review changed')
    review=read(review_path)['source_reviews']['DS0']
    positive=root/'gc-positive';negative=root/'gc-negative';positive.mkdir();negative.mkdir()
    source=(old/'native-ds/code/gc_cupy.py').read_text()
    (positive/'gc_cupy.py').write_text(source)
    wrong=zero_numeric_returns(source,'compute_gc')
    (negative/'gc_cupy.py').write_text(wrong)
    prefix=main.BASE/'envs/science-gc-v1';materials=main.BASE/'science/intake/gc'
    gc={'positive':grade(positive,materials,prefix,source_review=review),
        'negative_wrong_numbers':grade(negative,materials,prefix)}
    refused=False
    try:validate_gc_source(source+'\ndef forbidden_download(x):\n    return x.get()\n')
    except ValueError:refused=True
    good=(black['positive']['verdict']=='PASS' and black['negative']['verdict']=='FAIL'
          and gc['positive']['verdict']=='PASS' and gc['negative_wrong_numbers']['verdict']=='FAIL' and refused)
    value={'status':'PASS_PUBLIC_PRIVATE_ORACLES' if good else 'CONTROL_FAILED','black':black,'gc':gc,
           'device_download_negative_refused':refused,'model_calls':0}
    exclusive_json(root/'oracle-controls.json',value)
    return value


def require_controls(payload):
    for path in RUNS.glob('formal-controls-*/receipt.json'):
        value=read(path)
        if (value.get('status')=='PASS_FORMAL_SDK_CONTROLS' and value.get('model_calls')==0
                and value.get('source_sha256')==payload['source_sha256']):
            return {'path':str(path),'sha256':sha(path)}
    raise RuntimeError('Exact comparator source needs successful zero-model controls')


def real_tool_gates(payload):
    quiet();control=require_controls(payload)
    root=RUNS/payload['run_id'];root.mkdir(parents=True);results={}
    for provider in ('deepseek','subscription'):
        quiet();dest=root/provider;dest.mkdir();work=dest/'code';work.mkdir()
        shared.trusted_git(work,'init','-q');shared.trusted_git(work,'config','user.name','Pi live tool gate')
        shared.trusted_git(work,'config','user.email','gate@example.invalid')
        prompt='This is a tool connectivity gate. Create probe_value.py defining answer() returning integer 42. Use write and bash to test it, then commit the file. No installs, subagents, credentials or other directories. Give a short final summary.'
        w=execute(dest,work,'P0',provider,payload['budget'],prompt,900,Path(__file__).with_name('pi_session.mjs'),key=payload.get('key'))
        # Verify model-produced code and Git only through the existing OS fence.
        vf=replace(Fence.of(local='all',user='none',system='none',online=False,workdir=work,home=dest/'home'),tmp=str(dest/'tmp'))
        def check(argv):
            return subprocess.run(namespace_command([*wrapper(vf),*argv]),cwd=work,capture_output=True,timeout=20)
        test=check(['python3','-c',"import runpy;assert runpy.run_path('probe_value.py')['answer']()==42"])
        commit=check(['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','log','-1','--format=%H','--','probe_value.py'])
        valid=w['status']=='COMPLETED' and test.returncode==0 and commit.returncode==0 and bool(commit.stdout.strip()) and w['summary'].get('total_tool_calls',0)>=2
        results[provider]={'worker':w,'independent_value_pass':test.returncode==0,'independent_commit_pass':commit.returncode==0 and bool(commit.stdout.strip()),
                           'status':'PASS_REAL_PROVIDER_TOOLS' if valid else 'NOT_PASSED'}
        exclusive_json(dest/'tool-gate.json',results[provider])
        if not valid:break  # Never automatically replay a failed paid gate.
    receipt={'status':'PASS_REAL_PROVIDER_TOOLS' if len(results)==2 and all(x['status']=='PASS_REAL_PROVIDER_TOOLS' for x in results.values()) else 'NOT_PASSED',
             'results':results,'source_sha256':payload['source_sha256'],'controls':control,'benchmark_acceptance':'NOT_RUN'}
    exclusive_json(root/'receipt.json',receipt)
    return {'status':receipt['status'],'providers':{k:v['status'] for k,v in results.items()},'root':str(root)}


def require_real_tools(payload):
    for path in RUNS.glob('formal-live-tools-*/receipt.json'):
        v=read(path)
        if v.get('status')=='PASS_REAL_PROVIDER_TOOLS' and v.get('source_sha256')==payload['source_sha256']:
            return {'path':str(path),'sha256':sha(path)}
    raise RuntimeError('Exact source requires both actual provider tool gates')


def compare(payload):
    quiet();control=require_controls(payload);live=require_real_tools(payload)
    plan=validate_plan(payload['plan']);body=dict(plan);expected=body.pop('plan_sha256')
    if digest(body)!=expected or body['source_sha256']!=payload['source_sha256']:
        raise ValueError('Frozen Pi plan changed')
    if len(body['cells'])!=16 or body['bulk_256_enabled'] is not False:
        raise ValueError('Only the prespecified sixteen-cell comparison is authorized')
    root=RUNS/payload['run_id'];root.mkdir(parents=True)
    exclusive_json(root/'plan.json',plan)
    (root/'control').mkdir();(root/'control/canary').write_text('Pi controller only')
    stages=Stages(root/'control/stages');results=[]
    exclusive_json(root/'ledger-before.private.json',read(LEDGER))
    for cell in body['cells']:
        quiet()
        name=cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
        task_row=next(t for t in body['main_manifest']['tasks'] if t['task_id']==cell['task_id'])
        task_payload={'task':task_row,'manifest':body['main_manifest'],'budget':payload['budget']}
        if task_row['family']=='scientific':
            sys.path.insert(0,'/opt/workbench/benchmark/envs/science-tms-v1/lib/python3.12/site-packages')
            import p6_science_main_linux as science
            task=science.task(task_payload);tester=science.test
            from p6_gate_policy import GENERATION_RULES
            task['prompt']+='\n'+GENERATION_RULES
        else:task=main.public_task(task_payload);tester=main.public_test
        role=task_limits(payload['budget'],task_row)['role_seconds']
        shared.ACTIVE.clear();shared.ACTIVE.update(root=root,task=task,payload=task_payload,
            ledger=MainLedger(LEDGER,payload['budget']),key='',deadline=time.monotonic()+role,
            generation_seconds=role,active_seconds=role,workers={},main_phase=True,defer_hidden=True,fixture_url=None)
        shared.LEDGER_PATH=LEDGER;shared.test_source=tester
        # Existing helper clones an independent baseline Git store. Pi retains
        # its own official agent loop/tools rather than replacing a Harness.
        descriptor,_=main.job(name,'pi')
        dest=Path(descriptor['root']);work=Path(descriptor['work'])
        prompt=descriptor['prompt']+'\nFinal deliverable must be committed cleanly in this original worktree. If you use research task worktrees, bring the final implementation back here and commit it. Preserve original tests and fixtures. No model subagents or credential access.'
        worker=stages.run(name+'-model',lambda:execute(dest,work,cell['profile'],cell['provider'],payload['budget'],prompt,role,
            Path(__file__).with_name('pi_session.mjs'),key=payload.get('key'),prefix=Path(task['prefix']),
            public_reads=descriptor['public_read_paths'],gpu=task.get('gpu_coding',False),
            denied=descriptor['denied_paths']))
        shared.ACTIVE['workers'][name]=worker
        candidate=stages.run(name+'-public',lambda:shared.candidate(name,worker))
        exclusive_json(dest/'frozen-program.json',{'head_commit':candidate.get('head_commit'),
            'candidate_sha256':digest(candidate),'program_sha256':digest({'patch':candidate.get('patch'),'source':candidate.get('source')}),
            'private_results_seen':False,'cell':cell,'plan_sha256':expected})
        if worker['status']=='COMPLETED' and candidate['verdict']=='PASS':
            def accept():
                try:return tester(work,True)
                except ValueError as error:
                    return {'verdict':'INDETERMINATE' if 'review' in str(error).lower() else 'FAIL',
                            'error_type':type(error).__name__,'reason':str(error)[:500],'elapsed_seconds':0}
                except (OSError,ImportError,KeyError,TypeError) as error:
                    return {'verdict':'INFRA_FAIL','error_type':type(error).__name__,'reason':str(error)[:500],'elapsed_seconds':0}
            acceptance=stages.run(name+'-acceptance',accept)
        else:acceptance={'verdict':'NOT_RUN','reason':'Public or completion gate did not pass','elapsed_seconds':0}
        outcome=acceptance['verdict'] if worker['status']=='COMPLETED' and candidate['verdict']=='PASS' else 'FAIL' if worker['status']=='COMPLETED' else worker['status']
        row={'cell':cell,'plan_sha256':expected,'outcome':outcome,'candidate_verdict':candidate['verdict'],
             'worker_status':worker['status'],'head_commit':candidate.get('head_commit'),'acceptance':acceptance,
             'scope':worker['scope'],'task_environment_sha256':task['seal']['env_sha256'],'base_commit':task['base_commit'],
             'hidden_suite_sha256':task['hidden_suite_sha256'],'role_seconds':role,
             'coding_and_public_seconds':worker['wall_seconds']+candidate.get('test_report',{}).get('elapsed_seconds',0),
             'usage':worker['summary'].get('usage'),'sdk_dispatches':worker['sdk_dispatches'],
             'provider_wire_attempts':worker['wire_count'],'api_cash_actual':worker['api_cash_actual'],
             'evidence_kind':'REAL_MODEL','harness':'official Pi SDK 1.1.0','model_requested':worker['model_identity']}
        exclusive_json(dest/'result.json',row);results.append(row)
        exclusive_json(root/('progress-'+str(len(results)).zfill(2)+'.json'),{'completed_cells':len(results),'last':row})
        if worker['status']=='INFRA_RETRY_PENDING':break
        ledger=read(LEDGER)
        if len(ledger['requests'])>=10000 or ledger['cash_bound_nano']>=200_000_000_000:break
    receipt={'status':'FORMAL_COMPARISON_COMPLETED' if len(results)==16 else 'FORMAL_COMPARISON_INTERRUPTED',
             'results':results,'completed_cells':len(results),'total_cells':16,'source_sha256':payload['source_sha256'],
             'controls':control,'real_provider_tools':live,'main_results_replayed':False,
             'failed_cells_retained':True,'api_cash_actual':'unavailable','external_release_authorized':False}
    exclusive_json(root/'receipt.json',receipt)
    exclusive_json(root/'ledger-after.private.json',read(LEDGER))
    return {'status':receipt['status'],'completed_cells':len(results),'root':str(root)}


if __name__=='__main__':
    protect_memory()
    if os.getuid()==0:raise RuntimeError('Non-root only')
    payload=json.load(sys.stdin)
    for path,expected in payload['source_sha256'].items():
        if sha(path)!=expected:raise ValueError('Pinned comparator source changed')
    try:
        if payload['mode']!='controls':
            plan=validate_plan(payload['plan'])
            for path,expected in plan['main_manifest']['runner_source_sha256'].items():
                if sha(path)!=expected:raise ValueError('Original P6 runtime changed')
        fn={'controls':fixture_controls,'tools':real_tool_gates,'compare':compare}[payload['mode']]
        print(json.dumps(fn(payload)),flush=True)
    except Exception as error:
        import traceback
        root=RUNS/payload['run_id']
        if root.exists() and not (root/'failure.json').exists():
            exclusive_json(root/'failure.json',{'status':'INFRA_FAIL','error_type':type(error).__name__,'traceback':traceback.format_exc(),'automatic_model_replay':False})
        raise
