"""Scientific coverage/claim integrity with constructed data, no efficacy claim."""
import copy
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from workbench.science import grid_summary,claim_checks,normalized_material_path


class ScienceTests(unittest.TestCase):
    def rows(self):
        return [{'dataset':'fixture','activation':'relu','method':m,'width':w,'depth':d,'seed':s,
                 'final_test_acc':{'bp':.8,'pc':.6,'pcalm':.78}[m]+s*.01,
                 'grad_cos_to_bp':{'bp':1.,'pc':.5,'pcalm':.8}[m]}
                for m in ('bp','pc','pcalm') for w in (8,16,128) for d in (8,64,128) for s in (0,1)]

    def summary(self, rows=None, **changes):
        args=dict(dataset='fixture',activation='relu',widths=(8,16,128),depths=(8,64,128),
                  seeds=(0,1),deep_narrow=((8,64),(8,128),(16,64),(16,128)))
        return grid_summary(self.rows() if rows is None else rows,**(args|changes))

    def test_fixed_region_does_not_change_with_grid_percentiles(self):
        rows=self.rows()
        for row in rows:
            if row['method']=='pcalm' and row['width']==16: row['final_test_acc']=.62
        summary=self.summary(rows)
        self.assertEqual(len(summary['deep_narrow_cells']),4)
        self.assertAlmostEqual(summary['pcalm_minus_pc_deep_narrow_mean'],.0975)
        self.assertAlmostEqual(summary['seed_spread']['pc']['ddof1_mean'],.01/math.sqrt(2))
        self.assertAlmostEqual(summary['seed_spread']['pc']['ddof0_mean'],.005)

    def test_missing_duplicate_nan_extra_seed_and_invalid_fraction_fail_closed(self):
        original=self.rows()
        for rows in (original[:-1],original+[original[0]],original+[original[0]|{'seed':9}],
                     [original[0]|{'final_test_acc':float('nan')}]+original[1:],
                     [original[0]|{'final_test_acc':80}]+original[1:]):
            with self.assertRaises(ValueError):self.summary(rows)
        with self.assertRaises(ValueError):self.summary(widths=(8,128))

    def test_all_five_checks_are_strict_and_claim_failure_is_not_zero_exit(self):
        summary=self.summary();limits={'C1':.04,'C2':.1,'C3':.1,'C4':.05,'C5':.15}
        result=claim_checks(summary,limits)
        self.assertTrue(result['claim_supported']);self.assertEqual(result['claim_exit_code'],0)
        limits['C5']=summary['pcalm_minus_pc_cosine_mean']
        result=claim_checks(summary,limits)
        self.assertFalse(result['claim_supported']);self.assertEqual(result['claim_exit_code'],1)
        self.assertEqual(result['implementation_fidelity'],'NOT_DETERMINED_BY_CLAIM_STATISTICS')
        limits.pop('C1')
        with self.assertRaises(ValueError):claim_checks(summary,limits)

    def test_windows_manifest_paths_normalize_but_cannot_escape(self):
        self.assertEqual(str(normalized_material_path('private_evaluation\\gold\\case.npz')),
                         'private_evaluation/gold/case.npz')
        for name in ('C:\\secret','../gold','a\\..\\gold','/gold','a//gold','a/./gold','a\x00b'):
            with self.assertRaises(ValueError):normalized_material_path(name)


if __name__=='__main__':unittest.main()
