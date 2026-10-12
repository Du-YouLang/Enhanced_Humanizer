"""A manually continued pre-spend refusal cannot retry a model failure."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_p6_main_batch import continuation_attempts


class BatchContinuationTests(unittest.TestCase):
    def setUp(self):
        self.manifest={'manifest_sha256':'a'*64}
        self.batch={'status':'STOPPED_PRESERVED_NO_AUTOMATIC_RETRY','manifest_sha256':'a'*64,
                    'automatic_retry':False,'planned_tasks':['first','second'],
                    'attempts':[{'task_id':'first','mode':'execute','status':'MAIN_TASK_COMPLETED',
                                 'run_id':'owned-first','alive':False},
                                {'task_id':'first','mode':'sensitivity','status':'LAUNCHING'}]}
        self.log='RuntimeError: Commit and validate source before paid execution'

    def test_reuses_completed_source_without_mutating_old_index(self):
        before=copy.deepcopy(self.batch)
        reused=continuation_attempts(self.batch,self.manifest,self.log)
        self.assertEqual([a['run_id'] for a in reused],['owned-first'])
        reused[0]['status']='changed'
        self.assertEqual(self.batch,before)

    def test_paid_failure_or_changed_protocol_cannot_resume(self):
        for change in ('failed-source','started-tail','changed-protocol','missing-proof'):
            batch=copy.deepcopy(self.batch);manifest=dict(self.manifest);log=self.log
            if change=='failed-source':batch['attempts'][0]['status']='INFRA_FAIL'
            elif change=='started-tail':batch['attempts'][-1]['run_id']='already-started'
            elif change=='changed-protocol':manifest['manifest_sha256']='b'*64
            else:log='Unspecified launch failure'
            with self.subTest(change=change),self.assertRaises(ValueError):
                continuation_attempts(batch,manifest,log)

    def test_skipping_task_or_mode_is_refused(self):
        batch=copy.deepcopy(self.batch);batch['attempts'][-1]['task_id']='second'
        with self.assertRaises(ValueError):continuation_attempts(batch,self.manifest,self.log)
