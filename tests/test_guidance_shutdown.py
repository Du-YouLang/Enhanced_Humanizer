import sys,unittest,sqlite3,tempfile,json
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p6_guidance_shutdown import scope,MENTOR,SESSION_ID,remaining_seconds,usage_segments,allow_partial,allow_science
from p6_guidance_session_resume import attach,relocate

class ShutdownTests(unittest.TestCase):
    def test_interruption_debits_role_and_rejects_exhausted_time(self):
        self.assertEqual(remaining_seconds(100,142.1),(43,857))
        for a,b in [(100,99),(0,901),(float('nan'),100)]:
            with self.assertRaises(ValueError):remaining_seconds(a,b)
    def test_completed_and_other_roles_are_not_replayable(self):
        self.assertTrue(allow_partial({'scope':scope('code-tests-ds')}))
        self.assertFalse(allow_partial({'scope':scope('initial-ds')}))
        self.assertFalse(allow_partial({'scope':scope(MENTOR)}))
        self.assertTrue(allow_science('GUIDANCE/new/SCI-EGL/initial-ds','new'))
        self.assertFalse(allow_science('GUIDANCE/new/SWEL-sympy__sympy-11870/initial-ds','new'))
    def test_session_usage_delta_keeps_old_consumption_once(self):
        before=dict(input_tokens=100,cached_input_tokens=40,output_tokens=10,reasoning_output_tokens=2,total_tokens=110)
        after=dict(input_tokens=150,cached_input_tokens=60,output_tokens=15,reasoning_output_tokens=3,total_tokens=165)
        old,delta=usage_segments(before,after)
        self.assertEqual(old['input_tokens']+delta['input_tokens'],150)
        self.assertEqual(delta['cached_input_tokens'],20)
        with self.assertRaises(ValueError):usage_segments(after,before)
    def test_same_scope_cannot_repeat_and_linked_continuation_keeps_both_reservations(self):
        from p6_main_budget import MainLedger,BudgetDenied
        config=json.loads((ROOT/'configs/budget-p6-main-v10-guidance-approved.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.json';ledger=MainLedger(path,config)
            old=scope(MENTOR);continued=old.replace('guidance-20261016T090045Z','guidance-20261016T235959Z')
            ledger.reserve_codex_turn(old,'gpt-6.1-sol');before=json.loads(path.read_text())
            with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn(old,'gpt-6.1-sol')
            ledger.reserve_codex_turn(continued,'gpt-6.1-sol');after=json.loads(path.read_text())
            self.assertEqual(after['codex_turns'][:1],before['codex_turns'])
            self.assertEqual(len(after['codex_turns']),2)
            self.assertEqual(after['cash_bound_nano'],before['cash_bound_nano'])
    def test_attach_only_adopts_the_verified_original_unopened_thread(self):
        class Handle:
            def __init__(self):
                self.inner=SimpleNamespace(agent=SimpleNamespace(),coganchor=self)
                self.id=None
            def _adopt(self,value):self.id=value
        handle=Handle();attach(handle,SESSION_ID,ROOT/'keeps')
        self.assertEqual(handle.id,SESSION_ID)
        self.assertEqual(handle.inner.agent.keeps,ROOT/'keeps')
        with self.assertRaises(ValueError):attach(handle,SESSION_ID,ROOT/'keeps')
        with self.assertRaises(ValueError):attach(Handle(),'other',ROOT/'keeps')
    def test_only_one_thread_path_index_changes_in_a_copied_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);trace=root/'sessions/2026/10/16'/('rollout-'+SESSION_ID+'.jsonl')
            trace.parent.mkdir(parents=True);trace.write_text('unchanged history')
            with closing(sqlite3.connect(root/'state_5.sqlite')) as db, db:
                db.execute('CREATE TABLE threads(id TEXT,rollout_path TEXT)')
                db.execute('INSERT INTO threads VALUES (?,?)',(SESSION_ID,'/old/rollout'))
            result=relocate(root,SESSION_ID)
            self.assertEqual(result['history_edits'],0)
            self.assertEqual(trace.read_text(),'unchanged history')
            with closing(sqlite3.connect(root/'state_5.sqlite')) as db, db:
                self.assertEqual(db.execute('SELECT rollout_path FROM threads').fetchone()[0],str(trace))
                db.execute('INSERT INTO threads VALUES (?,?)',('another','/another/rollout'))
            with self.assertRaises(ValueError):relocate(root,SESSION_ID)

if __name__=='__main__':unittest.main()
