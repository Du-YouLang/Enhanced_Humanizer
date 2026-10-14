"""Shutdown handover boundaries and exact amendment reconciliation; zero models."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from continue_cash_budget import boundary_ready,check_gate,supervise
from cash_amend_linux import amend_or_reconcile,idle
from p6_main_budget import MainLedger

class CashHandoverTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.local-workbench/test-tmp';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_partial_failed_or_duplicate_pc_cannot_activate(self):
        complete={'status':'FINISHED_WITH_PENDING_INTERRUPTED','completed_receipts':{'p6-main-execute-SCI-PC-ALM-one':'a'*64,'p6-main-sensitivity-SCI-PC-ALM-one':'b'*64}}
        self.assertTrue(boundary_ready(complete))
        for status in ('OBSERVE_ACCEPTANCE_CONTINUATION','ADOPT_NATIVE','RECOVERY_BLOCKED'):
            bad=copy.deepcopy(complete);bad['status']=status;self.assertFalse(boundary_ready(bad))
        bad=copy.deepcopy(complete);bad['completed_receipts'].pop('p6-main-sensitivity-SCI-PC-ALM-one');self.assertFalse(boundary_ready(bad))
        bad=copy.deepcopy(complete);bad['completed_receipts']['p6-main-execute-SCI-PC-ALM-two']='c'*64;self.assertFalse(boundary_ready(bad))

    def test_all_exact_ci_checks_required(self):
        good=dict(commit='a'*40,checks=dict(integrity='SUCCESS',secrets='SUCCESS',**{'linux-budget':'SUCCESS'}))
        check_gate(good,'a'*40)
        for key in good['checks']:
            bad=copy.deepcopy(good);bad['checks'][key]='FAILURE'
            with self.assertRaises(ValueError):check_gate(bad,'a'*40)
        with self.assertRaises(ValueError):check_gate(good,'b'*40)

    def test_active_native_owners_block_ledger_handover(self):
        for name in ('p6_main_runtime_linux.py','continue_p6_acceptance_linux.py'):
            p=self.root/'123';p.mkdir(exist_ok=True);(p/'cmdline').write_bytes(('/usr/bin/python\0/opt/workbench/source/'+name+'\0').encode())
            with self.assertRaises(ValueError):idle(self.root)
        (p/'cmdline').write_bytes(b'ordinary-unrelated-process\0');idle(self.root)

    def test_crash_after_amendment_reconciles_exact_archive_without_reset(self):
        old=json.loads((ROOT/'configs/budget-p6-main-v5-network-approved.json').read_text())
        new=json.loads((ROOT/'configs/budget-p6-main-v6-cash200-approved.json').read_text())
        path=self.root/'ledger.json';archive=self.root/'before.json'
        MainLedger(path,old).reserve_request('CONTROL/old');before=path.read_bytes()
        first=amend_or_reconcile(path,old,new,archive);after=path.read_bytes()
        replay=amend_or_reconcile(path,old,new,archive)
        self.assertEqual(path.read_bytes(),after);self.assertEqual(archive.read_bytes(),before)
        self.assertEqual(first['cash_bound_nano_retained'],replay['cash_bound_nano_retained'])
        MainLedger(path,new).reserve_request('CONTROL/new')
        with self.assertRaises(ValueError):amend_or_reconcile(path,old,new,archive)

    def test_archive_only_crash_is_preserved_and_requires_inspection(self):
        old=json.loads((ROOT/'configs/budget-p6-main-v5-network-approved.json').read_text())
        new=json.loads((ROOT/'configs/budget-p6-main-v6-cash200-approved.json').read_text())
        path=self.root/'ledger.json';archive=self.root/'before.json'
        MainLedger(path,old).reserve_request('CONTROL/old');before=path.read_bytes();archive.write_bytes(before)
        with self.assertRaises(ValueError):amend_or_reconcile(path,old,new,archive)
        self.assertEqual(before,path.read_bytes());self.assertEqual(before,archive.read_bytes())

    def bridge_fixture(self):
        import hashlib
        project=self.root;folder=project/'.local-workbench/bridge';folder.mkdir(parents=True)
        paths=[]
        for name,tasks in [('old',['SCI-PC-ALM']),('future',['SCI-STROKE','SCI-EGL','SCI-GRANGER-GPU'])]:
            dest=project/'.local-workbench'/name;dest.mkdir();p=dest/'config.private.json';p.write_text(json.dumps(dict(tasks=tasks)))
            paths.append(p)
        gate=project/'.local-workbench/gate.json';gate.write_text(json.dumps(dict(commit='a'*40,checks=dict(integrity='SUCCESS',secrets='SUCCESS',**{'linux-budget':'SUCCESS'}))))
        config=dict(project=str(project),authorization='USER_APPROVED_2026-10-13_CUMULATIVE_USD200',files={},old_tasks=['SCI-PC-ALM'],
                    old_config=str(paths[0]),future_config=str(paths[1]),old_config_sha256=hashlib.sha256(paths[0].read_bytes()).hexdigest(),
                    future_config_sha256=hashlib.sha256(paths[1].read_bytes()).hexdigest(),ci_gate=dict(commit='a'*40,receipt='.local-workbench/gate.json'))
        p=folder/'config.private.json';p.write_text(json.dumps(config));(folder/'enabled.private.json').write_text('{"enabled":true}')
        return p,paths

    def test_future_dispatch_follows_durable_phase_and_repeat_finished_skips(self):
        config,paths=self.bridge_fixture()
        old=dict(status='FINISHED_WITH_PENDING_INTERRUPTED',completed_receipts={'p6-main-execute-SCI-PC-ALM-one':'a'*64,'p6-main-sensitivity-SCI-PC-ALM-one':'b'*64})
        (paths[0].parent/'state.private.json').write_text(json.dumps(old))
        calls=[]
        def once(path):
            calls.append(path)
            if path==str(paths[0]):return old
            stored=json.loads((config.parent/'state.private.json').read_bytes())
            self.assertEqual(stored['phase'],'FUTURE_COHORT')
            self.assertTrue((config.parent/'cash-activation.private.json').exists())
            return dict(status='ALL_COMPLETED',ledger={'requests':11})
        with patch('continue_cash_budget.supervisor_once',side_effect=once),patch('continue_cash_budget.activate',return_value=dict(status='CONTROL_ONLY',model_calls=0)) as activate:
            self.assertEqual(supervise(config,once=True)['phase'],'FINISHED');activate.assert_called_once()
            self.assertEqual(supervise(config,once=True)['phase'],'FINISHED')
        self.assertEqual(calls,[str(p) for p in paths])

    def test_active_acceptance_keeps_old_cohort_without_amendment(self):
        config,paths=self.bridge_fixture()
        with patch('continue_cash_budget.supervisor_once',return_value=dict(status='OBSERVE_ACCEPTANCE_CONTINUATION')) as once,patch('continue_cash_budget.activate') as activate:
            self.assertEqual(supervise(config,once=True)['phase'],'OLD_COHORT')
            once.assert_called_once_with(str(paths[0]));activate.assert_not_called()

if __name__=='__main__':unittest.main()
