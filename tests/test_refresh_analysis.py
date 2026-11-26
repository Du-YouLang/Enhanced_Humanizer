"""MOCK data only: immutable144 directory, audits, costs and complete-time coverage."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p6_refresh_analysis import build,digest,telemetry,TASKS,MODELS,METHODS
from report_p6_refresh import render,write


def metrics(units=1):
    return {'deepseek':{'requests':units,'known_usage_requests':units,'unknown_usage_requests':0,'input_tokens_known':10*units,'cache_read_input_tokens_known':8*units,'output_tokens_known':2*units},
    'openai':{'subscription_reservations':units,'recorded_session_usage_segments':units,'input_tokens_recorded':10*units,'cached_input_tokens_subset':8*units,'output_tokens_recorded':2*units,'token_totals_are_lower_bounds':False,'unknown_usage_scopes':[]}}


def row(task=TASKS[0],model='GPT61-Sol',method='Direct',status='PASS',seconds=10):
    return {'task_id':task,'model':model,'method':method,'outcome':status,'candidate':{'id':'sample','root':'MOCK','base_commit':'base','head_commit':'fixed','verdict':'PASS','test_report':{'verdict':'PASS'},'working_tree':'','protected_paths_modified':[]},
    'frozen':{'program_sha256':'1'*64},'acceptance':{'verdict':'PASS' if status=='PASS' else 'FAIL'},'metrics':metrics(),
    'method_timing':{'elapsed_seconds':seconds,'io_adjustment':{'raw_elapsed_seconds':10,'full_local_io_stall_seconds':2,'io_adjusted_elapsed_estimate_seconds':8}} if seconds==10 else {'elapsed_seconds':seconds}}


class AnalysisTests(unittest.TestCase):
    def test_duplicate_cells_and_unexpected_supplements_fail_closed(self):
        r=row()
        with self.assertRaisesRegex(ValueError,'duplicate'):build({'groups':[{'rows':[r,copy.deepcopy(r)]}]})
        with self.assertRaisesRegex(ValueError,'Unexpected'):build({'groups':[{'rows':[r]}],'interface_supplements':[{'rows':[r]}]})
        missing=copy.deepcopy(r);missing['candidate'].pop('protected_paths_modified')
        with self.assertRaisesRegex(ValueError,'Software PASS lacks'):build({'groups':[{'rows':[missing]}]})
    def test_corrected_supplement_preserves_raw_and_does_not_rebill_shared_builders(self):
        raw=row(method='Enhanced',status='INDETERMINATE');raw['metrics']=metrics(6);raw['candidate']=None;raw['frozen']=None
        sup=row(method='Enhanced',seconds='unavailable_split_flow');sup['metrics']=metrics(3);sup['metrics']['retained_builders_projection_not_additive_bill']=metrics(3)
        infra={'cell':[TASKS[0],'GPT61-Sol','Enhanced'],'metrics':metrics(4)}
        snap={'groups':[{'rows':[raw]}],'interface_supplements':[{'rows':[sup]}],'infrastructure_attempts':[infra]};before=copy.deepcopy(snap)
        result=build(snap);self.assertEqual(snap,before);self.assertEqual(result['unique_cells'],1)
        self.assertEqual(result['raw_rows'][0]['outcome'],'INDETERMINATE');self.assertEqual(result['reviewed_rows'][0]['reviewed_outcome'],'PASS')
        s=next(s for s in result['summary'] if s['name']=='Enhanced-GPT-6.1-Sol')
        self.assertEqual(s['all_attempt_openai']['input_tokens_recorded'],130)
        self.assertEqual(s['completed_cell_openai_projection']['input_tokens_recorded'],60)
        self.assertEqual(s['elapsed_measured_cells'],0);self.assertIsNone(s['io_adjusted_median_seconds'])
    def test_science_numeric_pass_never_becomes_full_pass_without_bound_independent_review(self):
        r=row(task='SCI-EGL');snap={'groups':[{'rows':[r]}]};result=build(snap)
        self.assertEqual(result['reviewed_rows'][0]['reviewed_outcome'],'PENDING_SCIENTIFIC_REVIEW')
        a={'cell':['SCI-EGL','GPT61-Sol','Direct'],'row_sha256':digest(r),'program_sha256':'1'*64,'independent_review':True,'status':'PASS','numerical':'PASS','source_method':'PASS','report':'PASS','figure':'PASS','evidence':['MOCK source, report and actual figure audit']}
        snap['science_adjudications']=[a];self.assertEqual(build(snap)['reviewed_rows'][0]['reviewed_outcome'],'PASS')
        a['program_sha256']='2'*64
        with self.assertRaisesRegex(ValueError,'another program'):build(snap)
        a['program_sha256']='1'*64;a['numerical']='NOT_REQUIRED';a['numerical_reason']='not a valid exclusion'
        with self.assertRaisesRegex(ValueError,'always requires'):build(snap)
        a['numerical']='PASS';a['figure']='NOT_REQUIRED'
        with self.assertRaisesRegex(ValueError,'contract evidence'):build(snap)
        a['status']='INDETERMINATE'
        with self.assertRaisesRegex(ValueError,'requires reason'):build(snap)
    def test_final_requires144_unique_cells_and36_audits(self):
        rows=[row(t,m,f) for t in TASKS for m in MODELS for f in METHODS];snap={'groups':[{'rows':rows}]}
        with self.assertRaisesRegex(ValueError,'144 unique'):build(snap,final=True)
        audits=[]
        for r in rows:
            if not r['task_id'].startswith('SCI-'):continue
            audits.append({'cell':[r['task_id'],r['model'],r['method']],'row_sha256':digest(r),'program_sha256':'1'*64,'independent_review':True,'status':'PASS','numerical':'PASS','source_method':'PASS','report':'PASS','figure':'PASS','evidence':['MOCK independent review']})
        snap['science_adjudications']=audits;result=build(snap,final=True)
        self.assertEqual(result['status'],'FINAL_REVIEWED_144');self.assertEqual(len(result['summary']),9)
        self.assertTrue(all(s['successes']==16 for s in result['summary']))
    def test_cache_is_subset_unknown_is_lower_bound_and_invalid_io_is_rejected(self):
        r=row();r['metrics']['deepseek'].update(requests=2,unknown_usage_requests=1)
        t=telemetry(r);self.assertTrue(t['deepseek']['lower_bound']);self.assertEqual(t['deepseek']['input_tokens_known'],10)
        self.assertEqual(t['openai']['input_tokens_recorded'],10);self.assertEqual(t['io_adjusted_estimate_seconds'],8)
        r['acceptance_io_adjustment']={'raw_elapsed_seconds':50}
        t=telemetry(r);self.assertEqual(t['hidden_acceptance_seconds'],50);self.assertEqual(t['active_phase_sum_seconds'],60)
        r['method_timing']['io_adjustment']['raw_elapsed_seconds']=11
        with self.assertRaisesRegex(ValueError,'I/O adjustment'):telemetry(r)
        r['method_timing']['elapsed_seconds']='unavailable_interrupted_method';self.assertIsNone(telemetry(r)['io_adjusted_estimate_seconds']);self.assertIsNone(telemetry(r)['active_phase_sum_seconds'])
        r['metrics']['openai']['cached_input_tokens_subset']=11
        with self.assertRaisesRegex(ValueError,'subset'):telemetry(r)
    def test_pairing_counts_role_timeouts_as_unsolved_but_excludes_infrastructure(self):
        rows=[]
        for t in TASKS[:3]:rows += [row(t,method='Enhanced'),row(t,method='Direct',status='TIMEOUT')]
        rows += [row(TASKS[3],method='Enhanced',seconds=5),row(TASKS[3],method='Direct',seconds=10)]
        result=build({'groups':[{'rows':rows}]});p=next(p for p in result['paired'] if p['model']=='GPT61-Sol' and p['left']=='Enhanced' and p['right']=='Direct')
        self.assertEqual(p['paired_tasks'],4);self.assertEqual(p['discordant_pairs'],3);self.assertEqual(p['exploratory_paired_sign_p'],.25)
        self.assertEqual(p['mutual_success_timing_pairs'],1);self.assertEqual(p['median_left_over_right_elapsed'],.5)
    def test_html_escapes_values_and_archive_never_includes_unrelated_files(self):
        r=row(status='<script>unsafe</script>');snap={'groups':[{'rows':[r]}]};result=build(snap)
        text=render(result);self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);(root/'unrelated.private').write_text('must not be zipped')
            artifact=write(result,root,snap)
            with zipfile.ZipFile(root/'report.zip')as z:self.assertNotIn('unrelated.private',z.namelist());self.assertIsNone(z.testzip())
            with (root/'summary.csv').open(encoding='utf-8-sig',newline='')as f:
                records=list(csv.DictReader(f));self.assertIn('openai_input_tokens_recorded',records[0]);self.assertEqual(len(records),9)

if __name__=='__main__':unittest.main()
