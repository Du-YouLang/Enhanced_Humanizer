"""Real schema adversaries, not benchmark model evidence."""
import copy
import json
import statistics
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from p6_science_contracts import egl_manifest,egl_summary,pc_manifest,source_identity,pc_within_tolerance


class ScienceContractTests(unittest.TestCase):
    def test_pc_exact_decimal_boundary_passes_but_any_real_excess_fails(self):
        self.assertGreater(100*abs(.7025-.7),.25)
        self.assertTrue(pc_within_tolerance(.7025,.7,.1,.08))
        self.assertFalse(pc_within_tolerance(.7025001,.7,.1,.08))
        self.assertFalse(pc_within_tolerance(.7025,.7,.1000001,.08))
        for bad in (float('nan'),float('inf'),True,None):
            self.assertFalse(pc_within_tolerance(bad,.7,.1,.08))

    def test_pc_measured_python_version_alias_preserves_other_gates_and_rejects_conflicts(self):
        temp=ROOT/'.local-workbench/test-temp';temp.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp) as folder:
            source=Path(folder);(source/'run_benchmark.py').write_text('pass\n')
            raw={'python_version':'3.11.16','packages':{'jax':'0.10.1'},'data_sha256':{'data.gz':'b'*64},
                 'gate_elapsed_seconds':{'smoke':1.,'anchor':2.,'grid':3.}}
            result=pc_manifest(raw,source)
            self.assertEqual(result['python'],'3.11.16')
            self.assertEqual(result['packages'],raw['packages']);self.assertEqual(result['data_sha256'],raw['data_sha256'])
            self.assertEqual(result['gate_elapsed_seconds'],raw['gate_elapsed_seconds'])
            self.assertEqual(pc_manifest(raw|{'python':{'version':'3.11.16'}},source),result)
            for bad in (raw|{'python':'3.12'},raw|{'environment':{'python_version':'3.12'}},
                        raw|{'python_version':None},raw|{'packages':{}},raw|{'data_sha256':{'data.gz':'invalid'}}):
                with self.assertRaises(ValueError):pc_manifest(bad,source)

    def test_explicit_egl_aliases_and_memory_units(self):
        raw={'file_sha256':{'candidate.py':'a'*64},'python_version':'3.10','num_threads':8,'dtype':'float32',
             'seeds':[1,2,3],'peak_rss_bytes':2048,'torch_version':'2.5.1'}
        result=egl_manifest(raw)
        self.assertEqual(result['peak_rss_kib'],2)
        self.assertEqual(result['files_sha256'],raw['file_sha256'])
        with self.assertRaises(ValueError):egl_manifest(raw|{'peak_rss_kib':3})
        with self.assertRaises(ValueError):egl_manifest(raw|{'threads':1})
        with self.assertRaises(ValueError):egl_manifest(raw|{'peak_rss_bytes':float('nan')})
        legacy={k:v for k,v in raw.items() if k!='peak_rss_bytes'}|{'peak_memory_mb':2.}
        with self.assertRaises(ValueError):egl_manifest(legacy)
        self.assertEqual(egl_manifest(legacy,reviewed_units={'peak_memory_mb':'MiB'})['peak_rss_kib'],2048)

    def test_paired_summary_equivalence_does_not_accept_wrong_seed_order_or_nan(self):
        groups=[{'n':n,'algorithm':a,'mean_test_accuracy_pct':10.,'std_test_accuracy_pct':0.} for n in (200,2000,20000) for a in ('eg','gd')]
        metrics={(n,s,a):{'curves':[{'test_accuracy_pct':10.}]} for n in (200,2000,20000) for s in (1,2,3) for a in ('eg','gd')}
        pairs=[{'n':n,'per_seed_eg_minus_gd_pp':[0.,0.,0.],'mean_eg_minus_gd_pp':0.,'std_eg_minus_gd_pp':0.} for n in (200,2000,20000)]
        raw={'groups':groups,'paired_differences':pairs};gains={str(n):0. for n in (200,2000,20000)}
        egl_summary(raw,groups,gains,metrics)
        for key,value in [('mean_eg_minus_gd_pp',float('nan')),('per_seed_eg_minus_gd_pp',[0.,0.,1.])]:
            bad=copy.deepcopy(raw);bad['paired_differences'][0][key]=value
            with self.assertRaises(ValueError):egl_summary(bad,groups,gains,metrics)
        with self.assertRaises(ValueError):egl_summary(raw|{'eg_minus_gd_mean_pp':{'200':1.}},groups,gains,metrics)

    def test_pc_parent_attests_source_without_fabricating_git_or_driver(self):
        temp=ROOT/'.local-workbench/test-temp';temp.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp) as folder:
            source=Path(folder);(source/'run_benchmark.py').write_text('pass\n')
            raw={'environment':{'python':'3.11','packages':{'jax':'0.10'}},'data_files':{'data.gz':{'sha256':'b'*64}},
                 'stages':{n:{'wall_seconds':1.} for n in ('smoke','anchor','grid')},'workspace_commit':{'returncode':128}}
            result=pc_manifest(raw,source)
            self.assertNotIn('git_commit',result)
            self.assertEqual(result['driver_measurement'],'unavailable')
            old=result['source_provenance']['tree_sha256'];(source/'run_benchmark.py').write_text('changed\n')
            self.assertNotEqual(source_identity(source)['tree_sha256'],old)
            for bad in (raw|{'data_files':{'data.gz':'unknown'}},raw|{'data_sha256':{'data.gz':'c'*64}},
                        raw|{'stages':{'smoke':{'wall_seconds':0},'anchor':{'wall_seconds':1},'grid':{'wall_seconds':1}}}):
                with self.assertRaises(ValueError):pc_manifest(bad,source)

    def test_egl_short_paired_fields_recompute_each_seed_and_do_not_mutate_input(self):
        values={'eg':(3.,4.,7.),'gd':(5.,1.,3.)};diff=[-2.,3.,4.]
        groups=[{'n':n,'algorithm':a,'mean_test_accuracy_pct':statistics.mean(values[a]),
                 'std_test_accuracy_pct':statistics.stdev(values[a])} for n in (200,2000,20000) for a in values]
        metrics={(n,s,a):{'curves':[{'test_accuracy_pct':values[a][s-1]}]}
                 for n in (200,2000,20000) for s in (1,2,3) for a in values}
        pairs=[{'n':n,'values':diff[:],'mean':statistics.mean(diff),'std':statistics.stdev(diff)} for n in (200,2000,20000)]
        raw={'groups':groups,'paired_differences':pairs,
             'eg_minus_gd_mean_pp':{str(n):statistics.mean(diff) for n in (200,2000,20000)}}
        original=copy.deepcopy(raw)
        egl_summary(raw,groups,raw['eg_minus_gd_mean_pp'],metrics)
        self.assertEqual(raw,original)
        # Seed reversal and population std cannot hide behind a correct mean.
        for field,value in [('values',list(reversed(diff))),('std',statistics.pstdev(diff)),
                            ('values',[True,3.,4.]),('values',[-2.,3.,float('nan')]),
                            ('std',-1.),('mean',float('inf')),('values',[-2.,3.])]:
            bad=copy.deepcopy(raw);bad['paired_differences'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                egl_summary(bad,groups,raw['eg_minus_gd_mean_pp'],metrics)
        bad=copy.deepcopy(raw);del bad['paired_differences'][0]['std']
        with self.assertRaises(ValueError):egl_summary(bad,groups,raw['eg_minus_gd_mean_pp'],metrics)

    def test_egl_paired_aliases_reject_conflicts_and_invalid_duplicate_declarations(self):
        groups=[{'n':n,'algorithm':a,'mean_test_accuracy_pct':10.,'std_test_accuracy_pct':0.}
                for n in (200,2000,20000) for a in ('eg','gd')]
        metrics={(n,s,a):{'curves':[{'test_accuracy_pct':10.}]}
                 for n in (200,2000,20000) for s in (1,2,3) for a in ('eg','gd')}
        pairs=[{'n':n,'values':[0.,0.,0.],'mean':0.,'std':0.,
                'per_seed_eg_minus_gd_pp':[0.,0.,0.],'mean_eg_minus_gd_pp':0.,'std_eg_minus_gd_pp':0.}
               for n in (200,2000,20000)]
        raw={'groups':groups,'paired_differences':pairs};gains={str(n):0. for n in (200,2000,20000)}
        egl_summary(raw,groups,gains,metrics)
        for field,value in [('values',[0.,0.,1.]),('mean',1.),('std',1.),
                            ('values',[False,0.,0.]),('mean',False),('std',False)]:
            bad=copy.deepcopy(raw);bad['paired_differences'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                egl_summary(bad,groups,gains,metrics)


if __name__=='__main__':unittest.main()
