import copy
import importlib.util
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]/'benchmarks/pi-comparison/runners/pi_protocol.py'
spec=importlib.util.spec_from_file_location('pi_protocol',P);policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)


class FormalPiTests(unittest.TestCase):
    def plan(self):
        v={'cells':[{'task_id':tid,'profile':p,'provider':provider,'repetition':0}
                    for tid in ('BIP-black-2','SCI-GRANGER-GPU') for provider in ('deepseek','subscription') for p in ('P0','P1','P2','P3')],
           'bulk_256_enabled':False,'external_release_authorized':False}
        v['plan_sha256']=policy.digest(v)
        return v

    def test_no_missing_duplicate_or_reordered_cells_even_when_rehashed(self):
        v=self.plan();self.assertEqual(policy.validate_plan(v),v)
        for cells in (v['cells'][:-1],v['cells'][:-1]+[v['cells'][0]],list(reversed(v['cells']))):
            changed={**v,'cells':cells};changed.pop('plan_sha256');changed['plan_sha256']=policy.digest(changed)
            with self.assertRaises(ValueError):policy.validate_plan(changed)

    def test_approval_does_not_enable_release_or_bulk(self):
        for key in ('bulk_256_enabled','external_release_authorized'):
            v=self.plan();v[key]=True;v.pop('plan_sha256');v['plan_sha256']=policy.digest(v)
            with self.assertRaises(ValueError):policy.validate_plan(v)

    def test_unknown_usage_is_not_filled_with_zero(self):
        row={'usage':{'input_tokens':7,'output_tokens':3,'cache_read_input_tokens':2,'cache_creation_input_tokens':0}}
        summary={'usage':{'input_tokens':7,'output_tokens':3,'cache_read_tokens':2,'cache_write_tokens':0}}
        self.assertTrue(policy.settled_usage_match(summary,[row,{'status':'RESERVED_UNKNOWN_USAGE'}]))
        self.assertFalse(policy.settled_usage_match(summary,[{'status':'RESERVED_UNKNOWN_USAGE'}]))
        summary['usage']['output_tokens']=4
        self.assertFalse(policy.settled_usage_match(summary,[row]))

    def test_numeric_negative_changes_the_real_entrypoint_and_refuses_a_typo(self):
        source='def compute_gc(x):\n    return x + 3\n'
        transformed=policy.zero_numeric_returns(source,'compute_gc')
        ns={};exec(transformed,ns)
        self.assertEqual(ns['compute_gc'](5),0)
        with self.assertRaises(ValueError):policy.zero_numeric_returns(source,'compute_gc_gpu')


if __name__=='__main__':unittest.main()
