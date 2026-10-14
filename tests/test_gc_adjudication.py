import copy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_gc_adjudication import finalize_gc_review
from p6_gc_source_policy import REVIEW_CHECKS,checked_source_review,validate_gc_source


class GCAdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.text='def metadata(x):\n return cp.asnumpy(x)\n'
        self.review={'reviewer':'independent_acceptance','source_sha256':hashlib.sha256(self.text.encode()).hexdigest(),
                     'checks':{name:True for name in REVIEW_CHECKS},'metadata_download_lines':[2],
                     'finding':'Reviewed metadata helper only; no signal or regression host computation'}
        self.numeric={'verdict':'INDETERMINATE','numeric_verdict':'PASS_NUMERIC_REVIEW_PENDING',
                      'detail':{'verdict':'PASS_NUMERIC_REVIEW_PENDING'}}

    def test_exact_source_review_completes_existing_numeric_result_without_mutation(self):
        with self.assertRaises(ValueError):validate_gc_source(self.text)
        before=copy.deepcopy(self.numeric)
        result=finalize_gc_review(self.numeric,self.text,self.review,original_sha256='a'*64)
        self.assertEqual(result['verdict'],'PASS');self.assertEqual(self.numeric,before)
        self.assertTrue(result['numerical_execution_reused']);self.assertEqual(result['model_calls'],0)

    def test_numeric_failure_or_incomplete_result_cannot_be_promoted(self):
        for update in ({'verdict':'FAIL'},{'numeric_verdict':'FAIL'}, {'detail':{'verdict':'FAIL'}},
                       {'verdict':'RUNNING'}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                finalize_gc_review({**self.numeric,**update},self.text,self.review,original_sha256='a'*64)

    def test_missing_false_stale_or_wrong_location_review_is_refused(self):
        for change in ({'source_sha256':'0'*64},{'reviewer':'coding_candidate'}, {'finding':''},
                       {'checks':{}},{'metadata_download_lines':[]},{'metadata_download_lines':[3]},
                       {'checks':{**self.review['checks'],'substantive_gpu_regression':False}}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                checked_source_review(self.text,{**self.review,**change})
        with self.assertRaises(ValueError):checked_source_review(self.text+'\n# changed',self.review)

    def test_reviewed_metadata_download_never_exempts_array_get(self):
        text=self.text+'signals.get()\n'
        review={**self.review,'source_sha256':hashlib.sha256(text.encode()).hexdigest()}
        with self.assertRaises(ValueError):checked_source_review(text,review)


if __name__=='__main__':unittest.main()
