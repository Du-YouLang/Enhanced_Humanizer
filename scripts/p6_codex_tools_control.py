"""Real official Code Mode tool engine against loopback scripted SSE, zero providers.

Protocol reference: openai/codex rust-v0.172.0 sdk/python/tests/app_server_harness.py.
The fixture replaces only model responses, not Codex tools, execution host or OS fence.
"""
import asyncio
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading


def events(items,response):
    values=[{'type':'response.created','response':{'id':response}}]
    values += [{'type':'response.output_item.done','item':v} for v in items]
    values += [{'type':'response.completed','response':{'id':response,'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}}]
    return ''.join('event: '+v['type']+'\ndata: '+json.dumps(v)+'\n\n' for v in values).encode()


class Fixture:
    def __init__(self,code):
        self.requests=[];self.code=code
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                body=json.dumps({'object':'list','data':[{'id':'gpt-6.1-sol','object':'model','created':0,'owned_by':'fixture'}]}).encode()
                self.send_response(200);self.send_header('content-type','application/json');self.send_header('content-length',str(len(body)));self.end_headers();self.wfile.write(body)
            def do_POST(self):
                raw=self.rfile.read(int(self.headers.get('content-length','0')))
                if not self.path.endswith('/responses'):self.send_error(404);return
                owner.requests.append({'body':raw,'authorization_header_present':bool(self.headers.get('Authorization'))})
                n=len(owner.requests)
                if n>3:self.send_error(500);return
                item=({'type':'custom_tool_call','id':'ctc_fixture','call_id':'call_fixture','name':'exec','input':owner.code} if n==1 else
                      {'type':'message','id':'msg_fixture','role':'assistant','phase':'final_answer','content':[{'type':'output_text','text':'FIXTURE_DONE'}]})
                body=events([item],'resp_fixture_'+str(n))
                self.send_response(200);self.send_header('content-type','text/event-stream');self.send_header('content-length',str(len(body)));self.end_headers();self.wfile.write(body);self.wfile.flush()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*args):self.server.shutdown();self.server.server_close();self.thread.join(2)
    @property
    def host(self):return '127.0.0.1:'+str(self.server.server_address[1])


def one(payload,mode,missing=False):
    from p1_drivers import MeteredDriver
    from p3_worker_linux import RoleLedger
    from p6_main_budget import MainLedger
    from p2_candidates import candidate_env
    from p6_worker_linux import task_fence,native_turn
    from p6_trace_evidence import tool_trace
    from p6_refresh_protocol import verify_handoff_trace,execution_host_failure
    from hmz.flows import Permission
    with tempfile.TemporaryDirectory(prefix='codex-tool-control-',dir='/opt/workbench/tmp') as temp:
        root=Path(temp);work=root/'code';work.mkdir();env=candidate_env(root)
        code_home=Path(env['HOME'])/'.codex';code_home.mkdir();env['CODEX_HOME']=str(code_home)
        vendor=payload['vendor'];binary_dir=payload['missing_binary_directory'] if missing else vendor+'/bin'
        env['PATH']=binary_dir+':'+vendor+'/codex-path:'+env['PATH']
        env['CODEX_APP_SERVER_DISABLE_MANAGED_CONFIG']='1'
        for k in ('OPENAI_API_KEY','CODEX_API_KEY','DEEPSEEK_API_KEY','DEEPSEEK_BASE_URL'):env.pop(k,None)
        input_file=root/'input.json';raw=b'{"public":"tool execution control"}';input_file.write_bytes(raw)
        secret=root/'authority.txt';secret.write_text('private control authority')
        python=payload['prefix']+'/bin/python'
        script='\n'.join([
            'from pathlib import Path','import hashlib',
            'p=Path('+repr(str(input_file))+')','b=p.read_bytes()',
            'print(str(p))','print(len(b))','print(hashlib.sha256(b).hexdigest())',
            "print('EXECUTION_HOST_ACTUALLY_EXECUTED')",
            'try:'," Path('own-marker').write_text('EXECUTED')"," print('OWN_WRITE_ALLOWED')",
            'except PermissionError:'," print('OWN_WRITE_DENIED')",
            'try:',' open('+repr(str(secret))+",'ab').close()"," print('AUTHORITY_WRITE_ALLOWED_FAILURE')",
            'except PermissionError:'," print('AUTHORITY_WRITE_DENIED')"])
        compile(script,'fixture-actual-command','exec')
        import shlex
        command=shlex.quote(python)+' -B -c '+shlex.quote(script)
        js='text(await tools.exec_command('+json.dumps({'cmd':command,'max_output_tokens':3000})+'));'
        before=dict(os.environ)
        try:
            os.environ.clear();os.environ.update(env)
            with Fixture(js) as fixture:
                job={'root':str(root),'work':str(work),'backend':'codex','role':'verifier' if mode=='read' else 'builder',
                    'prefix':payload['prefix'],'input_file':str(input_file),'denied_paths':[str(secret)],
                    'authority_write_denied_paths':[str(secret)],'public_read_paths':[vendor,binary_dir],
                    'parent_namespace':payload['parent_namespace'],'prompt':'Execute the supplied fixture control; no actual model provider exists.',
                    'role_seconds':45}
                transform=task_fence(job)
                def narrow(fence):return transform(replace(fence,hosts=(fixture.host,)))
                permission=Permission(local=mode,user='none',system='none',online='none')
                ledger=MainLedger(root/'synthetic-ledger.json',payload['budget'],fixture=True)
                scope='REFRESH/refresh-20261126T000000Z/BIP-black-1/GPT61-Sol/Direct/direct'
                driver=MeteredDriver('builder=codex/gpt-6.1-sol:low',RoleLedger(ledger),scope,[],1,45,
                    permission=permission,fence_transform=narrow,external_readonly=mode=='read')
                # The installed official adapter deliberately restricts its
                # override field. Use its supported role-private CLI config,
                # exactly as the official SDK's local-provider fixture does.
                (code_home/'config.toml').write_text(
                    'model_provider = "fixture"\n[model_providers.fixture]\n'
                    'name = "Loopback fixture"\nbase_url = '+json.dumps('http://'+fixture.host+'/v1')+'\n'
                    'wire_api = "responses"\nrequires_openai_auth = false\nrequest_max_retries = 0\nstream_max_retries = 0\n')
                answer=asyncio.run(native_turn(driver,job))
                trace=tool_trace(root,max_bytes=8_000_000);receipt=verify_handoff_trace(trace,input_file,raw)
                outputs='\n'.join(str(json.loads(r['body']).get('input')) for r in fixture.requests)
                host_failure=execution_host_failure(trace)
                if missing:
                    if not host_failure or (work/'own-marker').exists():raise ValueError('Missing-host negative not rejected')
                else:
                    if receipt['status']!='HANDOFF_READ_RECEIPT_OBSERVED' or 'EXECUTION_HOST_ACTUALLY_EXECUTED' not in outputs or 'AUTHORITY_WRITE_DENIED' not in outputs:
                        raise ValueError('Actual command/read/authority proof missing: '+json.dumps(trace)[:3000])
                    expected='OWN_WRITE_DENIED' if mode=='read' else 'OWN_WRITE_ALLOWED'
                    if expected not in outputs or (work/'own-marker').exists()!=(mode=='all'):raise ValueError('Actual workspace permissions differ')
                if any(r['authorization_header_present'] for r in fixture.requests):raise ValueError('Fixture must never receive credentials')
                return {'status':'PASS_MISSING_HOST_NEGATIVE' if missing else 'PASS_OFFICIAL_CODE_MODE_ACTUAL_TOOL',
                    'permission':mode,'fixture_wire_requests':len(fixture.requests),'real_provider_calls':0,'real_ledger_writes':0,
                    'tool_read_receipt':receipt['status'],'authority_write_denied':not missing,'trace_records':len(trace['records'])}
        finally:os.environ.clear();os.environ.update(before)


def run_controls(payload):
    # Production roles each have their own process. Match that here too: the
    # official SDK caches a temporary fence launcher within a process.
    import subprocess
    from p2_candidates import namespace_command
    rows=[]
    for permission,missing in (('all',False),('read',False),('all',True)):
        p=dict(payload,case={'permission':permission,'missing':missing},parent_namespace=os.readlink('/proc/self/ns/pid'))
        result=subprocess.run(namespace_command([sys.executable,'-B',str(Path(__file__))]),
            input=json.dumps(p).encode(),capture_output=True,timeout=75)
        if result.returncode:raise RuntimeError('Actual tool fixture failed: '+result.stderr.decode(errors='replace')[-5000:])
        rows.append(json.loads(result.stdout))
    return {'status':'PASS_ACTUAL_CODEX_EXECUTION_CONTROLS','rows':rows,'real_provider_calls':0,'real_ledger_writes':0}


if __name__=='__main__':
    p=json.load(sys.stdin);print(json.dumps(one(p,p['case']['permission'],p['case']['missing'])))
