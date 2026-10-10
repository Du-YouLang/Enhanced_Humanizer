"""Loopback owner UI, browser-origin and session checks enforced before every mutation."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit,parse_qs

from .memory import ROOT,canonical,now,safe_text,sha,uid
from .gitops import GitOps
from .review import Reviews
from .execution import Execution,settings

STATIC=Path(__file__).parent/'web'


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,memory,port,execution=None,repository=ROOT):
        super().__init__(('127.0.0.1',port),Handler)
        self.memory=memory;self.ops=GitOps(memory,repository);self.execution=execution or Execution(memory)
        self.sessions={};self.sessions_lock=threading.Lock();self.review_key=secrets.token_urlsafe(32)
        self.reviews=Reviews(memory,self.review_key)
        self.origin='http://127.0.0.1:'+str(self.server_port)


class Handler(BaseHTTPRequestHandler):
    server_version='Workbench/0.5'
    def log_message(self,*args):pass  # full traces/credentials never appear in HTTP access logs

    def output(self,status,value,mime='application/json; charset=utf-8',cookie=None):
        data=value if isinstance(value,bytes) else canonical(value)
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(data)

    def boundary(self):
        if self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):raise PermissionError('Loopback Host required')
        site=self.headers.get('Sec-Fetch-Site')
        if site in ('cross-site','same-site'):raise PermissionError('Cross-origin requests denied')
        origin=self.headers.get('Origin')
        if origin and origin!=self.server.origin:raise PermissionError('Origin denied')

    def session(self):
        cookies={}
        for item in self.headers.get('Cookie','').split(';'):
            if '=' in item:key,value=item.strip().split('=',1);cookies[key]=value
        with self.server.sessions_lock:value=self.server.sessions.get(cookies.get('workbench_owner',''))
        if not value or value['expires']<time.time():raise PermissionError('Owner browser session required')
        return value

    def do_GET(self):
        try:
            self.boundary();url=urlsplit(self.path);params=parse_qs(url.query)
            if url.path=='/health':return self.output(200,{'status':'ready','phase':'P5','bind':'loopback'})
            cookie=None
            if url.path=='/':
                try:self.session()
                except PermissionError:
                    # Local owner navigation is trusted; remote sites and isolated agents cannot mint this session.
                    if self.headers.get('Sec-Fetch-Mode')!='navigate' or self.headers.get('Sec-Fetch-Site')!='none':raise PermissionError('Open the workbench directly in the local owner browser')
                    identifier=secrets.token_urlsafe(32);session={'csrf':secrets.token_urlsafe(32),'expires':time.time()+12*3600}
                    with self.server.sessions_lock:self.server.sessions[identifier]=session
                    cookie='workbench_owner='+identifier+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'
            else:self.session()
            if url.path in ('/','/app.js','/style.css'):
                file=STATIC/({'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[url.path])
                return self.output(200,file.read_bytes(),{'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[url.path],cookie)
            memory=self.server.memory
            if url.path=='/api/state':
                value={'tasks':memory.list('task'),'runs':self.server.execution.visible_runs() if hasattr(self.server.execution,'visible_runs') else memory.list('run'),'attempts':memory.list('attempt'),
                       'judgments':memory.list('judgment'),'knowledge':memory.list('knowledge'),'actions':memory.list('action'),
                       'tests':memory.list('test_result'),'csrf':self.session()['csrf'],'active_run':self.server.execution.running,
                       'phase_budget':self.server.execution.limits,'current_ledger':None,'defaults':settings({}),
                       'git_delivery':'DEFERRED_BY_USER','product_pr_policy':'fresh human review for each exact head',
                       'judges':[{'id':'J0','status':'available','identity':'frozen tests and deterministic rules'},
                                 {'id':'J1','status':'available','identity':'original LAV logprob scoring'},
                                 {'id':'J2','status':'BLOCKED_REGION','identity':'Jev; zero requests'},
                                 {'id':'J3','status':'available','identity':'independent Sol structured rubric'}]}
                try:value['current_ledger']=memory.get('project_contract','p5-ledger')
                except KeyError:pass
                return self.output(200,value)
            if url.path=='/api/artifact':
                data=memory.read_artifact(params['id'][0]);return self.output(200,data,'text/plain; charset=utf-8')
            if url.path=='/api/diff':return self.output(200,self.server.ops.diff(params['node'][0]).encode(),'text/plain; charset=utf-8')
            if url.path=='/api/events':
                node=params.get('node',[None])[0]
                events=[e for e in memory.events() if node is None or e['id']==node or e['data'].get('attempt_id')==node]
                return self.output(200,events)
            raise KeyError('Unknown endpoint')
        except PermissionError as error:self.output(403,{'error':str(error)})
        except (ValueError,KeyError,FileNotFoundError) as error:self.output(400,{'error':str(error)[:500]})

    def do_POST(self):
        try:
            self.boundary();session=self.session()
            if self.headers.get('Origin')!=self.server.origin or self.headers.get('X-Workbench-CSRF')!=session['csrf']:raise PermissionError('Owner origin and CSRF capability required')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON body required')
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=1_000_000:raise ValueError('Bounded JSON body required')
            value=json.loads(self.rfile.read(size));safe_text(canonical(value).decode())
            if not isinstance(value,dict) or 'actor' in value or 'capability' in value:raise PermissionError('Identity is assigned by backend, not request body')
            result=self.action(urlsplit(self.path).path,value)
            self.output(200,result)
        except PermissionError as error:self.output(403,{'error':str(error)})
        except (ValueError,KeyError,TypeError,FileNotFoundError) as error:self.output(400,{'error':str(error)[:500]})
        except RuntimeError as error:self.output(409,{'error':safe_text(str(error)[:500],redact=True)})

    def action(self,path,value):
        memory=self.server.memory;node_id=value.get('node');reason=value.get('reason','')
        if path in ('/api/annotate','/api/reject','/api/route'):
            node=memory.get('attempt',node_id)
            if not isinstance(reason,str) or not reason.strip():raise ValueError('Decision reason required')
            return memory.record('action',uid(path.rsplit('/',1)[-1]),{'task_id':node['task_id'],'attempt_id':node_id,
                  'kind':path.rsplit('/',1)[-1],'reason':reason,'status':'RECORDED','head_sha':node.get('head_sha')},'human_owner')
        if path=='/api/fork':
            if not reason.strip():raise ValueError('Fork direction required')
            return self.server.ops.fork(node_id,reason,'human_owner')
        if path=='/api/handoff':return memory.handoff(node_id,'builder',reason or 'Continue from explicit saved evidence')
        if path=='/api/pr-intent':return self.server.reviews.intent(node_id,{'mode':'LOCAL_REVIEW_ONLY','repository':'unassigned','base':'unassigned'},reason or 'Prepare a reviewable proposal')|{'publication':'DEFERRED_BY_USER; target, ancestry, privacy and CI need preflight before a GitHub PR'}
        if path=='/api/approve':return self.server.reviews.approve(value['intent'],self.server.review_key,value['reviewed_head'],reason)
        if path=='/api/reject-pr':return self.server.reviews.reject(value['intent'],self.server.review_key,reason)
        if path=='/api/publish-pr':raise PermissionError('Git remote actions are deferred by the user; approval alone does not authorize another account or upload')
        if path=='/api/start':return self.server.execution.start(value.get('settings',{}),value.get('contract'))
        if path=='/api/retry':return self.server.execution.retry_pool(value['run'],value.get('settings'))
        if path in ('/api/pause','/api/stop','/api/resume'):return self.server.execution.request(value['run'],path.rsplit('/',1)[-1])
        if path=='/api/continue':return self.server.execution.continue_from(node_id,value.get('settings',{}),value.get('contract'))
        if path=='/api/export':return self.server.ops.export()
        raise KeyError('Unknown action')


def serve(memory,port=8765):
    server=WorkbenchServer(memory,port)
    private=memory.root/'server.json';private.write_bytes(canonical({'url':server.origin,'pid':__import__('os').getpid(),'bind':'127.0.0.1','started_at':now()}))
    print('Workbench ready: '+server.origin,flush=True)
    try:server.serve_forever()
    finally:server.server_close()
