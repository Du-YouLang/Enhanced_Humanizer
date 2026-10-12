"""An unavailable judge cannot silently turn enhanced arms into J0 fallbacks."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p2_candidates import digest
from p2_judges import J0,blocked
from p6_main_contract import enhanced_selection,classify_role_completion
from test_p2 import pool


class MainContractTests(unittest.TestCase):
    def test_trusted_request_cap_is_failure_not_infrastructure_or_retry(self):
        raw={'status':'INFRA_FAIL','error':'HTTP 402','broker_denials':[{'reason':'Role request cap exhausted'}]}
        got=classify_role_completion(raw)
        self.assertEqual(got['status'],'BUDGET_EXHAUSTED')
        self.assertEqual(got['raw_worker_status'],'INFRA_FAIL')
        self.assertEqual(raw['status'],'INFRA_FAIL')
        self.assertEqual(got['error'],'HTTP 402')

    def test_upstream_402_policy_and_timeout_do_not_become_request_caps(self):
        for denials in ([],[{'reason':'Invalid output cap'}],[{'reason':'Role request cap exhausted'},{'reason':'Invalid request size'}]):
            raw={'status':'INFRA_FAIL','error':'HTTP 402','broker_denials':denials}
            self.assertEqual(classify_role_completion(raw),raw)
        raw={'status':'TIMEOUT','broker_denials':[{'reason':'Role request cap exhausted'}]}
        self.assertEqual(classify_role_completion(raw),raw)

    def setup_pools(self):
        original=pool();expanded=copy.deepcopy(original);expanded.pop('pool_hash')
        m=copy.deepcopy(expanded['candidates'][0]);m.update(id='M',head_commit='9'*40)
        expanded['candidates'].append(m);expanded['pool_hash']=digest(expanded)
        return original,expanded

    def test_incomplete_judges_do_not_select_any_fallback(self):
        original,expanded=self.setup_pools()
        self.assertEqual(enhanced_selection(original,expanded,J0().judge(original),J0().judge(expanded)),'A')
        for side in (0,1):
            judgments=[J0().judge(original),J0().judge(expanded)]
            judgments[side]=blocked((original,expanded)[side],'J3','TIMEOUT','controlled missing judge')
            self.assertIsNone(enhanced_selection(original,expanded,*judgments))

    def test_changed_original_or_wrong_pool_is_rejected(self):
        original,expanded=self.setup_pools();bad=copy.deepcopy(expanded);bad.pop('pool_hash')
        bad['candidates'][0]['source']='altered';bad['pool_hash']=digest(bad)
        with self.assertRaises(ValueError):enhanced_selection(original,bad,J0().judge(original),J0().judge(bad))
        with self.assertRaises(ValueError):enhanced_selection(original,expanded,J0().judge(expanded),J0().judge(expanded))


if __name__=='__main__':unittest.main()
