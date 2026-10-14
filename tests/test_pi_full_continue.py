import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'benchmarks/pi-comparison/runners/pi_full_continue_policy.py'
spec=importlib.util.spec_from_file_location('continue_policy',path);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class UnstartedContinuationTests(unittest.TestCase):
    def test_completed_pass_fail_and_infra_all_retained(self):
        cells=[{'task_id':str(i),'profile':'P0','provider':'subscription','repetition':0} for i in range(4)]
        rows=[{'cell':c,'worker_status':s} for c,s in zip(cells,('COMPLETED','COMPLETED','INFRA_FAIL'))]
        self.assertEqual(p.remaining_cells({'cells':cells},rows),cells[3:])
        self.assertEqual(rows[2]['worker_status'],'INFRA_FAIL')

    def test_reordered_nonprefix_or_success_stop_cannot_authorize_replay(self):
        cells=[{'task_id':str(i),'profile':'P0','provider':'deepseek','repetition':0} for i in range(3)]
        for rows in ([],[{'cell':cells[1],'worker_status':'INFRA_FAIL'}],
                     [{'cell':cells[0],'worker_status':'COMPLETED'}]):
            with self.assertRaises(ValueError):p.remaining_cells({'cells':cells},rows)


if __name__=='__main__':unittest.main()
