import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_tms_legacy_contract import canonical_views,NF,MAX,BOUNDARY


class LegacyContractTests(unittest.TestCase):
    def example(self):
        return {'metadata':{'roi':['FC3','FC1','C3','C1'],'artifact_reviewed':True,'synthetic':True,
                            'pci_available':False,'allow_unreviewed':False},
                'scalars':{NF:None,MAX:2.,BOUNDARY:False,'other':17}}

    def test_alias_and_undefined_auxiliary_preserve_originals_and_other_fields(self):
        gold=self.example();actual=copy.deepcopy(gold);actual['metadata']['roi_order']=actual['metadata'].pop('roi')
        actual['scalars'][MAX]=None;actual['scalars'][BOUNDARY]=None
        before=copy.deepcopy(actual);original=copy.deepcopy(gold)
        a,r,changes=canonical_views(actual,gold)
        self.assertEqual(a['metadata']['roi'],r['metadata']['roi']);self.assertIsNone(a['scalars'][MAX]);self.assertIsNone(r['scalars'][MAX])
        self.assertEqual(a['scalars']['other'],17);self.assertEqual(actual,before);self.assertEqual(gold,original)
        self.assertEqual(len(changes),3)

    def test_conflicting_or_wrong_roi_and_non_boolean_metadata_are_not_waived(self):
        for mutation in ('conflict','order','boolean'):
            gold=self.example();actual=copy.deepcopy(gold)
            if mutation=='conflict':actual['metadata']['roi_order']=['wrong']
            if mutation=='order':actual['metadata']['roi'].reverse()
            if mutation=='boolean':actual['metadata']['artifact_reviewed']='false'
            with self.assertRaises(ValueError):canonical_views(actual,gold)

    def test_no_nf_does_not_exempt_incorrect_finite_maximum_or_boundary(self):
        for key,value in [(MAX,10.),(MAX,True),(MAX,float('nan')),(BOUNDARY,True),(BOUNDARY,0)]:
            gold=self.example();actual=copy.deepcopy(gold);actual['scalars'][key]=value
            with self.assertRaises(ValueError):canonical_views(actual,gold)

    def test_detected_nf_and_spurious_nf_are_untouched_for_original_judge(self):
        gold=self.example();gold['scalars'][NF]=20.;actual=copy.deepcopy(gold);actual['scalars'][MAX]=None
        a,r,changes=canonical_views(actual,gold)
        self.assertEqual(changes,[]);self.assertIsNone(a['scalars'][MAX]);self.assertEqual(r['scalars'][MAX],2.)
        gold=self.example();actual=copy.deepcopy(gold);actual['scalars'][NF]=50.
        a,r,changes=canonical_views(actual,gold)
        self.assertEqual(changes,[]);self.assertEqual(a['scalars'][NF],50.);self.assertIsNone(r['scalars'][NF])


if __name__=='__main__':unittest.main()
