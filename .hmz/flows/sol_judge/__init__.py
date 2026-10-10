"""A fresh independent Sol Verifier session with read-only workspace permission."""

from pydantic import BaseModel
from hmz.flows import Agent,AgentCollection,EnvCollection,FlowContext,FlowParams,LocalEnv,Permission,flow


class CandidateScore(BaseModel):
    id: str
    correctness: int
    robustness: int
    maintainability: int
    evidence: list[str]


class Judgment(BaseModel):
    candidates: list[CandidateScore]
    ranking: list[str]
    rationale: str


class Verifier(Agent):
    _permission=Permission(local='read',user='none',system='none',online='none')


class Agents(AgentCollection):verifier: Verifier
class Envs(EnvCollection):workspace: LocalEnv


@flow(agents=Agents,envs=Envs,params=FlowParams)
async def sol_judge(task: str, *, agents: Agents, envs: Envs, params: FlowParams, ctx: FlowContext):
    verifier=agents['verifier'];session=await verifier.spawn()
    answer=await verifier.run(task,session=session,env=envs['workspace'],output_schema=Judgment)
    return {'judgment':answer.model_dump(mode='json'),'session_id':session.id}
