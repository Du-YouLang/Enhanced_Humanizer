"""MOCK/synthetic-only controls: never replay slot1 or reuse its billing scope."""
import sys,tempfile,sqlite3,json,copy,unittest
from pathlib import Path
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_refresh_matched_resume import slots,validate,relocate,SESSION,ORIGINAL,bind_workspace
from p6_main_budget import MainLedger
from p1_budget import BudgetDenied

def job():
 return {'backend':'codex','role':'builder','root':'/resume','scope':ORIGINAL.replace('refresh-20261126T060538Z','refresh-20261127T120000Z'),'role_seconds':5985,'refresh_per_turn_seconds':1200,'refresh_slots':6,'refresh_matched_resume':{'session_id':SESSION,'original_scope':ORIGINAL,'keeps':'/resume/keeps','completed_slots':1,'resume_slot':2,'prior_seconds':15}}
class MatchedResumeTests(unittest.TestCase):
 def test_only_slots2_to6_run_with_remaining_partial_allowance(self):
  j=job();rows=slots(j);self.assertEqual([r[0]for r in rows],[2,3,4,5,6]);self.assertEqual([r[1]for r in rows],[1185,1200,1200,1200,1200]);self.assertIn('refresh-20261127T120000Z',rows[0][2]);self.assertEqual(rows[1][2],ORIGINAL.rsplit('/',1)[0]+'/matched-3')
 def test_wrong_role_scope_session_or_reset_allowance_fails(self):
  for field,value in [('role','verifier'),('backend','dsh'),('role_seconds',6000),('scope',ORIGINAL)]:
   j=job();j[field]=value
   with self.assertRaises(ValueError):validate(j)
  for field,value in [('completed_slots',0),('resume_slot',1),('session_id','other')]:
   j=job();j['refresh_matched_resume'][field]=value
   with self.assertRaises(ValueError):validate(j)
 def test_original_thread_history_is_unchanged_and_only_copy_pointer_moves(self):
  with tempfile.TemporaryDirectory()as tmp:
   p=Path(tmp);trace=p/'sessions/2026/11/27'/('rollout-'+SESSION+'.jsonl');trace.parent.mkdir(parents=True);trace.write_text('MOCK immutable history')
   with closing(sqlite3.connect(p/'state_5.sqlite'))as db,db:db.execute('CREATE TABLE threads(id TEXT,rollout_path TEXT)');db.execute('INSERT INTO threads VALUES (?,?)',(SESSION,'/old/path'))
   self.assertEqual(relocate(p)['history_edits'],0);self.assertEqual(trace.read_text(),'MOCK immutable history')
   with closing(sqlite3.connect(p/'state_5.sqlite'))as db:self.assertEqual(db.execute('SELECT rollout_path FROM threads').fetchone()[0],str(trace))
 def test_official_resume_explicitly_rebinds_cwd_and_does_not_reopen_held_thread(self):
  from types import SimpleNamespace
  class Server:
   def __init__(self):self.bound=False;self.calls=[];self.cwd='/resume/code';self.given=0
   def give(self):self.given+=1
   def holds(self,*a):return self.bound
   def holding(self,*a):self.bound=True
   def call(self,method,params):self.calls.append((method,params));return {'thread':{'id':SESSION,'cwd':self.cwd}}
  server=Server();cog=SimpleNamespace(_agent=SimpleNamespace(_taken=lambda held=None:server),_permitted=lambda _: {'sandbox':'danger-full-access'},_thread=lambda _:SESSION)
  j=job();j['work']='/resume/code';result=bind_workspace(cog,j,force=True);self.assertEqual(result['workspace'],j['work']);self.assertEqual(server.calls[0][1]['cwd'],j['work'])
  bind_workspace(cog,j);self.assertEqual(len(server.calls),1);self.assertIs(cog._on,server);self.assertEqual(server.given,2)
  server.bound=False;server.cwd='/original/code'
  with self.assertRaisesRegex(ValueError,'workspace'):bind_workspace(cog,j)

 def test_resume_and_subsequent_turn_share_one_server_checkout(self):
  from types import SimpleNamespace
  created=[]
  class Server:
   def __init__(self):self.bound=False;self.busy=0
   def give(self):self.busy-=1
   def holds(self,*a):return self.bound
   def holding(self,*a):self.bound=True
   def call(self,*a):return {'thread':{'id':SESSION,'cwd':'/resume/code'}}
  def taken(held=None):
   if held is None:
    server=next((s for s in created if s.busy==0),None)
    if server is None:server=Server();created.append(server)
   else:server=held
   server.busy+=1;return server
  cog=SimpleNamespace(_agent=SimpleNamespace(_taken=taken),_permitted=lambda _: {},_thread=lambda _:SESSION);j=job();j['work']='/resume/code'
  bind_workspace(cog,j,force=True);bind_workspace(cog,j);server=taken(cog._on);server.give()
  self.assertEqual(len(created),1);self.assertEqual(created[0].busy,0)

 def test_actual_ledger_duplicate_denial_and_new_linked_scope_preserve_old(self):
  config=json.loads((Path(__file__).resolve().parents[1]/'configs/budget-p6-model-refresh-approved.json').read_bytes())
  with tempfile.TemporaryDirectory()as tmp:
   ledger=MainLedger(Path(tmp)/'ledger.json',config,fixture=True);old=ORIGINAL.rsplit('/',1)[0]+'/matched-2';new=slots(job())[0][2]
   ledger.reserve_codex_turn(old,'gpt-6.1-sol');before=ledger.path.read_bytes()
   with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn(old,'gpt-6.1-sol')
   self.assertEqual(ledger.path.read_bytes(),before);ledger.reserve_codex_turn(new,'gpt-6.1-sol');v=json.loads(ledger.path.read_bytes());self.assertEqual([r['experiment']for r in v['codex_turns']],[old,new])
if __name__=='__main__':unittest.main()
