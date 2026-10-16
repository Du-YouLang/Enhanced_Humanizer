"""Paired evidence isolation and cumulative accounting; no provider calls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'benchmarks/pi-comparison/runners')]
from p6_guidance_protocol import (TASKS,BRANCHES,PROTOCOL,branch_order,digest,allowed_scope,
    mentor_view,validate_guidance,validate_plan)
from p6_main_budget import MainLedger,BudgetDenied,authorization
from pi_full_protocol import Journal,UncertainStage


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.c={'base_commit':'a'*40,'head_commit':'b'*40,'patch':'diff','source':'source',
            'test_report':{'verdict':'FAIL','log':'public only'},'known_failures':['public'],
            'hidden_acceptance':{'verdict':'PRIVATE_SECRET'},'worker_status':'COMPLETED'}
        self.g={'diagnosis':'Off by one at boundary','observations':[{'finding':'boundary omitted',
            'evidence_kind':'code','reference':'solver.py:10'}],'hypotheses':['Possible index issue'],
            'next_actions':['Check the boundary condition'], 'public_verification':['Run public boundary tests'],
            'limitations':['Hidden tests unavailable']}
    def test_matched_views_only_trace_differs_and_no_private_label(self):
        trace={'truncated':False,'records':[{'type':'tool/result','data':'observed failure'}]}
        baseline=mentor_view(self.c,'task');augmented=mentor_view(self.c,'task',trace)
        self.assertEqual(baseline,{k:v for k,v in augmented.items() if k!='tool_trace'})
        self.assertNotIn('PRIVATE_SECRET',json.dumps(augmented))
        self.assertNotIn('worker_status',baseline)
        self.assertEqual(sum(branch_order(t)[0]==BRANCHES[0] for t in TASKS),8)
        with self.assertRaises(ValueError):mentor_view(self.c,'task',{'truncated':True})
    def test_guidance_cannot_cite_unseen_trace_or_return_patch(self):
        view=mentor_view(self.c,'task');validate_guidance(self.g,view)
        altered=copy.deepcopy(self.g);altered['observations'][0]['evidence_kind']='trace'
        with self.assertRaises(ValueError):validate_guidance(altered,view)
        validate_guidance(altered,{**view,'tool_trace':{}})
        for edit in ({'next_actions':['```python\npass\n```']},{'observations':[]},{'next_actions':[]}):
            with self.assertRaises(ValueError):validate_guidance({**self.g,**edit},view)
    def test_scope_exact_roles_tasks_and_provider(self):
        prefix='GUIDANCE/guidance-20261016T120000Z/'
        for tid in TASKS:
            self.assertTrue(allowed_scope(prefix+tid+'/initial-ds','deepseek'))
            self.assertTrue(allowed_scope(prefix+tid+'/code-tests-trace-mentor','subscription'))
        for s,p in [(prefix+TASKS[0]+'/initial-ds','subscription'),
                    (prefix+'other/initial-ds','deepseek'),(prefix+TASKS[0]+'/code-tests-mentor','deepseek'),
                    (prefix+TASKS[0]+'/initial-ds/extra','deepseek')]:self.assertFalse(allowed_scope(s,p))
    def test_plan_changes_and_omitted_tasks_rejected(self):
        plan={'protocol':PROTOCOL,'tasks':list(TASKS),'branches':list(BRANCHES),'effort':'low',
            'shared_initial_ds':True,'mentor_writes_code':False,'hidden_after_both_branches_frozen':True,
            'cumulative_requests':15000,'cumulative_usd':500,'external_release_authorized':False}
        plan['plan_sha256']=digest(plan);validate_plan(plan)
        for key,value in [('tasks',list(TASKS[:-1])),('mentor_writes_code',True),('effort','high')]:
            altered={**plan,key:value};altered.pop('plan_sha256');altered['plan_sha256']=digest(altered)
            with self.assertRaises(ValueError):validate_plan(altered)
    def test_journal_reuses_completion_and_blocks_uncertain_action(self):
        with tempfile.TemporaryDirectory() as folder:
            journal=Journal(folder);calls=[]
            self.assertEqual(journal.run('first',lambda:calls.append(1) or {'result':'complete'}),{'result':'complete'})
            journal.run('first',lambda:self.fail('Completed model must never replay'))
            self.assertEqual(calls,[1])
            with self.assertRaises(RuntimeError):journal.run('interrupted',lambda:(_ for _ in ()).throw(RuntimeError('power loss')))
            with self.assertRaises(UncertainStage):journal.run('interrupted',lambda:self.fail('Uncertain model must block'))
    def test_amendment_preserves_unknown_and_settled_rows_and_subscription(self):
        old=json.loads((ROOT/'configs/budget-p6-main-v9-cash500-four-redo-approved.json').read_bytes())
        new=json.loads((ROOT/'configs/budget-p6-main-v10-guidance-approved.json').read_bytes())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ledger.json';ledger=MainLedger(path,old,fixture=True)
            ledger.reserve_request('old-unknown');index=ledger.reserve_request('old-settled')
            ledger.settle(index,{'input_tokens':4,'cache_read_input_tokens':3,'cache_creation_input_tokens':0,'output_tokens':2},{'model_id':'deepseek-flash'})
            ledger.reserve_codex_turn('old-sol','gpt-6.1-sol');before=path.read_bytes();archive=Path(folder)/'archive.json'
            updated=MainLedger(path,new);r=updated.amend_authorization(old,archive)
            after=json.loads(path.read_bytes());prior=json.loads(before)
            for key in ('requests','codex_turns','cash_bound_nano'):self.assertEqual(after[key],prior[key])
            self.assertEqual(archive.read_bytes(),before);self.assertEqual(r['aggregate_caps']['requests'],15000)
            scope='GUIDANCE/guidance-20261016T120000Z/BIP-black-1/'
            updated.reserve_request(scope+'initial-ds');updated.reserve_codex_turn(scope+'code-tests-mentor','gpt-6.1-sol')
            saved=path.read_bytes()
            with self.assertRaises(BudgetDenied):updated.reserve_request('old-unknown')
            with self.assertRaises(BudgetDenied):updated.reserve_codex_turn(scope+'initial-ds','gpt-6.1-sol')
            self.assertEqual(path.read_bytes(),saved)
            changed={**new,'per_request_timeout_seconds':601}
            with self.assertRaises(BudgetDenied):authorization(changed)


if __name__=='__main__':unittest.main()
