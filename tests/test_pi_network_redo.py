import copy,importlib.util,json,os,sys,tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

p=Path(__file__).resolve().parents[1]/'benchmarks/pi-comparison/runners/pi_network_redo_policy.py'
s=importlib.util.spec_from_file_location('network_redo_policy',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class NetworkRedoTests(unittest.TestCase):
    def plan(self):
        return {'authorization':m.AUTH,'cell':dict(m.CELL),'original_run':m.ORIGINAL,
            'fresh_role_seconds':900,'fresh_role_requests':1000,'maximum_new_trials':1,
            'cumulative_caps':{'deepseek_requests':10000,'api_cash_usd':250},
            'cash_authorization':'USER_APPROVED_2026-10-15_CUMULATIVE_USD250_BLACK5_P1_ONLY','original_result_preserved':True,
            'external_release_authorized':False}
    def original(self):return {'cell':dict(m.CELL),'outcome':'INFRA_RETRY_PENDING','role_seconds':900}
    def test_only_exact_failed_cell_can_receive_one_new_trial(self):
        self.assertEqual(m.validate_redo(self.plan(),self.original()),self.plan())
        for key,value in [('cell',{**m.CELL,'profile':'P0'}),('maximum_new_trials',2),('fresh_role_seconds',901),
                          ('fresh_role_requests',1001),('cumulative_caps',{'deepseek_requests':10000,'api_cash_usd':201}),
                          ('external_release_authorized',True),('original_result_preserved',False)]:
            with self.assertRaises(ValueError):m.validate_redo({**self.plan(),key:value},self.original())
        for outcome in ('PASS','FAIL','TIMEOUT'):
            with self.assertRaises(ValueError):m.validate_redo(self.plan(),{**self.original(),'outcome':outcome})

    @unittest.skipIf(os.name=='nt','POSIX executor lock')
    def test_running_controller_prevents_dispatch(self):
        import fcntl
        sys.path.insert(0,str(p.parent))
        import pi_network_redo_linux as runtime
        root=p.parents[3]/'.local-workbench/tests/network-redo';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            base=Path(tmp);pi=SimpleNamespace(BASE=base,protect_memory=lambda:None)
            with (base/'full-main-owner.lock').open('a') as owned,patch.object(runtime,'bind',return_value=SimpleNamespace(pi=pi)):
                fcntl.flock(owned,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):runtime.execute({'mode':'execute','plan':{}})

    @unittest.skipIf(os.name=='nt','POSIX executor budget gate')
    def test_exhausted_budget_prevents_marker_and_model(self):
        sys.path.insert(0,str(p.parent))
        import pi_network_redo_linux as runtime
        root=p.parents[3]/'.local-workbench/tests/network-redo';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            base=Path(tmp);ledger=base/'ledger.json';ledger.write_text(json.dumps({'requests':[],'cash_bound_nano':249_900_000_000}))
            closed=base/'closed.json';closed.write_text('{}');marker=base/'once.json'
            pi=SimpleNamespace(BASE=base,LEDGER=ledger,protect_memory=lambda:None,quiet=lambda:None)
            core=SimpleNamespace(pi=pi,MainLedger=lambda *args:SimpleNamespace(request_reserve=622_000_000))
            plan={'after_run_receipt':str(closed),'single_use_marker':str(marker),'executor_payload':{'budget':{}}}
            before=ledger.read_bytes()
            with patch.object(runtime,'bind',return_value=core):result=runtime.execute({'mode':'execute','plan':plan})
            self.assertEqual(result['status'],'BLOCKED_CUMULATIVE_BUDGET');self.assertFalse(result['redo_started'])
            self.assertEqual(ledger.read_bytes(),before);self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
