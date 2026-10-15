"""Metered provider reconnects, buffering partial SSE before any tool delivery.

This is a transport adapter around the existing Harness, never an agent loop.
Every wire attempt reserves the shared ledger; unknown usage is never refunded.
"""
import asyncio
import json
import threading
import time

from p1_broker import Broker
from p1_budget import BudgetDenied, ChatUsage
from p6_network_policy import NetworkCheckRequired, NetworkRetryPending, validate

TRANSIENT_HTTP = frozenset((408, 429, 500, 502, 503, 504))
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class TransientNetworkError(RuntimeError):
    pass


def retryable(error):
    # Permission denial, malformed SSE/usage and credentials are not reconnects.
    if isinstance(error,(TransientNetworkError,TimeoutError)):return True
    if isinstance(error,(PermissionError,ValueError,BudgetDenied)):return False
    try:import httpx
    except ImportError:return False
    return isinstance(error,(httpx.NetworkError,httpx.TimeoutException,httpx.RemoteProtocolError))


async def recover(call, reserve, deadline, config, events, *, first_index=None):
    """Bounded consecutive failures, with a fresh client for each attempt."""
    validate(config)
    failures=0
    for attempt in range(1, config['network_consecutive_failure_limit']+1):
        if time.monotonic() >= deadline:
            if not failures:
                events.append({'state':'ROLE_TIMEOUT','reason':'ROLE_DEADLINE','consecutive_failures':0})
                raise TimeoutError('Role deadline reached without a provider connection failure')
            events.append({'state':'RETRY_PENDING','reason':'ROLE_DEADLINE','consecutive_failures':failures})
            raise NetworkRetryPending('Role deadline reached during network recovery')
        try:index=first_index if attempt==1 and first_index is not None else reserve()
        except BudgetDenied:
            events.append({'state':'RETRY_PENDING' if failures else 'BUDGET_EXHAUSTED','reason':'AUTHORIZED_BUDGET','consecutive_failures':failures})
            raise
        tick=time.perf_counter()
        row={'attempt':attempt,'request_index':index,'state':'RUNNING'}
        events.append(row)
        remaining=deadline-time.monotonic()
        limited_by_role=remaining<config['per_request_timeout_seconds']
        try:
            async with asyncio.timeout(min(config['per_request_timeout_seconds'],remaining)):
                result=await call(index,config['per_request_timeout_seconds'])
            row.update(state='RECOVERED' if failures else 'COMPLETED',consecutive_failures=0)
            return result
        except asyncio.CancelledError:
            if not failures:
                row.update(state='ROLE_STOPPED',consecutive_failures=0)
                raise
            row.update(state='RETRY_PENDING',reason='ROLE_STOPPED',consecutive_failures=failures)
            raise NetworkRetryPending('Owning role stopped during a provider request')
        except Exception as error:
            if isinstance(error,TimeoutError) and limited_by_role and time.monotonic()>=deadline and not failures:
                row.update(state='ROLE_TIMEOUT',reason='ROLE_DEADLINE',consecutive_failures=0)
                raise
            if not retryable(error):
                row.update(state='NON_RETRYABLE',error_type=type(error).__name__)
                raise
            failures+=1
            row.update(state='SHOULD_RETRY',error_type=type(error).__name__,consecutive_failures=failures)
            if failures>=5:row['network_warning']=True
            if failures==config['network_consecutive_failure_limit']:
                row['state']='NETWORK_CHECK_REQUIRED'
                raise NetworkCheckRequired(str(failures)+' consecutive provider connection failures') from error
            delay=config['network_retry_backoff_seconds'][attempt-1]
            if time.monotonic()+delay >= deadline:
                events.append({'state':'RETRY_PENDING','reason':'ROLE_DEADLINE','consecutive_failures':failures})
                raise NetworkRetryPending('Insufficient role time to reconnect') from error
            await asyncio.sleep(delay)
        finally:row['elapsed_seconds']=round(time.perf_counter()-tick,6)


