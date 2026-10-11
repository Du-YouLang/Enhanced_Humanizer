"""Complete-cell statistics and explicit ddof, independent of training results."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_pc_statistics import statistics_table


class PCStatisticsTests(unittest.TestCase):
    def rows(self):
        return [{'dataset':'test','activation':'relu','method':m,'width':w,'depth':d,'seed':s,
                 'final_test_acc':.5+(s-1)*(.1 if d==16 else .01),'grad_cos_to_bp':.7}
                for m in ('bp','pc','pcalm') for w in (8,16,32,64,128)
                for d in (8,16,32,64,128) for s in (0,1,2)]

    def result(self,rows):
        return statistics_table(rows,dataset='test',activation='relu',widths=(8,16,32,64,128),
                                depths=(8,16,32,64,128),seeds=(0,1,2))

    def test_depth16_contributes_and_ddof_conversions_are_explicit(self):
        result=self.result(self.rows());table={(r['method'],r['ddof']):r for r in result['cross_seed_statistics']}
        self.assertEqual(table['all',0]['cells'],75)
        expected_mean=(5*10+20*1)/25*math.sqrt(2/3)
        self.assertAlmostEqual(table['bp',0]['mean_std_pp'],expected_mean)
        self.assertAlmostEqual(table['bp',0]['max_std_pp'],10*math.sqrt(2/3))
        self.assertAlmostEqual(table['all',1]['mean_std_pp'],expected_mean*math.sqrt(3/2))
        self.assertEqual(result['same_seed_repeat_tolerance'],'NOT_ESTIMATED_FROM_CROSS_SEED_VARIANCE')

    def test_missing_depth_duplicate_and_unexpected_seed_refuse_statistics(self):
        rows=self.rows()
        for broken in ([r for r in rows if r['depth']!=16],rows+[rows[0]],rows+[rows[0]|{'seed':4}]):
            with self.assertRaises(ValueError):self.result(broken)


if __name__=='__main__':unittest.main()
