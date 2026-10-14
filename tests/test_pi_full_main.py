"""Missing-task dispatch, durable checkpoints and unchanged budget controls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'benchmarks/pi-comparison/runners/pi_full_protocol.py'
spec=importlib.util.spec_from_file_location('pi_full_policy_test',path)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class FullPiTests(unittest.TestCase):
    def plan(self):
        value={'protocol':p.PROTOCOL,'cells':p.cells(t for t in p.TASKS if t not in p.RETAINED_TASKS),
               'retained_cells':p.cells(p.RETAINED_TASKS),'main_manifest':{'tasks':[{'task_id':t} for t in p.TASKS]},
               'bulk_256_enabled':False,'external_release_authorized':False,
               'cumulative_caps':{'deepseek_requests':10000,'api_cash_usd':200}}
        value['plan_sha256']=p.digest(value);return value

    def rehash(self,value):
        value.pop('plan_sha256',None);value['plan_sha256']=p.digest(value);return value

    def test_full_scope_is112_new_plus16_retained_without_overlap(self):
        value=self.plan();self.assertEqual(p.validate_plan(value),value)
        self.assertEqual(len(value['cells']),112);self.assertEqual(len(value['retained_cells']),16)
        self.assertFalse({p.digest(c) for c in value['cells']}&{p.digest(c) for c in value['retained_cells']})
        self.assertEqual({c['task_id'] for c in value['cells']}|set(p.RETAINED_TASKS),set(p.TASKS))

    def test_duplicate_missing_reorder_old_replay_and_new_repetition_rejected(self):
        value=self.plan()
        for new in (value['cells'][:-1],value['cells'][:-1]+[value['cells'][0]],
                    list(reversed(value['cells'])),value['cells']+[value['retained_cells'][0]],
                    [{**value['cells'][0],'repetition':1},*value['cells'][1:]]):
            changed=copy.deepcopy(value);changed['cells']=new
            with self.assertRaises(ValueError):p.validate_plan(self.rehash(changed))

    def test_budget_and_release_cannot_expand_with_a_rehash(self):
        for key,new in (('cumulative_caps',{'deepseek_requests':20000,'api_cash_usd':400}),
                        ('external_release_authorized',True),('bulk_256_enabled',True)):
            value=self.plan();value[key]=new
            with self.assertRaises(ValueError):p.validate_plan(self.rehash(value))

    def test_completed_stages_reused_but_uncertain_model_never_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=p.Journal(tmp);calls=[]
            result=journal.run('first-model',lambda:calls.append(1) or {'actual':'done'})
            self.assertEqual(p.Journal(tmp).run('first-model',lambda:self.fail('Completed model replay')),result)
            self.assertEqual(calls,[1])
            def lost():raise InterruptedError('simulated loss of power')
            with self.assertRaises(InterruptedError):journal.run('next-model',lost)
            with self.assertRaises(p.UncertainStage):p.Journal(tmp).run('next-model',lambda:self.fail('Uncertain model replay'))
            self.assertTrue((Path(tmp)/'next-model.started.json').exists())

    def test_tampered_completed_stage_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=p.Journal(tmp);journal.run('public',lambda:{'verdict':'FAIL'})
            path=Path(tmp)/'public.completed.json';row=json.loads(path.read_bytes())
            row['value']['verdict']='PASS';path.write_text(json.dumps(row))
            with self.assertRaises(ValueError):journal.run('public',lambda:self.fail('Replay'))

    def test_cumulative_bound_stops_on_either_cap(self):
        self.assertTrue(p.budget_available({'requests':[None]*9999,'cash_bound_nano':199_999_999_999}))
        self.assertFalse(p.budget_available({'requests':[None]*10000,'cash_bound_nano':0}))
        self.assertFalse(p.budget_available({'requests':[],'cash_bound_nano':200_000_000_000}))


if __name__=='__main__':unittest.main()
