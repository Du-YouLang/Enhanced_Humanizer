"""Meaningful P6 checks: immutable identities, fair environments, and missing data accounting."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from workbench.benchmark import (ARMS, REQUIRED_METRICS, check_manifest, digest,
                                 freeze_manifest, plan, same_pool, summarize, validate_result)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_evaluate_linux import validate_source_links, task_path


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((Path(__file__).resolve().parents[1]/'configs/benchmark-p6-v2.json').read_text())

    def test_latest_entrypoint_bytes_match_frozen_protocol_and_packaged_lf(self):
        root=Path(__file__).resolve().parents[1]
        latest=json.loads((root/'configs/benchmark-p6-v10-final.json').read_text())
        check_manifest(latest);entry=(root/'scripts/run_p6_main.py').read_bytes()
        self.assertNotIn(b'\r\n',entry)
        self.assertEqual(hashlib.sha256(entry).hexdigest(),latest['entrypoint_sha256'])

    def test_closed_smoke_refuses_paid_reentry_before_wsl_or_credential_access(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'configs/budget-p6-smoke-approved.json').read_text())
        self.assertFalse(config['model_execution_enabled'])
        p=subprocess.run([sys.executable,'-B',str(root/'scripts/run_p6_smoke.py'),'execute','--task','BIP-black-2'],
                         cwd=root,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('P6 paid entry is closed',p.stderr)

    def test_immutable_task_material_and_original_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'manifest.json'
            raw = check_manifest(self.manifest)
            first = freeze_manifest(raw, path)
            self.assertEqual(freeze_manifest(raw, path), first)
            changed = copy.deepcopy(raw)
            changed['tasks'][0]['base_commit'] = 'a'*40
            with self.assertRaises(ValueError): freeze_manifest(changed, path)
            first['tasks'].pop()
            with self.assertRaises(ValueError): check_manifest(first)

    def test_unrun_tasks_are_not_zero_success_or_zero_cost(self):
        rows = plan(self.manifest)
        self.assertEqual(len(rows), 96)
        summary = summarize(rows)
        for arm in ARMS:
            self.assertEqual(summary['arms'][arm]['completion_rate'], 'unavailable')
            self.assertEqual(summary['arms'][arm]['metrics']['api_cash_usd']['total'], 'unavailable')
            self.assertEqual(summary['arms'][arm]['outcomes'], {'NOT_RUN': 16})
        self.assertNotIn('patch', json.dumps(self.manifest))
        self.assertEqual(sum(task['preparation_status'] == 'NOT_RUN_MISSING_MATERIAL' for task in self.manifest['tasks']), 4)

    def test_science_ready_requires_real_material_identities(self):
        raw=check_manifest(self.manifest)
        task=next(t for t in raw['tasks'] if t['family']=='scientific')
        task.update(preparation_status='READY',paper='unspecified paper',data_sha256='fake',gold_sha256='fake',
                    license='unspecified',tolerances={'atol':.01},invariants=['check'])
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            freeze_manifest(raw,Path(directory)/'bad-science.json')

    def real_row(self):
        row = plan(self.manifest)[0]
        preparation = dict(status='READY', task_id=row['task_id'], env_sha256='a'*64,
                           hardware_sha256='b'*64, permissions_sha256='c'*64,
                           base_commit=self.manifest['tasks'][0]['base_commit'], hidden_suite_sha256='d'*64)
        row.update({key: preparation[key] for key in ('env_sha256', 'hardware_sha256', 'permissions_sha256', 'base_commit', 'hidden_suite_sha256')})
        row.update(outcome='PASS', evidence_kind='REAL_MODEL', time_cap_seconds=1200,
                   evidence_sha256='e'*64, run_contract_sha256='f'*64,
                   independent_acceptance='PASS', head_commit='a'*40,
                   metrics={key: 'unavailable' for key in REQUIRED_METRICS})
        row['metrics'].update(end_to_end_seconds=20, api_upper_bound_usd=.01, subscription_turns=0)
        return row, preparation

    def test_mock_score_changed_hardware_or_time_cannot_pass(self):
        row, preparation = self.real_row()
        validate_result(row, self.manifest, preparation)
        for key, bad in [('evidence_kind', 'MOCK'), ('hardware_sha256', 'f'*64),
                         ('independent_acceptance', 'FAIL'), ('time_cap_seconds', 1300),
                         ('model_identity', 'some-other-model')]:
            changed = copy.deepcopy(row); changed[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_result(changed, self.manifest, preparation)
        changed = copy.deepcopy(row); changed['metrics']['input_tokens'] = True
        with self.assertRaises(ValueError): validate_result(changed, self.manifest, preparation)

    def test_failed_unknown_measurements_retained_and_no_seed_selection(self):
        row, _ = self.real_row()
        failed = copy.deepcopy(row); failed.update(task_id=self.manifest['tasks'][1]['task_id'], outcome='INFRA_FAIL')
        failed['metrics']['end_to_end_seconds'] = 'unavailable'
        result = summarize([row, failed])['arms']['A']
        self.assertEqual(result['attempted'], 2)
        self.assertEqual(result['completion_rate'], .5)
        self.assertEqual(result['metrics']['end_to_end_seconds']['known_sum'], 20)
        self.assertEqual(result['metrics']['end_to_end_seconds']['total'], 'unavailable')
        self.assertEqual(result['api_cash_per_success'], 'unavailable')
        with self.assertRaises(ValueError): summarize([row, row])

    def test_new_family_limits_bind_each_task_and_every_arm_without_changing_old_manifest(self):
        original=copy.deepcopy(self.manifest);raw=copy.deepcopy(check_manifest(self.manifest))
        raw.update(protocol_version=10,candidate_time_cap_seconds=1200,task_time_cap_seconds=10800,
                   role_timeout_seconds_by_family={'public':900,'scientific':1200},
                   experiment_timeout_seconds_by_family={'public':7200,'scientific':10800})
        for task in raw['tasks']:
            family='scientific' if task['family']=='scientific' else 'public'
            task.update(role_time_cap_seconds=raw['role_timeout_seconds_by_family'][family],
                        model_activity_time_cap_seconds=raw['experiment_timeout_seconds_by_family'][family])
        temporary_root=Path(__file__).resolve().parents[1]/'.local-workbench/test-tmp'
        temporary_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as folder:
            new=freeze_manifest(raw,Path(folder)/'new.json');row,preparation=self.real_row()
            row.update(manifest_sha256=new['manifest_sha256'],time_cap_seconds=7200)
            validate_result(row,new,preparation)
            row['time_cap_seconds']=10800
            with self.assertRaises(ValueError):validate_result(row,new,preparation)
            for field,bad in [('role_time_cap_seconds',901),('role_time_cap_seconds',900.0),('model_activity_time_cap_seconds',1200)]:
                changed=copy.deepcopy(raw);changed['tasks'][0][field]=bad
                with self.assertRaises(ValueError):freeze_manifest(changed,Path(folder)/('bad-'+field+'.json'))
        self.assertEqual(self.manifest,original)

    def test_judge_and_merge_comparisons_bind_the_same_public_pool(self):
        one = dict(pool_sha256='a'*64, rubric_sha256='b'*64, public_evidence_sha256='c'*64)
        two = copy.deepcopy(one)
        self.assertTrue(same_pool([one, two]))
        two['public_evidence_sha256'] = digest({'leaked_hidden_answer': 'anything'})
        with self.assertRaises(ValueError): same_pool([one, two])

    def test_hidden_paths_and_source_links_do_not_escape(self):
        for name in ('../answer.py', '/private/answer.py', 'tests/../../answer.py', '.git/config'):
            with self.subTest(name=name), self.assertRaises(ValueError): task_path(name)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';root.mkdir();(root/'actual').write_text('fixture')
            try:(root/'internal').symlink_to('actual')
            except OSError:self.skipTest('Platform does not permit test symlinks')
            (root/'generated-doc').symlink_to('missing-generated-file')
            validate_source_links(root)
            (root/'outside').symlink_to('../outside-file')
            with self.assertRaises(ValueError):validate_source_links(root)

    def test_p6_approved_caps_and_phase_separation_are_enforced(self):
        from p1_budget import Ledger, BudgetDenied
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.json'
            ledger=Ledger(path, phase='P6', requests=999, cash_nano=99_000_000_000, codex_turns=999)
            self.assertEqual((ledger.requests,ledger.cash_nano,ledger.codex_turns),(200,5_000_000_000,32))
            ledger.reserve_codex_turn('smoke','gpt-6.1-sol')
            with self.assertRaises(BudgetDenied):Ledger(path,phase='P5').reserve_codex_turn('other','gpt-6.1-sol')
            limited=Ledger(path,phase='P6',codex_turns=1)
            with self.assertRaises(BudgetDenied):limited.reserve_codex_turn('smoke','gpt-6.1-sol')
            self.assertEqual(len(json.loads(path.read_text())['codex_turns']),1)
            with self.assertRaises(BudgetDenied):Ledger(Path(directory)/'p7.json',phase='P7')

    def test_public_handoff_excludes_hidden_answers_and_private_state(self):
        import p6_runtime_linux as runtime
        task={'prompt':'public task','base_commit':'a'*40,'seal':{'env_sha256':'b'*64}}
        old=dict(runtime.ACTIVE)
        self.addCleanup(lambda:(runtime.ACTIVE.clear(),runtime.ACTIVE.update(old)))
        runtime.ACTIVE['task']=task
        rows=[dict(id=cid,base_commit='a'*40,env_hash='b'*64,prompt_hash=runtime.digest(b'public task'),
                   verdict='FAIL',patch='public patch',source='public source',test_report={'log':'visible failure'},
                   hidden_acceptance={'gold_answer':'withheld','verdict':'PASS'},root='/private/controller',
                   partial_patch='withheld private snapshot') for cid in ('A','B','C')]
        pool=runtime.public_pool(rows)
        raw=json.dumps(pool)
        self.assertNotIn('withheld',raw)
        self.assertNotIn('/private/controller',raw)
        self.assertEqual(len(pool['candidates']),3)


if __name__ == '__main__':
    unittest.main()