class RecoveryBroker(Broker):
    provider_endpoint='https://api.deepseek.com/chat/completions'
    transient_passthrough=False  # Explicitly enabled only by zero-provider SDK controls.
    def __init__(self,key,ledger,experiment,deadline,config):
        self.config=validate(config)
        self.network_events=[]
        self.active=set()
        self.active_lock=threading.Lock()
        self.circuit_open=False
        super().__init__(key,ledger,experiment,deadline)

    def reserve_request(self):
        if self.circuit_open:raise BudgetDenied('NETWORK_CHECK_REQUIRED; no new upstream attempt')
        return super().reserve_request()

    async def exchange(self,body,index,seconds):
        import httpx
        tracker=ChatUsage();first=None;tick=time.perf_counter();chunks=[];size=0;data=[]
        # A new connection/client is the reconnect; no global proxy/firewall change.
        async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=seconds) as client:
            async with client.stream('POST',self.provider_endpoint,json=body,
                    headers={'Authorization':'Bearer '+self.key,'accept':'text/event-stream'}) as response:
                if response.status_code in TRANSIENT_HTTP and not self.transient_passthrough:
                    raise TransientNetworkError('Transient upstream HTTP status '+str(response.status_code))
                if response.status_code!=200:
                    return {'status':response.status_code,'chunks':[]}
                async for line in response.aiter_lines():
                    raw=(line+'\n').encode();size+=len(raw)
                    if size>MAX_RESPONSE_BYTES:raise ValueError('Provider stream exceeded explicit transport buffer')
                    chunks.append(raw)
                    if line.startswith('data:'):data.append(line[5:].lstrip())
                    elif line=='' and data:
                        raw='\n'.join(data);data=[]
                        value=raw if raw=='[DONE]' else json.loads(raw)
                        tracker.event(value)
                        if first is None and isinstance(value,dict) and any(c.get('delta') for c in value.get('choices',[])):
                            first=time.perf_counter()-tick
                if not tracker.complete:
                    raise TransientNetworkError('Provider stream disconnected before completion')
                usage=tracker.verified()  # Requires terminal marker, usage and model.
                self.ledger.settle(index,usage,{'model_id':tracker.model,'http_status':200,
                    'request_id':response.headers.get('request-id') or 'unavailable',
                    'elapsed_seconds':round(time.perf_counter()-tick,6),
                    'first_delta_seconds':'unavailable' if first is None else round(first,6),
                    'protocol':'chat-completions','cache_creation_accounting':'not_applicable_in_protocol',
                    'effective_max_output_tokens':body['max_tokens'],'bill_cash_usd':'unavailable',
                    'stream_delivery_policy':'COMPLETE_BUFFERED','request_timeout_seconds':seconds})
                return {'status':200,'chunks':chunks}

    async def forward(self,handler,body,index):
        loop=asyncio.get_running_loop();task=asyncio.current_task()
        with self.active_lock:self.active.add((loop,task))
        try:
            result=await recover(lambda i,s:self.exchange(body,i,s),
                self.reserve_request,self.deadline,self.config,
                self.network_events,first_index=index)
            # Partial failed streams never reach the Harness, so tool calls cannot
            # execute twice. Usage was settled even if the downstream disconnects.
            handler.send_response(result['status'])
            handler.send_header('Content-Type','text/event-stream')
            handler.send_header('Connection','close');handler.end_headers()
            handler.response_started=True
            for chunk in result['chunks']:handler.wfile.write(chunk)
            handler.wfile.flush()
        except (NetworkCheckRequired,NetworkRetryPending):
            self.circuit_open=True
            raise
        finally:
            with self.active_lock:self.active.discard((loop,task))

    def close(self):
        with self.active_lock:
            for loop,task in self.active:
                loop.call_soon_threadsafe(task.cancel)
        super().close()
        # Prevent a daemon forward thread mutating usage after controller receipt.
        if not self.serial.acquire(timeout=3):raise RuntimeError('Transport did not stop before receipt')
        self.serial.release()


def broker(key,ledger,scope,deadline,config):
    from p6_network_policy import enabled
    return RecoveryBroker(key,ledger,scope,deadline,config) if enabled(config) else Broker(key,ledger,scope,deadline)
