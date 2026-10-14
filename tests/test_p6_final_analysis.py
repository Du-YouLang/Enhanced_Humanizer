"""Offline reporting guards; synthetic rows are never model evidence."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_final_analysis import summarize,validate_input,measured


def fixture():
    rows=[]
    for task in range(16):
        for arm in 'ABCDEF':
            rows.append({'task_id':f'task-{task}','family':'public' if task<12 else 'scientific','arm':arm,
                         'original_outcome':'PASS' if task<8 else 'FAIL','outcome':'PASS' if task<8 else 'FAIL',
                         'receipt_sha256':'1'*64,'contract_sha256':'2'*64,'manifest_sha256':'3'*64,'adjudication_sha256':None,
                         'metrics':{'end_to_end_seconds':100 if task!=0 else 'unavailable','api_upper_bound_usd':1.,
                                    'subscription_turns':0,'input_tokens':20 if task!=1 else 'unavailable'}})
    return {'rows':rows,'judges':[],'merges':[],'models_started':0,'whole_task_replays':0,'github_operations':0,
            'budget':{'groups':{'only':{'requests':1,'api_upper_bound_usd':1.}},'requests':1,'api_upper_bound_usd':1.,'actual_api_cash_usd':None}}


class FinalAnalysisTests(unittest.TestCase):
    def test_failures_stay_in_denominator_and_missing_times_are_not_zero(self):
        stats=summarize(fixture())['arms']['A']
        self.assertEqual((stats['accepted'],stats['total']),(8,16))
        self.assertEqual(stats['median_recorded_path_seconds'],100)
        self.assertEqual(stats['path_seconds_coverage'],15)
        self.assertEqual(stats['path_api_bound_per_acceptance_usd'],2)
        self.assertEqual(stats['token_coverage'],15)
        self.assertEqual(measured([0,'unavailable',None,10]),[0,10])

    def test_duplicate_or_missing_cell_cannot_inflate_report(self):
        data=fixture();data['rows'][-1]=copy.deepcopy(data['rows'][0])
        with self.assertRaisesRegex(ValueError,'distinct'):validate_input(data)

    def test_original_failure_needs_explicit_supplement_before_promotion(self):
        data=fixture();row=data['rows'][-1];row['outcome']='PASS'
        with self.assertRaisesRegex(ValueError,'supplemental'):validate_input(data)
        row['adjudication_sha256']='4'*64
        self.assertEqual(summarize(data)['arms']['F']['accepted'],9)
        self.assertEqual(summarize(data)['arms']['F']['original_accepted'],8)

    def test_global_ledger_groups_cannot_duplicate_cost_or_invent_invoice(self):
        data=fixture();data['budget']['groups']['duplicate']={'requests':1,'api_upper_bound_usd':1.}
        with self.assertRaisesRegex(ValueError,'reconcile'):validate_input(data)
        data=fixture();data['budget']['actual_api_cash_usd']=1.
        with self.assertRaisesRegex(ValueError,'invoice'):validate_input(data)


if __name__=='__main__':unittest.main()
