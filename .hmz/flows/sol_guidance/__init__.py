"""Read-only evidence-grounded mentor; the DS continuation owns code changes."""
from pydantic import BaseModel
from hmz.flows import Agent, AgentCollection, EnvCollection, FlowContext, FlowParams, LocalEnv, Permission, flow


class Observation(BaseModel):
    finding: str
    evidence_kind: str
    reference: str


class Guidance(BaseModel):
    diagnosis: str
    observations: list[Observation]
    hypotheses: list[str]
    next_actions: list[str]
    public_verification: list[str]
    limitations: list[str]


class Mentor(Agent):
    _permission = Permission(local='read', user='none', system='none', online='none')


class Agents(AgentCollection):verifier: Mentor
class Envs(EnvCollection):workspace: LocalEnv


@flow(agents=Agents, envs=Envs, params=FlowParams)
async def sol_guidance(task: str, *, agents: Agents, envs: Envs, params: FlowParams, ctx: FlowContext):
    mentor = agents['verifier']; session = await mentor.spawn()
    answer = await mentor.run(task, session=session, env=envs['workspace'], output_schema=Guidance)
    return {'guidance': answer.model_dump(mode='json'), 'session_id': session.id}
