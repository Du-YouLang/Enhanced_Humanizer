"""Bounded direct Builders, using only the upstream Humanize Flow API."""

import asyncio
import json
from pathlib import Path

from hmz.flows import Agent, AgentCollection, EnvCollection, FlowContext, FlowParams, LocalEnv, Permission, ShellEnvMixin, flow
from p1_acceptance import DESIGN_CHECK, verification_command


class Builder(Agent):
    _permission=Permission(local='all',user='none',system='none',online='none')


class Agents(AgentCollection):
    ds_builder: Builder
    sol_builder: Builder


class Workspace(LocalEnv,ShellEnvMixin):
    pass


class Envs(EnvCollection):
    workspace: Workspace


class Params(FlowParams):
    base_commit: str
    pause_at_boundary: bool=True
    pause_signal: str
    workspace_path: str
    verification_scratch: str


SOL_TASK='Redesign weighted_stats.py around a streaming WeightedMean accumulator with add(value, weight), merge(other), and result(). weighted_mean(pairs) must use that accumulator. Preserve valid weighted-mean results, reject negative weights and zero total weight. Add test_accumulator.py covering incremental add and merge, run python -m unittest -v, then make a new Git commit. You are a direct Builder: implement a new design, not only review. Do not edit test_weighted_stats.py or install dependencies or spawn subagents.'


@flow(agents=Agents,envs=Envs,params=Params,resumable=True)
async def basic_relay(task: str, *, agents: Agents, envs: Envs, params: Params, ctx: FlowContext):
    """DS implements, pause at an accepted commit, then a fresh Sol redesigns."""
    state=ctx.state
    assert state is not None
    workspace=envs['workspace']
    next_step=state['next_step'] if 'next_step' in state else 0
    handoffs=state['handoffs'] if 'handoffs' in state else []
    for index,role in enumerate(('ds_builder','sol_builder')):
        if index<next_step:continue
        builder=agents[role]
        session=await builder.spawn()
        prompt=task if index==0 else SOL_TASK+'\n\nProgram-generated handoff (claims are not hidden test truth):\n'+json.dumps(handoffs[-1],sort_keys=True)
        await builder.run(prompt,session=session,env=workspace)
        code,out,err=await workspace.exec(verification_command(params.workspace_path,['python','-m','unittest','-v'],params.verification_scratch),timeout=15)
        if code:raise RuntimeError('Builder independent public tests failed: '+err[-1000:])
        _,head,_=await workspace.exec(['git','rev-parse','HEAD'],timeout=5)
        _,dirty,_=await workspace.exec(['git','status','--porcelain'],timeout=5)
        previous=handoffs[-1]['head_commit'] if handoffs else params.base_commit
        _,changed,_=await workspace.exec(['git','diff','--name-only',previous,head.strip()],timeout=5)
        if dirty.strip() or head.strip()==previous or not changed.strip():raise RuntimeError('Builder needs a clean real new commit')
        if 'test_weighted_stats.py' in changed.splitlines():raise RuntimeError('Frozen acceptance test was modified')
        if index==1:
            design_code,_,design_error=await workspace.exec(verification_command(params.workspace_path,['python','-c',DESIGN_CHECK],params.verification_scratch),timeout=15)
            if design_code:raise RuntimeError('Independent redesign check failed: '+design_error[-1000:])
        package={'schema_version':1,'role':role,'model_requested':builder.model,'base_commit':previous,
                 'head_commit':head.strip(),'test_command':'python -m unittest -v','test_exit_code':code,
                 'changed_files':changed.splitlines(),'known_failures':[],
                 'context_transfer':'program evidence and repository only; no prior chat transcript'}
        handoffs=[*handoffs,package]
        state['handoffs']=handoffs
        state['next_step']=index+1
        if index==0 and params.pause_at_boundary:
            Path(params.pause_signal).write_text(json.dumps({'next_step':1,'head_commit':head.strip()}))
            await asyncio.Event().wait()  # external Run.stop, then native Humanize --resume semantics
    return {'handoffs':handoffs,'resumed':ctx.resumed,'next_step':state['next_step']}
