"""A local metering transport around the official API; no model/tool/agent logic."""

import asyncio
import ctypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time

import httpx

from p1_budget import BudgetDenied, Ledger, MAX_OUTPUT, ChatUsage


class Broker:
    def __init__(self,key,ledger,experiment,deadline):
        self.key=key
        self.ledger=ledger
        self.experiment=experiment
        self.deadline=deadline
        self.capability=secrets.token_urlsafe(32)
        self.serial=threading.Lock()
        self.denials=[]
        broker=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass  # Headers/credentials never enter request logs.

            def do_POST(self):
                if self.path!='/chat/completions':
                    self.send_error(403,'Only the fixed Chat Completions route is permitted');return
                auth=self.headers.get('x-api-key') or self.headers.get('Authorization','').removeprefix('Bearer ')
                if not secrets.compare_digest(auth,broker.capability):
                    self.send_error(403,'Local capability required');return
                if not broker.serial.acquire(blocking=False):
                    self.send_error(429,'P1 serial transport busy');return
                try:
                    if time.monotonic()>=broker.deadline:raise BudgetDenied('Experiment time cap reached')
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=2_000_000:raise BudgetDenied('Invalid request size')
                    self.connection.settimeout(10)
                    body=json.loads(self.rfile.read(length))
                    if body.get('model')!='deepseek-flash' or body.get('stream') is not True:
                        raise BudgetDenied('Fixed model and streaming mode required')
                    body['max_tokens']=min(body.get('max_tokens',MAX_OUTPUT),MAX_OUTPUT)
                    if type(body['max_tokens']) is not int or body['max_tokens']<=0:raise BudgetDenied('Invalid output cap')
                    # Drop unknown provider extensions, including possible billed server tools.
                    allowed={'model','stream','messages','max_tokens','thinking','reasoning_effort','temperature','stop','tools','tool_choice','stream_options','dsh_plugin_packages'}
                    if set(body)-allowed:raise BudgetDenied('Unsupported request extension')
                    if body.get('stream_options')!={'include_usage':True}:raise BudgetDenied('Exact usage reporting required')
                    if any(tool.get('type')!='function' for tool in body.get('tools',[])):
                        raise BudgetDenied('Billed server tools are not authorized')
                    index=broker.ledger.reserve_request(broker.experiment)
                    asyncio.run(broker.forward(self,body,index))
                except BudgetDenied as error:
                    broker.denials.append({'reason':str(error),'observed_monotonic':time.monotonic()})
                    if not getattr(self,'response_started',False):self.send_error(402,'P1 budget/policy denied')
                except Exception:
                    # Failed/aborted requests retain the entire reservation. Do not print request/error bodies.
                    try:
                        if not getattr(self,'response_started',False):self.send_error(502,'Metered upstream request failed; reservation retained')
                    except (OSError,ValueError):pass
                finally:
                    broker.serial.release()
        # DSH always bypasses HTTP proxies for literal loopback hosts. The distro hostname
        # resolves to loopback but is routed through Humanize's exact-host proxy correctly.
        self.host=socket.gethostname()
        address=socket.gethostbyname(self.host)
        if not address.startswith('127.'):
            raise RuntimeError('Metering requires distro hostname resolving to loopback')
        self.server=ThreadingHTTPServer((address,0),Handler)
        self.server.daemon_threads=True

    @property
    def url(self):return 'http://'+self.host+':'+str(self.server.server_port)

    @property
    def host_port(self):return self.host+':'+str(self.server.server_port)

    def start(self):
        threading.Thread(target=self.server.serve_forever,daemon=True).start()

    async def forward(self,handler,body,index):
        tick=time.perf_counter()
        tracker=ChatUsage()
        first=None
        data=[]
        async with asyncio.timeout(min(120,max(0.01,self.deadline-time.monotonic()))):
            async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=120) as client:
                async with client.stream('POST','https://api.deepseek.com/chat/completions',json=body,
                                         headers={'Authorization':'Bearer '+self.key,'accept':'text/event-stream'}) as response:
                    handler.send_response(response.status_code)
                    handler.send_header('Content-Type',response.headers.get('content-type','application/octet-stream'))
                    handler.send_header('Connection','close');handler.end_headers()
                    handler.response_started=True
                    if response.status_code!=200:
                        # Status is enough for diagnosis; never reflect arbitrary API errors containing secrets.
                        return
                    async for line in response.aiter_lines():
                        handler.wfile.write((line+'\n').encode());handler.wfile.flush()
                        if line.startswith('data:'):data.append(line[5:].lstrip())
                        elif line=='' and data:
                            raw='\n'.join(data);data=[]
                            row=raw if raw=='[DONE]' else json.loads(raw)
                            tracker.event(row)
                            if first is None and isinstance(row,dict) and any(c.get('delta') for c in row.get('choices',[])):
                                first=time.perf_counter()-tick
                    usage=tracker.verified()
                    request_id=response.headers.get('request-id') or response.headers.get('x-request-id') or response.headers.get('x-deepseek-request-id') or 'unavailable'
                    self.ledger.settle(index,usage,{'model_id':tracker.model,'http_status':200,'request_id':request_id,
                                                  'elapsed_seconds':round(time.perf_counter()-tick,6),
                                                  'first_delta_seconds':'unavailable' if first is None else round(first,6),
                                                  'protocol':'chat-completions','cache_creation_accounting':'not_applicable_in_protocol',
                                                  'bill_cash_usd':'unavailable'})

    def close(self):
        self.server.shutdown();self.server.server_close();self.key=''


def protect_memory():
    # Agent descendants cannot open this controller's /proc memory/environment/fd views.
    if os.name!='posix' or ctypes.CDLL(None,use_errno=True).prctl(4,0,0,0,0)!=0:
        raise RuntimeError('Controller memory protection unavailable')
