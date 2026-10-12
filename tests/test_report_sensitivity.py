"""Prevent different-program comparisons and false accuracy for missing judges."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from report_sensitivity import paired_judgments


class ReportSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.identity={'original_pool_hash':'a'*64,'trace_pool_hash':'b'*64,
                       'unchanged_candidate_objects':[{'id':x} for x in 'ABC']}
        self.source={'J3':{'status':'COMPLETED','pool_hash':'a'*64,'ranking':list('ABC'),'raw_selected':'A','eligible_selected':None}}
        self.trace={'J3':{'status':'COMPLETED','pool_hash':'b'*64,'ranking':list('BAC'),'raw_selected':'B','eligible_selected':'B'}}
        self.truth={'A':{'verdict':'FAIL'},'B':{'verdict':'PASS'}}

    def test_change_uses_same_programs_and_independent_truth(self):
        before=copy.deepcopy((self.source,self.trace,self.identity))
        row=paired_judgments(self.source,self.trace,self.identity,self.truth)['judges']['J3']
        self.assertTrue(row['raw_selected_changed'])
        self.assertFalse(row['source_raw_selected_accepted'])
        self.assertTrue(row['trace_raw_selected_accepted'])
        self.assertEqual(row['source_eligible_selected_accepted'],'unavailable')
        self.assertAlmostEqual(row['pairwise_order_agreement'],2/3)
        self.assertEqual((self.source,self.trace,self.identity),before)

    def test_missing_or_blocked_is_not_comparable_or_zero_accuracy(self):
        for traced in ({}, {'J3':{'status':'TIMEOUT','pool_hash':'b'*64}}):
            row=paired_judgments(self.source,traced,self.identity,self.truth)['judges']['J3']
            self.assertEqual(row['status'],'INDETERMINATE')
            self.assertEqual(row['raw_selected_changed'],'unavailable')
            self.assertEqual(row['trace_raw_selected_accepted'],'unavailable')

    def test_wrong_pool_or_changed_candidate_coverage_is_refused(self):
        for change in ('pool','coverage','unknown-selection','duplicate-object'):
            trace=copy.deepcopy(self.trace);identity=copy.deepcopy(self.identity)
            if change=='pool':trace['J3']['pool_hash']='a'*64
            elif change=='coverage':trace['J3']['ranking']=['A','B']
            elif change=='unknown-selection':trace['J3']['raw_selected']='D'
            else:identity['unchanged_candidate_objects'].append({'id':'A'})
            with self.subTest(change=change),self.assertRaises(ValueError):
                paired_judgments(self.source,trace,identity,self.truth)
