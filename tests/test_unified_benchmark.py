import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from unified_benchmark_analysis import normalized_codex_usage,normalized_pi_usage,ds_usage,codex_usage,normalize_pi,exact_p,add_observed


class UnifiedBenchmarkTests(unittest.TestCase):
    def test_codex_cache_and_reasoning_subsets_are_not_added_twice(self):
        value=normalized_codex_usage({'input_tokens':1000,'cached_input_tokens':700,'output_tokens':30,'reasoning_output_tokens':10})
        self.assertEqual(value['input']+value['cache_read']+value['output'],1030)
        self.assertEqual(value['reasoning'],10)
        with self.assertRaises(ValueError):normalized_codex_usage({'input_tokens':100,'cached_input_tokens':101,'output_tokens':1})

    def test_pi_input_is_disjoint_from_cache(self):
        value=normalized_pi_usage({'input_tokens':300,'cache_read_tokens':700,'cache_write_tokens':0,'output_tokens':30,'reasoning_tokens':None})
        self.assertEqual(value['input']+value['cache_read']+value['output'],1030)
        self.assertIsNone(value['reasoning'])

    def test_unknown_requests_remain_missing_and_scope_reuse_is_deduplicated(self):
        ledger={'scope':{'requests':2,'known_usage':1,'unknown_usage':1,'usage':{'input_tokens':10,'cache_read_input_tokens':90,'cache_creation_input_tokens':0,'output_tokens':4},'charge_bound_nano':2}}
        value=ds_usage(['scope','scope'],ledger)
        self.assertEqual(value['requests'],2);self.assertEqual(value['unknown_requests'],1);self.assertFalse(value['complete'])
        self.assertEqual(value['observed']['output'],4)
        self.assertIsNone(add_observed([])['input'])
        with self.assertRaises(ValueError):ds_usage(['absent'],ledger)

    def test_duplicate_subscription_session_does_not_double_bill_tokens(self):
        usage={'session_id':'one','usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':10}}
        worker={'scope':'same','usage':[usage,copy.deepcopy(usage)]}
        value=codex_usage([worker],{'same':{'subscription_reservations':2}})
        self.assertEqual(value['known_sessions'],1);self.assertEqual(value['observed']['output'],10);self.assertFalse(value['complete'])

    def test_fresh_retry_selects_new_result_and_charges_failed_attempts_without_extra_task(self):
        cell={'task_id':'BIP-black-5','profile':'P1','provider':'deepseek'}
        def trial(scope,status,seconds):return {'cell':cell,'scope':scope,'outcome':status,'head_commit':scope,'usage':None,'coding_and_public_seconds':seconds}
        original=trial('old','INFRA_RETRY_PENDING',900);middle=trial('redo','FAIL',113);fresh=trial('new','PASS',486)
        ledger={s:{'requests':1,'known_usage':1,'unknown_usage':0,'usage':{'input_tokens':10,'cache_read_input_tokens':90,'cache_creation_input_tokens':0,'output_tokens':4},'charge_bound_nano':1} for s in ('old','redo','new')}
        intake={'pi':[{'result':original}],'ledger_scopes':ledger,'supplements':{'pi_four_fresh':{'data':{'results':[fresh]}},'pi_network_redo':{'data':{'result':middle}},'pi_overload_recovery':{'data':{'results':[]}}}}
        prior=copy.deepcopy(intake)
        review={'pi_rows':[dict(cell,official_status='INFRA_RETRY_PENDING',head_commit='old',source_run='first')]}
        rows=normalize_pi(intake,review)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['latest_status'],'PASS');self.assertEqual(rows[0]['first_reviewed_status'],'INFRA_RETRY_PENDING')
        self.assertEqual(rows[0]['ds']['requests'],3);self.assertEqual(rows[0]['selected_ds']['requests'],1)
        self.assertEqual(rows[0]['all_attempt_seconds_observed'],1499);self.assertEqual(rows[0]['selected_seconds'],486)
        self.assertEqual(intake,prior)

    def test_paired_small_sample_does_not_turn_three_wins_into_significance(self):
        self.assertEqual(exact_p(3,0),.25);self.assertEqual(exact_p(0,0),1);self.assertEqual(exact_p(2,1),1)
