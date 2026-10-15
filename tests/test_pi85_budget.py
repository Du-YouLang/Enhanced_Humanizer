import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'benchmarks/pi-comparison/runners')]
from p6_main_budget import MainLedger,authorization
from p1_budget import BudgetDenied
from p6_pi_remaining_scope import REVISION,allowed_cells,allowed_scope
from pi_full_continue_policy import transport_successor
from pi_full_protocol import budget_available,validate_plan,digest


class Pi85BudgetTests(unittest.TestCase):
    def config(self):return json.loads((ROOT/'configs/budget-p6-main-v8-cash250-pi85-approved.json').read_bytes())
    def test_exact85_matches_original_suffix_and_excludes_every_closed_cell(self):
        original=json.loads((ROOT/'benchmarks/pi-comparison/full-main-plan-v4.json').read_bytes())
        self.assertEqual(allowed_cells(),original['cells'][27:]);self.assertEqual(len(allowed_cells()),85)
        for c in original['cells']:
            scope='PI_FORMAL/formal-full-compare-20261015T120000Z/'+c['task_id']+'-'+c['profile']+'-'+c['provider']
            self.assertEqual(allowed_scope(scope,c['provider']),c in allowed_cells())
        self.assertFalse(allowed_scope('PI_FORMAL/formal-network-redo-20261015T120000Z/BIP-black-5-P1-deepseek','deepseek'))
    def test_same_cap_scope_amendment_retains_old_charges_and_denies_replays(self):
        old=json.loads((ROOT/'configs/budget-p6-main-v7-cash250-single-redo-approved.json').read_bytes());new=self.config()
        base=ROOT/'.local-workbench/tests/pi85';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            path=Path(tmp)/'ledger.json';prior=MainLedger(path,old)
            prior.reserve_request('PI_FORMAL/formal-network-redo-20261015T023615Z/BIP-black-5-P1-deepseek')
            before=path.read_bytes();ledger=MainLedger(path,new);ledger.amend_authorization(old,Path(tmp)/'before.json')
            self.assertEqual((Path(tmp)/'before.json').read_bytes(),before)
            for k in ('requests','codex_turns','cash_bound_nano'):self.assertEqual(json.loads(before)[k],json.loads(path.read_bytes())[k])
            for c in allowed_cells():
                scope='PI_FORMAL/formal-full-compare-20261015T120000Z/'+c['task_id']+'-'+c['profile']+'-'+c['provider']
                if c['provider']=='deepseek':ledger.reserve_request(scope)
                else:ledger.reserve_codex_turn(scope,'gpt-6.1-sol')
            for c in ('BIP-black-5-P1-deepseek','BIP-black-5-P2-deepseek','BIP-black-4-P3-subscription'):
                scope='PI_FORMAL/formal-full-compare-20261015T120000Z/'+c
                with self.assertRaises(BudgetDenied):
                    ledger.reserve_codex_turn(scope,'gpt-6.1-sol') if c.endswith('subscription') else ledger.reserve_request(scope)
            self.assertEqual(json.loads(path.read_bytes())['authorization_history'][-1]['amendment_kind'],REVISION)
        for k,v in [('api_cash_usd',251),('deepseek_inference_requests',10001),('paid_scope_policy','ALL')]:
            with self.assertRaises(BudgetDenied):authorization({**new,k:v})
    def test_executor_change_cannot_alter_tasks_or_role_limits(self):
        original_plan=json.loads((ROOT/'benchmarks/pi-comparison/full-main-plan-v4.json').read_bytes())
        old_budget=json.loads((ROOT/'configs/budget-p6-main-v6-cash200-approved.json').read_bytes())
        original={'budget':old_budget,'plan':original_plan};new=copy.deepcopy(original)
        new['budget']=self.config();new['plan'].update(remaining85_budget_authorization=REVISION,authorized_paid_cells=allowed_cells(),
            cumulative_caps={'deepseek_requests':10000,'api_cash_usd':250},budget_authorization_sha256=authorization(new['budget'])[1])
        new['plan'].pop('plan_sha256');new['plan']['plan_sha256']=digest(new['plan'])
        validate_plan(new['plan']);transport_successor(original,new)
        for field,value in [('public_role_seconds',901),('models',{'deepseek':'other'}),('authorized_paid_cells',allowed_cells()[:-1])]:
            changed=copy.deepcopy(new);changed['plan'][field]=value
            with self.assertRaises(ValueError):transport_successor(original,changed)
        self.assertTrue(budget_available({'requests':[],'cash_bound_nano':201_000_000_000,'aggregate_caps':{'cash_nano':250_000_000_000}}))
        self.assertFalse(budget_available({'requests':[],'cash_bound_nano':250_000_000_000,'aggregate_caps':{'cash_nano':250_000_000_000}}))
