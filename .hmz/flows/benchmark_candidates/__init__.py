"""Schedule full P6 task sessions via Humanize; execution belongs to official Harnesses."""
import asyncio
from hmz.flows import AgentCollection,EnvCollection,FlowContext,FlowParams,flow

class Agents(AgentCollection):pass
class Envs(EnvCollection):pass

@flow(agents=Agents,envs=Envs,params=FlowParams)
async def benchmark_candidates(task:str,*,agents:Agents,envs:Envs,params:FlowParams,ctx:FlowContext):
    from p6_runtime_linux import ACTIVE,launch
    jobs=ACTIVE['candidate_jobs']
    workers=await asyncio.gather(*(asyncio.to_thread(launch,*jobs[cid]) for cid in ('A','B','C')))
    return {'workers':workers,'concurrency':3,'outer_retries':0}
