"""P0 interface probe. Runs with Humanize's fake driver; no product workflow."""

from hmz.flows import Agent, AgentCollection, EnvCollection, FlowContext, FlowParams, LocalEnv, flow


class Agents(AgentCollection):
    probe: Agent


class Envs(EnvCollection):
    workspace: LocalEnv


class Params(FlowParams):
    turns: int = 1


@flow(agents=Agents, envs=Envs, params=Params)
async def p0_probe(task: str, *, agents: Agents, envs: Envs, params: FlowParams,
                   ctx: FlowContext):
    """Verify that a local flow can spawn a session and take one fake turn."""
    session = await agents["probe"].spawn()
    result = None
    for _ in range(params.turns):
        result = await agents["probe"].run(task, session=session, env=envs["workspace"])
    return {"probe_kind": "MOCK_ONLY", "result": result}
