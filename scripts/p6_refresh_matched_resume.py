"""Resume only the original second matched turn; retain first completed turn."""
from pathlib import Path,PurePosixPath
from contextlib import closing
import sqlite3,time
SESSION='01a21c6d-abcf-7570-b992-1bbfcf3929e1'
ORIGINAL='REFRESH/refresh-20261126T060538Z/SCI-GRANGER-GPU/GPT61-Sol/SingleAgent-MatchedBudget/matched-1'

def validate(job):
 d=job['refresh_matched_resume']
 if (job['backend']!='codex' or job['role']!='builder' or d['session_id']!=SESSION or d['original_scope']!=ORIGINAL or job['scope']==ORIGINAL or job['scope'].split('/')[2:]!=ORIGINAL.split('/')[2:]):raise ValueError('Exact interrupted matched session required')
 if d['completed_slots']!=1 or d['resume_slot']!=2 or job['refresh_per_turn_seconds']!=1200 or job['refresh_slots']!=6:raise ValueError('One completed slot and second interrupted slot required')
 if not 0<d['prior_seconds']<1200 or job['role_seconds']!=5*1200-d['prior_seconds']:raise ValueError('Consumed allowance must remain debited')
 if not Path(d['keeps']).resolve().is_relative_to(Path(job['root']).resolve()):raise ValueError('Independent session snapshot required')
 return d

def relocate(store):
 store=Path(store);paths=list(store.glob('sessions/*/*/*/rollout-*.jsonl'))
 if len(paths)!=1 or SESSION not in paths[0].name:raise ValueError('Original rollout required')
 with closing(sqlite3.connect(store/'state_5.sqlite'))as db:
  rows=db.execute('SELECT id,rollout_path FROM threads').fetchall()
  if len(rows)!=1 or rows[0][0]!=SESSION:raise ValueError('One original thread required')
  with db:db.execute('UPDATE threads SET rollout_path=? WHERE id=?',(str(paths[0]),SESSION))
 return {'session_id':SESSION,'history_edits':0}

def slots(job):
 d=validate(job)
 return [(index,(1200-d['prior_seconds'])if index==2 else 1200,(job['scope']if index==2 else ORIGINAL).rsplit('/',1)[0]+'/matched-'+str(index)) for index in range(2,7)]

async def resume(driver,job,sink,*,probe=False):
 from hmz.runtime.flowing.spi import Placement,HookTable,TurnRequest,Limits
 from hmz.flows import EnvBackendKind
 d=validate(job);driver.max_turns=5
 session=await driver.open(Placement(EnvBackendKind.LOCAL,'',PurePosixPath(job['work'])),permission=driver.permission,skills=(),hooks=HookTable())
 try:
  if session.id is not None:raise ValueError('Unopened original thread handle required')
  session.inner.agent.keeps=Path(d['keeps']);session.inner.coganchor._adopt(SESSION)
  if session.id!=SESSION:raise ValueError('Thread adoption failed')
  if probe:
   cog=session.inner.coganchor
   if cog._thread(cog._agent._taken())!=SESSION:raise ValueError('Official thread/resume failed')
   return {'status':'PASS_MATCHED_ORIGINAL_THREAD_ZERO_INFERENCE','session_id':SESSION,'model_calls':0}
  receipts=[{'index':1,'scope':ORIGINAL,'elapsed_seconds':'unavailable_original_driver_interval','same_official_session_id':SESSION,'retained_completed_turn':True,'official_event_interval_seconds':d['completed_event_seconds']}]
  answer=None
  for index,seconds,billing in slots(job):
   driver.experiment=billing
   slot=Path(job['root'])/'controller-slot.json';slot.write_text(__import__('json').dumps({'index':index,'scope':billing,'original_slot_scope':ORIGINAL.rsplit('/',1)[0]+'/matched-'+str(index)}))
   prompt=('Continue the SAME interrupted second work slot in the same session and retained workspace after human shutdown. Slot1 is already complete; do not repeat it. Finish the interrupted inspection, edits and public verification, preserving original task and immutable tests. '+job['prompt'])if index==2 else ('Continue your own previous solution in the same session and workspace. Use this additional bounded work slot to inspect correctness, edge cases and public tests. No other agent advice or hidden acceptance is available. Preserve immutable tests and dependencies; commit cleanly. Report remaining issues and validation evidence.')
   tick=time.perf_counter();answer=await session.turn(TurnRequest(prompt,limits=Limits(deadline=time.monotonic()+seconds,graceful=False)),sink)
   receipts.append({'index':index,'scope':billing,'original_slot_index':index,'elapsed_seconds':time.perf_counter()-tick,'same_official_session_id':SESSION,'prior_seconds_debited':d['prior_seconds']if index==2 else 0})
  return answer,receipts
 finally:await session.close();await driver.inner.close()
