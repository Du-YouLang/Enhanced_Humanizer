"""Single-agent continuation on the official native session; no custom tools."""
import json
import os
from pathlib import Path,PurePosixPath
import time
from p6_refresh_protocol import model_for_job,expected_model


def bounds(job):
    if job['scope'].split('/')[-2:]!=['SingleAgent-MatchedBudget','matched-1']:
        raise ValueError('Only the first scope of the matched control may own a six-slot session')
    model_for_job(job)
    seconds=job['refresh_per_turn_seconds']
    if type(seconds) is not int or seconds not in (900,1200):raise ValueError('Frozen public/scientific turn time required')
    if job['role_seconds']!=6*seconds or job.get('refresh_slots')!=6:raise ValueError('Exactly six bounded slots required')
    slot=Path(job['root'])/'controller-slot.json'
    if job.get('refresh_slot_file')!=str(slot):raise ValueError('Trusted slot state path differs')
    return slot,seconds


def slot_scope(job,index):
    if type(index) is not int or not 1<=index<=6:raise ValueError('Slot outside authorized six turns')
    return job['scope'].rsplit('/',1)[0]+'/matched-'+str(index)


def write_slot(job,index):
    path,_=bounds(job)
    value={'index':index,'scope':slot_scope(job,index)}
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(value));os.replace(temp,path)
    return value


class MatchedSlotLedger:
    """Broker resolves each trusted native turn to its own original 1000-call cap.

    State is outside the agent work/home and explicitly denied by the actual OS
    probe. The candidate cannot advance its budget by writing a tool argument.
    """
    def __init__(self,ledger,job):self.ledger,self.job=ledger,job;bounds(job)
    @property
    def max_output(self):return self.ledger.max_output
    def reserve_request(self,_):
        path,_=bounds(self.job);v=json.loads(path.read_bytes())
        scope=slot_scope(self.job,v['index'])
        if v.get('scope')!=scope or expected_model(scope)!='deepseek-flash':raise ValueError('Invalid trusted slot state')
        return self.ledger.reserve_request(scope,scope_requests=1000,scope_cash_nano=None)
    def settle(self,*args):return self.ledger.settle(*args)


async def run_matched(driver,job):
    from hmz.runtime.flowing.spi import Placement,TurnRequest,Limits,HookTable
    from hmz.flows import EnvBackendKind
    from p6_worker_linux import Sink
    _,seconds=bounds(job)
    driver.max_turns=6
    session=await driver.open(Placement(EnvBackendKind.LOCAL,'',PurePosixPath(job['work'])),
                              permission=driver.permission,skills=(),hooks=HookTable())
    responses=[];receipts=[]
    try:
        for index in range(1,7):
            state=write_slot(job,index);driver.experiment=state['scope']
            prompt=job['prompt'] if index==1 else (
                'Continue your own previous solution in the same session and workspace. '
                'Use this additional bounded work slot to inspect correctness, edge cases and public tests. '
                'No other agent advice or hidden acceptance is available. Preserve immutable tests and dependencies; '
                'commit cleanly. Report remaining issues and validation evidence.')
            tick=time.perf_counter()
            answer=await session.turn(TurnRequest(prompt,limits=Limits(deadline=time.monotonic()+seconds,graceful=False)),Sink())
            responses.append(answer);receipts.append({'index':index,'scope':state['scope'],'elapsed_seconds':time.perf_counter()-tick,'same_official_session_id':session.inner.id})
        return responses[-1],receipts
    finally:
        await session.close();await driver.inner.close()
