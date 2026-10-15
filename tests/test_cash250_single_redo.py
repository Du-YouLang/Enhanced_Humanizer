import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p6_main_budget import MainLedger,authorization
from p1_budget import BudgetDenied


class Cash250Tests(unittest.TestCase):
    def test_amendment_preserves_all_rows_and_limits_new_paid_scope(self):
        old=json.loads((ROOT/'configs/budget-p6-main-v6-cash200-approved.json').read_bytes())
        new=json.loads((ROOT/'configs/budget-p6-main-v7-cash250-single-redo-approved.json').read_bytes())
        root=ROOT/'.local-workbench/tests/cash250';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            path=Path(tmp)/'ledger.json';prior=MainLedger(path,old)
            prior.reserve_request('old/unknown');prior.reserve_codex_turn('old/subscription','gpt-6.1-sol')
            before=path.read_bytes();ledger=MainLedger(path,new)
            receipt=ledger.amend_authorization(old,Path(tmp)/'archive.json')
            self.assertEqual((Path(tmp)/'archive.json').read_bytes(),before)
            self.assertEqual(receipt['aggregate_caps']['cash_nano'],250_000_000_000)
            original=json.loads(before);current=json.loads(path.read_bytes())
            for k in ('requests','codex_turns','cash_bound_nano'):self.assertEqual(original[k],current[k])
            for scope in ('other','PI_FORMAL/formal-network-redo-20261015T020000Z/BIP-black-5-P2-deepseek'):
                with self.assertRaises(BudgetDenied):ledger.reserve_request(scope)
            with self.assertRaises(BudgetDenied):ledger.reserve_codex_turn('new/subscription','gpt-6.1-sol')
            ledger.reserve_request('PI_FORMAL/formal-network-redo-20261015T020000Z/BIP-black-5-P1-deepseek')
        for key,value in [('api_cash_usd',251),('paid_scope_policy','ALL'),('deepseek_inference_requests',10001)]:
            with self.assertRaises(BudgetDenied):authorization({**new,key:value})
