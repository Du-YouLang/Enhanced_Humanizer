"""Zero-paid-request diagnostics of the installed official DSH transport inside Humanize Fence."""

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import threading
import time

from deepseek_harness import DeepSeekHarness
from deepseek_harness_runtime import resolve_bundled_launch_args
from hmz.coganchor.fence import Fence, wrapper


def main():
    root=Path('/opt/workbench/runs/p1-transport-'+str(time.time_ns()))
    root.mkdir()
    rows=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            rows.append({'path':self.path,'keys':list(body),'model':body.get('model')})
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream')
            self.send_header('Connection','close');self.end_headers()
            chunks=[{'id':'mock','object':'chat.completion.chunk','model':'deepseek-flash',
                     'choices':[{'index':0,'delta':{'role':'assistant','content':'MOCK_TRANSPORT_ONLY'},'finish_reason':None}]},
                    {'id':'mock','model':'deepseek-flash','choices':[{'index':0,'delta':{},'finish_reason':'stop'}],
                     'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1}}]
            for chunk in chunks:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
    hostname=socket.gethostname()
    address=socket.gethostbyname(hostname)
    if not address.startswith('127.'):
        raise RuntimeError('Diagnostic requires distro hostname to resolve to loopback')
    server=ThreadingHTTPServer((address,0),Handler)
    server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start()
    output={'kind':'MOCK_TRANSPORT_ONLY','paid_requests':0,'cases':[]}
    try:
        for label,host,fenced in [('unfenced',address,False),('fenced-ip',address,True),('fenced-hostname',hostname,True)]:
            home=root/label;home.mkdir();scratch=home/'tmp';scratch.mkdir()
            launch=resolve_bundled_launch_args()
            if fenced:
                fence=Fence.of(local='none',user='none',system='none',online=False,workdir=root,home=Path.home(),
                               read=('/opt/workbench/.venv-linux',),write=(home,),hosts=(host+':'+str(server.server_port),))
                launch=(*wrapper(replace(fence,tmp=str(scratch))),*launch)
            env={'DEEPSEEK_API_KEY':'mock-no-' + 'provider-access','DEEPSEEK_BASE_URL':'http://'+host+':'+str(server.server_port),
                 'DSH_HOME':str(home),'PKG_NATIVE_CACHE_PATH':str(home/'cache'),'TMPDIR':str(scratch),'HUMANIZE_SENTRY':'off'}
            tick=time.perf_counter();before=len(rows)
            with DeepSeekHarness(_launch_args=(*launch,'--profile','sdk'),dsh_home=str(home),cwd=str(root),env=env,
                                 model='deepseek-flash',provider='deepseek-official',reasoning_effort='low',max_tokens=4096,
                                 request_timeout_seconds=30) as harness:
                result=harness.run('Return MOCK_TRANSPORT_ONLY; no tools.',session_id='mock-'+label)
            output['cases'].append({'label':label,'finish_reason':result.finish_reason,'answer':result.final_response,
                                    'elapsed_seconds':round(time.perf_counter()-tick,6),'requests':rows[before:]})
    finally:
        server.shutdown();server.server_close()
    output['verdict']='PASS' if [r['finish_reason'] for r in output['cases']]==['completed','error','completed'] else 'FAIL'
    Path('/opt/workbench/evidence/p1-transport.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output))


if __name__=='__main__':main()
