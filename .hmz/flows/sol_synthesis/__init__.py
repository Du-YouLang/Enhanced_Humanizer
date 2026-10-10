"""A fresh official Codex Reviewer may implement freely or explicitly refuse synthesis."""

from typing import Literal
from pydantic import BaseModel
from hmz.flows import Agent,AgentCollection,EnvCollection,FlowContext,FlowParams,LocalEnv,Permission,flow


class Decision(BaseModel):
    action: Literal['IMPLEMENTED','REFUSED']
    considered_candidates: list[str]
    rationale: str
    known_limitations: list[str]


class Reviewer(Agent):
    _permission=Permission(local='all',user='none',system='none',online='none')


class Agents(AgentCollection):reviewer: Reviewer
class Envs(EnvCollection):workspace: LocalEnv


@flow(agents=Agents,envs=Envs,params=FlowParams)
async def sol_synthesis(task: str, *, agents: Agents, envs: Envs, params: FlowParams, ctx: FlowContext):
    agent=agents['reviewer'];session=await agent.spawn()
    answer=await agent.run(task,session=session,env=envs['workspace'],output_schema=Decision)
    return {'decision':answer.model_dump(mode='json'),'session_id':session.id}
