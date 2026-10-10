"""Offline P3 safety/acceptance contracts; no model calls or inference claims."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p1_budget import Ledger,BudgetDenied
from p2_candidates import digest
from p2_judges import J0
from p3_contracts import handoff,validate_handoff,judge_pool,with_initial_judgment,compare,checkpoint,validate_checkpoint
from test_p2 import pool


class TestP3(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'.local-workbench/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)

    def package(self):
        p=pool();p['candidates'][1]['test_report']['log']='HIDDEN_EXPECTED_ANSWER_DO_NOT_FORWARD'
        p.pop('pool_hash');p['pool_hash']=digest(p)
        return p,handoff(p,{cid:{'source.py':'complete candidate code'} for cid in 'ABC'},
                         {cid:{'verdict':'FAIL' if cid=='B' else 'PASS','log':'visible evidence'} for cid in 'ABC'})

    def test_handoff_contains_failures_and_withholds_hidden_test_answers(self):
        _,package=self.package();validate_handoff(package)
        self.assertEqual([c['id'] for c in package['candidates']],list('ABC'))
        self.assertNotIn('HIDDEN_EXPECTED_ANSWER',json.dumps(package))
        self.assertNotIn('HIDDEN_EXPECTED_ANSWER',json.dumps(judge_pool(package)))
        self.assertEqual(package['candidates'][1]['verdict'],'FAIL')

    def test_handoff_is_immutable_and_cannot_omit_a_candidate(self):
        p,package=self.package();package['candidates'].pop()
        with self.assertRaises(ValueError):validate_handoff(package)
        with self.assertRaises(ValueError):handoff(p,{'A':{}},{'A':{}})

    def test_judgment_cannot_come_from_another_pool(self):
        p,_=self.package();j=J0().judge(p);j['pool_hash']='another'
        with self.assertRaises(ValueError):handoff(p,{cid:{} for cid in 'ABC'},{cid:{} for cid in 'ABC'},[j])

    def test_reviewer_judgment_is_bound_to_the_exact_public_view(self):
        _,package=self.package();j=J0().judge(judge_pool(package))
        forwarded=with_initial_judgment(package,j);validate_handoff(forwarded)
        self.assertEqual(forwarded['judgments'],[j]);self.assertEqual(package['judgments'],[])
        for field in ('pool_hash','rubric_hash'):
            with self.assertRaises(ValueError):with_initial_judgment(package,j|{field:'another'})

    def test_public_view_survives_resume_without_rerunning_timed_tests(self):
        from unittest.mock import patch
        from p5_runtime_linux import frozen_handoff
        p,package=self.package();root=Path(self.temp.name);(root/'inputs').mkdir()
        pool_file=root/'pool.json';pool_file.write_text(json.dumps(p),encoding='utf-8')
        with patch('p5_runtime_linux.runtime.build_handoff',return_value=package) as build:
            initial=frozen_handoff(root,pool_file);j=J0().judge(judge_pool(initial))
            resumed=frozen_handoff(root,pool_file)
            self.assertEqual(with_initial_judgment(resumed,j)['judgments'],[j]);build.assert_called_once()
        file=root/'inputs/candidate-handoff.json';altered=json.loads(file.read_text(encoding='utf-8'));altered['candidates'][0]['visible_tests']['elapsed_seconds']=999
        file.write_text(json.dumps(altered),encoding='utf-8')
        with self.assertRaises(ValueError):frozen_handoff(root,pool_file)

    def test_m_does_not_win_automatically_and_failed_selection_is_rejected(self):
        p,_=self.package();m={'verdict':'FAIL'}
        value=compare(p,m,{'eligible_selected':'A'})
        self.assertEqual(value['selected_candidate'],'A');self.assertFalse(value['M_wins_automatically'])
        with self.assertRaises(ValueError):compare(p,m,{'eligible_selected':'M'})

    def test_all_failed_and_refused_m_never_become_success(self):
        p=pool(('FAIL','FAIL','FAIL'))
        for verdict,status in [('FAIL','FAIL'),('REFUSED','FAIL'),('INFRA_FAIL','INDETERMINATE')]:
            value=compare(p,{'verdict':verdict},{'eligible_selected':None})
            self.assertEqual(value['status'],status);self.assertFalse(value['M_added_any_passing_solution'])
        self.assertTrue(compare(p,{'verdict':'PASS'},{'eligible_selected':'M'})['M_added_any_passing_solution'])

    def test_checkpoint_cannot_change_task_stage_or_erase_progress(self):
        state=checkpoint(1,[{'name':'reviewer','result_sha256':'frozen'}],'contract')
        validate_checkpoint(state,'contract')
        for key,value in [('next_step',0),('stages',[]),('contract_hash','other')]:
            bad=copy.deepcopy(state);bad[key]=value
            with self.assertRaises(ValueError):validate_checkpoint(bad,'contract')

    def test_codex_phase_and_role_limits_survive_restart(self):
        path=Path(self.temp.name)/'ledger.json'
        ledger=Ledger(path,phase='P3',codex_turns=12)
        for _ in range(2):ledger.reserve_codex_turn('reviewer','gpt-6.1-sol',scope_turns=2)
        with self.assertRaises(BudgetDenied):Ledger(path,phase='P3',codex_turns=12).reserve_codex_turn('reviewer','gpt-6.1-sol',scope_turns=2)
        for index in range(10):ledger.reserve_codex_turn('role-'+str(index),'gpt-6.1-sol')
        with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn('extra','gpt-6.1-sol')
        with self.assertRaises(BudgetDenied):Ledger(path,phase='P2').reserve_codex_turn('cross-phase','gpt-6.1-sol')

    def test_phase_cash_and_request_budget_remain_independent(self):
        path=Path(self.temp.name)/'ledger.json';ledger=Ledger(path,phase='P3',requests=40)
        for _ in range(3):ledger.reserve_request('ds-return')
        with self.assertRaises(BudgetDenied):ledger.reserve_request('another')
        other=Ledger(Path(self.temp.name)/'other.json',phase='P3',requests=1)
        other.reserve_request('first')
        with self.assertRaises(BudgetDenied):other.reserve_request('second')

    def test_successful_harness_retry_requires_its_exact_session_model_and_tokens(self):
        from p3_worker_linux import completed_session
        failed={'session_id':'failed','model_id':'gpt-6.1-sol','usage':'unavailable'}
        success={'session_id':'completed','model_id':'gpt-6.1-sol','usage':{'input_tokens':12845,'output_tokens':658,'cached_input_tokens':0}}
        turns=[{'status':'COMPLETED','session_id':'completed','model_requested':'gpt-6.1-sol'}]
        self.assertEqual(completed_session([failed,success],turns),success)
        for usage,record in (([failed],turns),([success,success],turns),([success],turns*2),
                             ([success],[]),([success|{'model_id':'wrong-model'}],turns),
                             ([success|{'usage':'unavailable'}],turns),
                             ([success|{'usage':success['usage']|{'cached_input_tokens':12846}}],turns)):
            with self.assertRaises(RuntimeError):completed_session(usage,record)


if __name__=='__main__':unittest.main()
