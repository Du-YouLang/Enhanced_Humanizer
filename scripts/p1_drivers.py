"""Meter official Humanize drivers without implementing model or tool execution."""

from dataclasses import replace
import os
import time
from urllib.parse import urlparse

from hmz.flows import Permission
from hmz.runtime.flowing.harnesses import open_agent
from hmz.runtime.flowing.specs import parse_agents


STRICT=Permission(local='all',user='none',system='none',online='none')


class PlannedTurnLimit(RuntimeError):
    pass


class MeteredDriver:
    def __init__(self,spec,ledger,experiment,turns,max_turns=2,turn_seconds=115,permission=STRICT,fence_auditor=None,fence_transform=None):
        self.inner=open_agent(parse_agents([spec])[0])
        if str(self.inner.harness)=='dsh':
            host=urlparse(os.environ['DEEPSEEK_BASE_URL']).netloc
            base_kind=self.inner._kind
            class BrokerOnlyAgent(base_kind):
                @property
                def backend(self):return 'dsh'

                def fenced(self):
                    fence=super().fenced()
                    if fence is None or fence.online:raise RuntimeError('DSH transport requires external network isolation')
                    narrowed=replace(fence,hosts=(host,))
                    if fence_transform is not None:narrowed=fence_transform(narrowed)
                    if fence_auditor is not None:fence_auditor(narrowed)
                    return narrowed
            self.inner._kind=BrokerOnlyAgent
        elif fence_transform is not None:
            base_kind=self.inner._kind
            class NarrowedAgent(base_kind):
                @property
                def backend(self):return 'codex'
                def fenced(self):
                    fence=super().fenced()
                    if fence is None:raise RuntimeError('Judge isolation requires an external fence')
                    return fence_transform(fence)
            self.inner._kind=NarrowedAgent
        self.ledger=ledger
        self.experiment=experiment
        self.turns=turns
        self.max_turns=max_turns
        self.turn_seconds=min(turn_seconds,600)
        self.permission=permission

    def __getattr__(self,key):return getattr(self.inner,key)

    async def open(self,*args,**kwargs):
        kwargs['permission']=self.permission
        return MeteredSession(await self.inner.open(*args,**kwargs),self)


class MeteredSession:
    def __init__(self,inner,driver):self.inner,self.driver=inner,driver
    def __getattr__(self,key):return getattr(self.inner,key)

    async def turn(self,request,sink):
        driver=self.driver
        if len(driver.turns)>=driver.max_turns:raise PlannedTurnLimit('Controlled upstream Flow turn cap')
        if str(driver.harness)=='codex':driver.ledger.reserve_codex_turn(driver.experiment,driver.model)
        deadline=min(request.limits.deadline or float('inf'),time.monotonic()+driver.turn_seconds)
        request=replace(request,limits=replace(request.limits,deadline=deadline,graceful=False))
        tick=time.perf_counter()
        row={'role':driver.inner._spec.role,'model_requested':driver.model,'harness':str(driver.harness),
             'prompt_sha256':__import__('hashlib').sha256(request.prompt.encode()).hexdigest(),'status':'RUNNING'}
        driver.turns.append(row)
        try:
            result=await self.inner.turn(request,sink)
            row['status']='COMPLETED'
            return result
        except BaseException as error:
            row.update(status='FAILED',error_type=type(error).__name__)
            raise
        finally:
            row.update(elapsed_seconds=round(time.perf_counter()-tick,6),session_id=self.inner.id,
                       usage=self.inner.usage.model_dump(mode='json'))
