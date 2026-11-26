import unittest,tempfile,sqlite3,json,copy,sys
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p6_refresh_session_resume import validate,relocate,SESSION,ORIGINAL
from p6_guidance_shutdown import usage_segments

class RefreshShutdownTests(unittest.TestCase):
    def job(self):
        return {'role':'verifier','backend':'codex','scope':ORIGINAL.replace('060538','200000'),'root':str(ROOT/'fake'),'role_seconds':883,'refresh_judge_resume':{'session_id':SESSION,'original_scope':ORIGINAL,'prior_seconds':17,'keeps':str(ROOT/'fake/store')}}
    def test_only_original_judge_and_remaining_time(self):
        self.assertEqual(validate(self.job())['prior_seconds'],17)
        for field,value in [('role','builder'),('backend','dsh'),('role_seconds',900),('scope',ORIGINAL)]:
            j=self.job();j[field]=value
            with self.assertRaises(ValueError):validate(j)
        j=self.job();j['refresh_judge_resume']['keeps']=str(ROOT/'outside')
        with self.assertRaises(ValueError):validate(j)
    def test_copied_store_relocates_only_thread_index(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp);trace=p/'sessions/2026/11/26'/('rollout-'+SESSION+'.jsonl');trace.parent.mkdir(parents=True);trace.write_bytes(b'original history')
            with closing(sqlite3.connect(p/'state_5.sqlite'))as db,db:
                db.execute('CREATE TABLE threads(id TEXT, rollout_path TEXT)');db.execute('INSERT INTO threads VALUES (?,?)',(SESSION,'/original/path'))
            self.assertEqual(relocate(p)['history_edits'],0);self.assertEqual(trace.read_bytes(),b'original history')
            with closing(sqlite3.connect(p/'state_5.sqlite'))as db,db:db.execute('INSERT INTO threads VALUES (?,?)',('other','other'))
            with self.assertRaises(ValueError):relocate(p)
    def test_linked_scope_keeps_original_reservation_and_usage_once(self):
        from p6_main_budget import MainLedger,BudgetDenied
        config=json.loads((ROOT/'configs/budget-p6-model-refresh-approved.json').read_bytes())
        with tempfile.TemporaryDirectory()as tmp:
            ledger=MainLedger(Path(tmp)/'ledger.json',config);ledger.reserve_codex_turn(ORIGINAL,'gpt-6.1-sol');before=json.loads(ledger.path.read_bytes())
            with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn(ORIGINAL,'gpt-6.1-sol')
            ledger.reserve_codex_turn(self.job()['scope'],'gpt-6.1-sol');after=json.loads(ledger.path.read_bytes())
            self.assertEqual(after['codex_turns'][:1],before['codex_turns']);self.assertEqual(len(after['codex_turns']),2)
            self.assertEqual(before['cash_bound_nano'],after['cash_bound_nano'])
        before=dict(input_tokens=56495,cached_input_tokens=35840,output_tokens=298,reasoning_output_tokens=0,total_tokens=56793)
        after={k:v+100 for k,v in before.items()};old,delta=usage_segments(before,after)
        self.assertEqual(old['input_tokens']+delta['input_tokens'],after['input_tokens'])
        with self.assertRaises(ValueError):usage_segments(after,before)
if __name__=='__main__':unittest.main()
