"""Offline contracts: frozen evidence, phase/candidate cash, failed pools and judge identity."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p1_budget import Ledger,BudgetDenied,REQUEST_RESERVE
from p1_fixture import TASK
from p2_candidates import RUBRIC,digest,validate_pool,failure_report
from p2_judges import J0,J2,J3
from p2_contract import validate_contract


def pool(verdicts=('PASS','FAIL','INFRA_FAIL')):
    rows=[{'id':chr(65+i),'verdict':v,'base_commit':'a'*40,'env_hash':'env','prompt_hash':digest(TASK.encode()),
           'head_commit':str(i+1)*40,'source':'synthetic offline fixture','patch':'fixture','test_report':{'verdict':v},'known_failures':[]}
          for i,v in enumerate(verdicts)]
    value={'task_contract':TASK,'task_hash':digest(TASK.encode()),'rubric':RUBRIC,'rubric_hash':digest(RUBRIC),
           'base_commit':'a'*40,'env_hash':'env','candidates':rows}
    value['pool_hash']=digest(value)
    return value


class TestP2(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'.local-workbench/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)

    def test_phase_and_per_candidate_reservation(self):
        path=Path(self.temp.name)/'ledger.json'
        ledger=Ledger(path,phase='P2',requests=100,cash_nano=2_000_000_000)
        i=ledger.reserve_request('A',scope_requests=1,scope_cash_nano=500_000_000)
        with self.assertRaises(BudgetDenied):ledger.reserve_request('A',scope_requests=1)
        for cid in 'BCDE':ledger.reserve_request(cid)
        self.assertEqual(json.loads(path.read_text())['cash_bound_nano'],REQUEST_RESERVE*5)
        with self.assertRaises(BudgetDenied):Ledger(path).reserve_request('P1-must-not-touch-P2')
        ledger.settle(i,{'input_tokens':100,'cache_read_input_tokens':10,'cache_creation_input_tokens':0,'output_tokens':5},{})
        ledger.reserve_request('F')

    def test_global_cap_survives_restart(self):
        path=Path(self.temp.name)/'ledger.json'
        ledger=Ledger(path,phase='P2',requests=2,cash_nano=2_000_000_000)
        ledger.reserve_request('A');ledger.reserve_request('B')
        with self.assertRaises(BudgetDenied):Ledger(path,phase='P2',requests=2).reserve_request('C')

    def test_p2_hundred_request_cap_includes_all_roles(self):
        ledger=Ledger(Path(self.temp.name)/'ledger.json',phase='P2',requests=100,cash_nano=2_000_000_000)
        for index in range(100):
            request=ledger.reserve_request('J1' if index%2 else 'candidate')
            ledger.settle(request,{'input_tokens':1,'cache_read_input_tokens':0,'cache_creation_input_tokens':0,'output_tokens':1},{})
        with self.assertRaises(BudgetDenied):ledger.reserve_request('another-role')

    def test_generic_contract_has_fixed_base_env_and_safe_paths(self):
        contract={'task_id':'new-small-project','prompt':'Implement a whole small project','base_repository':'/opt/workbench/source/empty-base',
                  'base_commit':'a'*40,'env_hash':'locked','source_file':'package/main.py','visible_test_program':'assert True',
                  'acceptance_test_program':'assert True','protected_files':{}}
        self.assertEqual(validate_contract(contract,'locked')['source_file'],'package/main.py')
        for key,value in [('base_repository','/etc'),('source_file','../escape'),('base_commit','main'),('env_hash','different')]:
            invalid=contract|{key:value}
            with self.assertRaises(ValueError):validate_contract(invalid,'locked')

    def test_frozen_pool_rejects_mutations(self):
        original=pool();validate_pool(original)
        for edit in (lambda p:p['candidates'][0].update(source='changed'),lambda p:p['rubric']['dimensions'].append('new')):
            bad=copy.deepcopy(original);edit(bad)
            with self.assertRaises(ValueError):validate_pool(bad)
        bad=copy.deepcopy(original);bad['candidates'][1]['env_hash']='different';bad['pool_hash']=digest({k:v for k,v in bad.items() if k!='pool_hash'})
        with self.assertRaises(ValueError):validate_pool(bad)

    def test_all_fail_and_infrastructure_are_distinct(self):
        failed=failure_report(pool(('FAIL','FAIL','TIMEOUT'))['candidates'])
        self.assertEqual(failed['status'],'FAIL');self.assertTrue(failed['all_failed']);self.assertFalse(failed['best_failure_is_success'])
        self.assertEqual(len(failed['failures']),3)
        infra=failure_report(pool(('FAIL','INFRA_FAIL','BUDGET_EXHAUSTED'))['candidates'])
        self.assertEqual(infra['status'],'INDETERMINATE')
        self.assertEqual(failure_report(pool()['candidates'])['status'],'PASS')
        self.assertEqual(failure_report(pool(('TIMEOUT','TIMEOUT','TIMEOUT'))['candidates'])['status'],'TIMEOUT')
        self.assertEqual(failure_report(pool(('BUDGET_EXHAUSTED','BUDGET_EXHAUSTED','BUDGET_EXHAUSTED'))['candidates'])['status'],'BUDGET_EXHAUSTED')

    def test_j0_cannot_accept_failure(self):
        result=J0().judge(pool(('FAIL','FAIL','FAIL')))
        self.assertIsNone(result['eligible_selected']);self.assertTrue(result['human_review_required'])

    def test_same_evidence_missing_jev_is_explicit(self):
        p=pool();a=J0().judge(p);b=J2().judge(p)
        self.assertEqual(a['evidence_hash'],b['evidence_hash']);self.assertEqual(b['status'],'BLOCKED_CREDENTIAL')
        self.assertEqual(b['requests'],0)

    def test_sol_scores_not_probabilities_and_failure_remains_ineligible(self):
        p=pool();raw={'candidates':[{'id':cid,'correctness':2,'robustness':3,'maintainability':1,'evidence':['frozen test/code reference']} for cid in 'ABC'],
                       'ranking':['B','C','A'],'rationale':'offline contract only'}
        j=J3(lambda _: (raw,{'kind':'MOCK_TRANSPORT_ONLY'})).judge(p)
        self.assertEqual(j['eligible_selected'],'A');self.assertIn('not-logprobs',j['algorithm'])
        raw['ranking']=['B','B','A']
        with self.assertRaises(ValueError):J3(lambda _: (raw,{})).judge(p)
        raw['ranking']=['A','B','C'];raw['candidates'][0]['correctness']=5
        with self.assertRaises(ValueError):J3(lambda _: (raw,{})).judge(p)

    def test_jev_typed_interface_offline_only(self):
        p=pool()
        def transport(body):
            self.assertEqual(body['model'],'jev-latest')
            return {'model':'MOCK_ONLY','answers':{key:{'type':'score','score':1} for key in body['questions']}}
        result=J2(transport).judge(p)
        self.assertEqual(result['model_id'],'MOCK_ONLY');self.assertEqual(result['pool_hash'],p['pool_hash'])


if __name__=='__main__':unittest.main()
