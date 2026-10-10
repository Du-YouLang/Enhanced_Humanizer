"""One real coding turn through the upstream Humanize and Codex drivers."""

from hmz.flows import Agent, AgentCollection, EnvCollection, FlowContext, FlowParams, LocalEnv, Permission, flow


class Builder(Agent):
    _permission = Permission(local='all', user='none', system='none', online='none')


class Agents(AgentCollection):
    builder: Builder


class Envs(EnvCollection):
    workspace: LocalEnv


@flow(agents=Agents, envs=Envs, params=FlowParams)
async def p0_coding_demo(task: str, *, agents: Agents, envs: Envs, params: FlowParams, ctx: FlowContext):
    """Edit, test and commit a synthetic task in one genuine model turn."""
    builder = agents['builder']
    session = await builder.spawn()
    said = await builder.run(task, session=session, env=envs['workspace'])
    return {'model_requested':builder.model, 'harness':str(builder.harness),
            'session_usage':session.usage.model_dump(mode='json'), 'answer':said}
