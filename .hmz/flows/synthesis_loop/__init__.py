"""Resumable Humanize orchestration, delegating all model/tool work to existing Harnesses."""

import asyncio
from pathlib import Path
from hmz.flows import AgentCollection,EnvCollection,FlowContext,FlowParams,flow
from p2_candidates import exclusive_json
from p3_contracts import checkpoint,validate_checkpoint,read_json


class Agents(AgentCollection):pass
class Envs(EnvCollection):pass
class Params(FlowParams):
    run_root: str
    contract_hash: str
    pause_after: str=''


@flow(agents=Agents,envs=Envs,params=Params,resumable=True)
async def synthesis_loop(task: str, *, agents: Agents, envs: Envs, params: Params, ctx: FlowContext):
    from p3_runtime_linux import stage,STAGES
    state=ctx.state
    assert state is not None
    root=Path(params.run_root)
    done=state['stages'] if 'stages' in state else []
    next_step=state['next_step'] if 'next_step' in state else 0
    if done:
        saved=validate_checkpoint(read_json(root/'control'/('checkpoint-'+str(next_step)+'.json')),params.contract_hash)
        if saved['stages']!=done:raise ValueError('Humanize state and checkpoint disagree')
        from p3_runtime_linux import load_stage
        for row in done:
            if load_stage(root,row['name'])['record_sha256']!=row['result_sha256']:raise ValueError('Completed stage changed')
    for index,name in enumerate(STAGES):
        if index<next_step:continue
        result=await asyncio.to_thread(stage,root,name)
        done=[*done,{'name':name,'result_sha256':result['record_sha256']}]
        state['stages']=done;state['next_step']=index+1
        value=checkpoint(index+1,done,params.contract_hash)
        exclusive_json(root/'control'/('checkpoint-'+str(index+1)+'.json'),value)
        if result.get('status') in ('INFRA_FAIL','TIMEOUT','BUDGET_EXHAUSTED'):
            raise RuntimeError('Role failed closed; preserved stage must not trigger more model calls')
        if name==params.pause_after or (root/'control/pause.requested').exists():
            exclusive_json(root/'control'/('pause-'+str(index+1)+'.json'),value)
            await asyncio.Event().wait()  # Run.stop/resume preserves completed stages, as in P1.
    return {'stages':done,'next_step':len(STAGES),'resumed':ctx.resumed}
