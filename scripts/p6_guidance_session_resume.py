"""Reattach the official Humanize Codex driver; never implement model tools."""
import time
import sqlite3
from contextlib import closing
from pathlib import Path
from p6_guidance_shutdown import SESSION_ID,scope,MENTOR

def relocate(store,session_id):
    """Repair only the path index of one isolated copied Codex thread."""
    store=Path(store);traces=list(store.glob('sessions/*/*/*/rollout-*.jsonl'))
    if session_id!=SESSION_ID or len(traces)!=1 or session_id not in traces[0].name:
        raise ValueError('One exact copied official rollout required')
    with closing(sqlite3.connect(store/'state_5.sqlite')) as database:
        with database:
            rows=database.execute('SELECT id,rollout_path FROM threads').fetchall()
            if len(rows)!=1 or rows[0][0]!=session_id:raise ValueError('Copied store must contain only the original mentor thread')
            database.execute('UPDATE threads SET rollout_path=? WHERE id=? AND rollout_path=?',
                (str(traces[0]),session_id,rows[0][1]))
    return {'session_id':session_id,'old_rollout_path':rows[0][1],'copied_rollout_path':str(traces[0]),'history_edits':0}

def attach(handle,session_id,keeps):
    if session_id!=SESSION_ID or handle.id is not None:raise ValueError('Only the interrupted unopened handle can attach')
    handle.inner.agent.keeps=Path(keeps)
    # The installed upstream has no public attach-by-id API. Its existing
    # adoption method feeds its own thread/resume transport, with all normal
    # model, permission, tool and schema handling retained.
    handle.inner.coganchor._adopt(session_id)
    if handle.id!=session_id:raise ValueError('Official handle did not retain the original session')

async def resume(driver,job,sink,*,probe=False):
    from hmz.runtime.flowing.spi import Placement,HookTable,TurnRequest,Limits
    from hmz.flows import EnvBackendKind
    from pathlib import PurePosixPath
    from flows.sol_guidance import Guidance
    details=job['guidance_session_resume']
    if job['role']!='verifier' or job['backend']!='codex' or job['scope']!=scope(MENTOR):
        raise ValueError('Exact read-only interrupted mentor scope required')
    if not Path(details['keeps']).resolve().is_relative_to(Path(job['root']).resolve()):
        raise ValueError('Only a separate local session snapshot may be resumed')
    session=await driver.open(Placement(EnvBackendKind.LOCAL,'',PurePosixPath(job['work'])),
        permission=driver.permission,skills=(),hooks=HookTable())
    try:
        attach(session,details['session_id'],details['keeps'])
        if probe:
            # thread/resume reads the saved thread; no turn/start or inference.
            cog=session.inner.coganchor;server=cog._agent._taken()
            thread=cog._thread(server)
            if thread!=SESSION_ID:raise ValueError('Original thread was not found')
            return {'status':'PASS_OFFICIAL_THREAD_RESUME_ZERO_INFERENCE','session_id':thread,'model_calls':0}
        answer=await session.turn(TurnRequest(
            'Continue this same read-only mentoring task after the user shut down the computer. '
            'Retain the previous context and observations. Finish the originally requested structured guidance; '
            'do not start a fresh analysis, modify code, access hidden tests, or change the original constraints.',
            output_schema=Guidance,limits=Limits(deadline=time.monotonic()+job['role_seconds'],graceful=False)),sink)
        return {'guidance':answer.model_dump(mode='json'),'session_id':session.id}
    finally:
        await session.close();await driver.inner.close()
