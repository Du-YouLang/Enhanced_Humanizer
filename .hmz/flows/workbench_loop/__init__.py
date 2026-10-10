"""Native resumable Humanize Flow. All agent tools remain in official Harnesses."""
import asyncio
from pathlib import Path
from hmz.flows import AgentCollection,EnvCollection,FlowContext,FlowParams,flow
from p2_candidates import exclusive_json
from p3_contracts import checkpoint,validate_checkpoint,read_json

class Agents(AgentCollection):pass
class Envs(EnvCollection):pass
class Params(FlowParams):
    run_root:str
    contract_hash:str
    pause_after:str=''

@flow(agents=Agents,envs=Envs,params=Params,resumable=True)
async def workbench_loop(task:str,*,agents:Agents,envs:Envs,params:Params,ctx:FlowContext):
    from p5_runtime_linux import STAGES,stage,load
    root=Path(params.run_root);state=ctx.state
    assert state is not None
    done=state['stages'] if 'stages' in state else [];next_step=state['next_step'] if 'next_step' in state else 0
    if done:
        saved=validate_checkpoint(read_json(root/'control'/('checkpoint-'+str(next_step)+'.json')),params.contract_hash)
        if saved['stages']!=done:raise ValueError('Humanize and durable checkpoint disagree')
        for item in done:
            if load(root,item['name'])['record_sha256']!=item['result_sha256']:raise ValueError('Completed evidence changed')
    for index,name in enumerate(STAGES):
        if index<next_step:continue
        result=await asyncio.to_thread(stage,root,name)
        done=[*done,{'name':name,'result_sha256':result['record_sha256']}]
        state['stages']=done;state['next_step']=index+1
        value=checkpoint(index+1,done,params.contract_hash);exclusive_json(root/'control'/('checkpoint-'+str(index+1)+'.json'),value)
        if result.get('status') in ('INFRA_FAIL','TIMEOUT','BUDGET_EXHAUSTED','CANCELLED'):
            raise RuntimeError('Stage failed closed; preserve evidence')
        if name==params.pause_after or (root/'control/pause.requested').exists():
            exclusive_json(root/'control'/('pause-'+str(index+1)+'.json'),value)
            await asyncio.Event().wait()
    return {'stages':done,'next_step':len(STAGES),'resumed':ctx.resumed}
