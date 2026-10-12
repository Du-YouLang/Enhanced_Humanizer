"""Repeat calibration must reject incomplete/duplicate data and excess drift."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_pc_calibrate_linux import CELLS,METHODS,repeat_statistics


class CalibrationTests(unittest.TestCase):
    def data(self):
        reference=[{'width':w,'depth':d,'method':m,'final_test_acc':.7,'grad_cos_to_bp':.8} for w,d in CELLS for m in METHODS]
        groups=[(label,reps,[{'width':w,'depth':d,'method':m,'repeat':r,'test_acc':.7,'grad_cos':.8}
                           for r in range(reps) for w,d in CELLS for m in METHODS])
                for label,reps in [('same-process',3),('cross-process-1',1),('cross-process-2',1)]]
        return groups,reference

    def test_complete_protocol_freezes_recommended_tolerance(self):
        groups,ref=self.data();result=repeat_statistics(groups,ref)
        self.assertEqual(result['status'],'PASS_LOCAL_CALIBRATION')
        self.assertEqual(result['training_runs'],60)
        self.assertEqual(result['accuracy_tolerance_pp'],.25)

    def test_missing_duplicate_extra_seed_repetition_and_nonfinite_are_rejected(self):
        for change in ('missing','duplicate','extra_rep','nan'):
            groups,ref=self.data();rows=groups[0][2]
            if change=='missing':rows.pop()
            elif change=='duplicate':rows[-1]=dict(rows[0])
            elif change=='extra_rep':rows[-1]['repeat']=3
            else:rows[-1]['test_acc']=float('nan')
            with self.subTest(change=change),self.assertRaises(ValueError):repeat_statistics(groups,ref)

    def test_cross_process_or_reference_drift_does_not_relax_threshold(self):
        for target,key,value in ((1,'test_acc',.703),(2,'grad_cos',.821)):
            groups,ref=self.data();groups[target][2][0][key]=value
            result=repeat_statistics(groups,ref)
            self.assertEqual(result['status'],'FAIL_LOCAL_CALIBRATION')
            self.assertFalse(result['tolerances_frozen_before_candidate_generation'])
        groups,ref=self.data();ref[0]['final_test_acc']=.71
        self.assertEqual(repeat_statistics(groups,ref)['status'],'FAIL_LOCAL_CALIBRATION')

    def test_process_protocol_cannot_be_substituted(self):
        groups,ref=self.data();groups[1],groups[2]=groups[2],groups[1]
        with self.assertRaises(ValueError):repeat_statistics(groups,ref)


if __name__=='__main__':unittest.main()
