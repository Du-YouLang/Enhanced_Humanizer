import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'benchmarks/pi-comparison/runners')]
from p1_budget import BudgetDenied
from p6_main_budget import MainLedger,authorization
import p6_pi_four_redo_scope as policy


class FourRedoTests(unittest.TestCase):
    def config(self,version):
        return json.loads((ROOT/('configs/budget-p6-main-'+version+'-approved.json')).read_bytes())

    def test_scope_currency_and_finite_caps_are_enforced(self):
        new=self.config('v9-cash500-four-redo')
        self.assertEqual(authorization(new)[0]['api_cash_usd'],500)
        for field,value in [('api_cash_usd',501),('paid_scope_policy','ALL'),('deepseek_inference_requests',10001),
                            ('per_request_output_tokens',128000),('per_request_timeout_seconds',601)]:
            with self.assertRaises(BudgetDenied):authorization({**new,field:value})
        for cell in policy.allowed_cells():
            name=cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
            scope='PI_FORMAL/formal-infra-redo4-20261016T040000Z/'+name
            self.assertTrue(policy.allowed_scope(scope,cell['provider']))
            self.assertFalse(policy.allowed_scope(scope+'/extra',cell['provider']))
            self.assertFalse(policy.allowed_scope(scope.replace('redo4','network-redo'),cell['provider']))
        self.assertFalse(policy.allowed_scope('PI_FORMAL/formal-infra-redo4-20261016T040000Z/BIP-black-5-P0-deepseek','deepseek'))

    def test_amendment_retains_unknowns_and_each_old_row_and_only_grants_four(self):
        old=self.config('v8-cash250-pi85');new=self.config('v9-cash500-four-redo')
        base=ROOT/'.local-workbench/tests/four-redo';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            path=Path(temp)/'ledger.json';prior=MainLedger(path,old,fixture=True)
            prior.reserve_request('old/unknown');prior.reserve_codex_turn('old/sub','gpt-6.1-sol')
            before=path.read_bytes();ledger=MainLedger(path,new);archive=Path(temp)/'archive.json'
            receipt=ledger.amend_authorization(old,archive)
            self.assertEqual(archive.read_bytes(),before)
            self.assertEqual(receipt['aggregate_caps']['cash_nano'],500_000_000_000)
            after=json.loads(path.read_bytes());original=json.loads(before)
            for field in ('requests','codex_turns','cash_bound_nano'):self.assertEqual(after[field],original[field])
            for cell in policy.allowed_cells():
                scope='PI_FORMAL/formal-infra-redo4-20261016T040000Z/'+cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
                if cell['provider']=='deepseek':ledger.reserve_request(scope)
                else:
                    ledger.reserve_codex_turn(scope,'gpt-6.1-sol')
                    with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn(scope,'gpt-6.1-sol')
            with self.assertRaises(BudgetDenied):ledger.reserve_request('unrelated')
            with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn('unrelated','gpt-6.1-sol')
            self.assertEqual(json.loads(path.read_bytes())['requests'][0],original['requests'][0])

    def test_authorization_never_changes_time_or_automatically_repeats_other_cells(self):
        old=self.config('v8-cash250-pi85');new=self.config('v9-cash500-four-redo')
        base=ROOT/'.local-workbench/tests/four-redo';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            path=Path(temp)/'ledger.json';MainLedger(path,old,fixture=True).reserve_request('old')
            changed={**new,'role_timeout_seconds_by_family':{'public':901,'scientific':1200}}
            with self.assertRaises(BudgetDenied):MainLedger(path,changed)
            self.assertFalse((Path(temp)/'archive.json').exists())

    def test_exact_four_original_infra_rows_and_one_fresh_trial_only(self):
        entries=[{'original_run':t[0],'result_path':'/opt/workbench/benchmark/private/pi-comparison/'+t[0]+'/'+c['task_id']+'-'+c['profile']+'-'+c['provider']+'/result.json'}
                 for t,c in zip(policy.TARGETS,policy.allowed_cells())]
        plan={'authorization':policy.AUTH,'cells':policy.allowed_cells(),'fresh_role_seconds':900,'fresh_role_requests':1000,
              'maximum_new_trials_per_cell':1,'original_result_preserved':True,'external_release_authorized':False,
              'cumulative_caps':{'deepseek_requests':10000,'api_cash_usd':500},'originals':entries}
        rows=[{'cell':c,'outcome':t[4],'role_seconds':900} for c,t in zip(policy.allowed_cells(),policy.TARGETS)]
        policy.validate_targets(plan,rows)
        for field,value in [('cells',list(reversed(policy.allowed_cells()))),('maximum_new_trials_per_cell',2),
                            ('original_result_preserved',False),('fresh_role_seconds',1800)]:
            with self.assertRaises(ValueError):policy.validate_targets({**plan,field:value},rows)
        bad=copy.deepcopy(rows);bad[0]['outcome']='PASS'
        with self.assertRaises(ValueError):policy.validate_targets(plan,bad)

    @unittest.skipIf(os.name=='nt','POSIX single-owner lock')
    def test_live_owner_blocks_every_new_trial(self):
        import fcntl
        import pi_four_infra_redo_linux as runner
        base=ROOT/'.local-workbench/tests/four-redo';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            pi=SimpleNamespace(BASE=Path(temp),protect_memory=lambda:None)
            core=SimpleNamespace(pi=pi)
            with (Path(temp)/'full-main-owner.lock').open('a') as held,patch.object(runner,'bind',return_value=core):
                fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):runner.execute({'plan':{},'mode':'execute'})


if __name__=='__main__':unittest.main()
