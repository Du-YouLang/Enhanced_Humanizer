"""Exact read-only official judge reattachment after a human shutdown."""
from pathlib import Path
from contextlib import closing
import sqlite3,time

SESSION='01a2172f-21f0-7c13-a828-56a2258f0385'
ORIGINAL='REFRESH/refresh-20261126T060538Z/BIP-black-5/GPT61-Sol/Enhanced/judge-input'

def validate(job):
    d=job['refresh_judge_resume']
    from p6_refresh_protocol import expected_model
    if (job['role']!='verifier' or job['backend']!='codex' or d['session_id']!=SESSION
        or d['original_scope']!=ORIGINAL or job['scope']==ORIGINAL
        or job['scope'].split('/')[2:]!=ORIGINAL.split('/')[2:]
        or expected_model(job['scope'])!='gpt-6.1-sol'):
        raise ValueError('Only the exact interrupted read-only judge can resume')
    if job['role_seconds']!=900-d['prior_seconds'] or not 0<d['prior_seconds']<900:
        raise ValueError('Original consumed role time must remain debited')
    if not Path(d['keeps']).resolve().is_relative_to(Path(job['root']).resolve()):
        raise ValueError('Isolated session snapshot required')
    return d

def relocate(store):
    store=Path(store);paths=list(store.glob('sessions/*/*/*/rollout-*.jsonl'))
    if len(paths)!=1 or SESSION not in paths[0].name:raise ValueError('Only original rollout allowed')
    with closing(sqlite3.connect(store/'state_5.sqlite')) as db:
        rows=db.execute('SELECT id,rollout_path FROM threads').fetchall()
        if len(rows)!=1 or rows[0][0]!=SESSION:raise ValueError('One original thread required')
        with db:db.execute('UPDATE threads SET rollout_path=? WHERE id=?',(str(paths[0]),SESSION))
    return {'session_id':SESSION,'old_rollout_path':rows[0][1],'new_rollout_path':str(paths[0]),'history_edits':0}

async def resume(driver,job,sink,*,probe=False):
    from hmz.runtime.flowing.spi import Placement,HookTable,TurnRequest,Limits
    from hmz.flows import EnvBackendKind
    from pathlib import PurePosixPath
    from flows.sol_judge import Judgment
    d=validate(job)
    session=await driver.open(Placement(EnvBackendKind.LOCAL,'',PurePosixPath(job['work'])),permission=driver.permission,skills=(),hooks=HookTable())
    try:
        if session.id is not None:raise ValueError('Unopened official handle required')
        session.inner.agent.keeps=Path(d['keeps'])
        session.inner.coganchor._adopt(SESSION)
        if session.id!=SESSION:raise ValueError('Original session adoption failed')
        if probe:
            cog=session.inner.coganchor
            if cog._thread(cog._agent._taken())!=SESSION:raise ValueError('Official thread/resume failed')
            return {'status':'PASS_OFFICIAL_THREAD_RESUME_ZERO_INFERENCE','session_id':SESSION,'model_calls':0}
        answer=await session.turn(TurnRequest('Continue the SAME interrupted read-only scoring task after user shutdown. Retain its context and input evidence. Finish the original judgment JSON using integer scores0 through4. Do not start fresh analysis, edit files, access hidden tests, or change constraints.',output_schema=Judgment,limits=Limits(deadline=time.monotonic()+job['role_seconds'],graceful=False)),sink)
        return {'judgment':answer.model_dump(mode='json'),'session_id':session.id}
    finally:
        await session.close();await driver.inner.close()
