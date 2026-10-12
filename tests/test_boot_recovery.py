"""Restart decision, durable intent, corruption and cross-process ownership controls: no providers."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from p6_boot_recovery import Journal, atomic, contained, next_step, singleton, validate_sources, supervise, digest
import p6_recovery_probe_linux as probe
import p6_boot_recovery as recovery


class BackgroundConsoleControls(unittest.TestCase):
    def test_non_windows_keeps_native_process_behavior(self):
        with patch.object(recovery.sys, 'platform', 'linux'):
            self.assertEqual({}, recovery.background_process_options())

    def test_windows_child_is_explicitly_windowless(self):
        with patch.object(recovery.sys, 'platform', 'win32'), \
             patch.object(subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True):
            self.assertEqual({'creationflags': 0x08000000}, recovery.background_process_options())

    def test_poll_queries_receive_windowless_options(self):
        result = subprocess.CompletedProcess([], 0, stdout=b'{}')
        with patch.object(recovery, 'background_process_options', return_value={'creationflags': 0x08000000}), \
             patch.object(recovery.subprocess, 'run', return_value=result) as run:
            recovery.native({'project': str(SCRIPTS.parent)})
            self.assertEqual(0x08000000, run.call_args.kwargs['creationflags'])
            result.stdout = '{}'
            recovery.ps_json('fixture')
            self.assertEqual(0x08000000, run.call_args.kwargs['creationflags'])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows console handle control')
    def test_real_console_child_has_no_console_and_still_returns_output(self):
        command = [sys.executable, '-c',
                   'import ctypes; print(ctypes.windll.kernel32.GetConsoleWindow())']
        result = subprocess.run(command, capture_output=True, text=True, check=True,
                                **recovery.background_process_options())
        self.assertEqual('0', result.stdout.strip())


class BootRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.config = {'tasks': ['one', 'two'], 'modes': ['execute', 'sensitivity'], 'old_attempts': []}
        self.state = {'launches': []}
        self.inv = {'runs': [], 'active_main_runs': [], 'unowned_main_pids': []}

    def decide(self, *, boot=True, owner=False):
        return next_step(self.config, self.state, self.inv, original_alive=owner, boot_changed=boot)

    def completed(self, task='one', mode='execute', outcome='FAIL'):
        row = {'run_id': task + '-' + mode, 'task_id': task, 'mode': mode, 'alive': False,
               'status': 'MAIN_TASK_COMPLETED' if mode == 'execute' else 'FULL_TOOL_TRACE_SENSITIVITY_COMPLETED',
               'arms': {a: outcome for a in 'ABCDEF'}}
        if mode == 'sensitivity': row['source_run'] = task + '-execute'
        self.inv['runs'].append(row)

    def test_current_controller_untouched_even_with_execute_authorization(self):
        before = copy.deepcopy((self.config, self.state, self.inv))
        self.assertEqual('OBSERVE_ORIGINAL', self.decide(owner=True)['action'])
        self.assertEqual(before, (self.config, self.state, self.inv))

    def test_same_boot_exit_not_automatically_replayed(self):
        self.assertEqual('WAIT_FOR_REBOOT_OR_MANUAL_RECOVERY', self.decide(boot=False)['action'])

    def test_failed_model_arm_is_completed_task_and_not_retried(self):
        self.completed(); self.completed(mode='sensitivity')
        step = self.decide()
        self.assertEqual(('LAUNCH_UNSTARTED', 'two', 'execute'), (step['action'], step['task'], step['mode']))

    def test_completed_execute_restarts_only_not_started_sensitivity(self):
        self.completed()
        step = self.decide()
        self.assertEqual('sensitivity', step['mode']); self.assertEqual('one-execute', step['source_run'])

    def test_lost_controller_but_native_alive_is_adopted(self):
        self.inv['active_main_runs'] = ['active']; self.assertEqual('ADOPT_NATIVE', self.decide()['action'])

    def test_unowned_native_process_blocks_duplicate_spending(self):
        self.inv['unowned_main_pids'] = [123]; self.assertEqual('BLOCK_UNOWNED_NATIVE', self.decide()['action'])

    def test_power_loss_during_task_preserves_partial_and_continues_next(self):
        self.inv['runs'] = [{'task_id': 'one', 'mode': 'execute', 'run_id': 'partial', 'status': 'EXIT_WITHOUT_RECEIPT'}]
        step = self.decide()
        self.assertEqual('two', step['task']); self.assertEqual(2, len(step['pending']))

    def test_launch_index_gap_is_not_assumed_unstarted(self):
        self.config['old_attempts'] = [{'task_id': 'one', 'mode': 'execute', 'status': 'LAUNCHING'}]
        self.assertEqual('two', self.decide()['task'])

    def test_unassigned_native_launch_gap_blocks_all_new_launches(self):
        self.inv['runs'] = [{'run_id': 'unknown', 'status': 'LAUNCH_UNCERTAIN'}]
        self.assertEqual('BLOCK_LAUNCH_GAP', self.decide()['action'])

    def test_duplicate_completed_receipts_are_refused(self):
        self.completed(); self.completed(); self.assertEqual('BLOCK_DUPLICATE_COMPLETION', self.decide()['action'])

    def test_trace_receipt_cannot_reuse_different_program_pool(self):
        self.completed(); self.completed(mode='sensitivity'); self.inv['runs'][-1]['source_run'] = 'wrong'
        self.assertEqual('BLOCK_SENSITIVITY_SOURCE', self.decide()['action'])

    def test_all_completed_disables_new_model_work(self):
        for task in ('one', 'two'):
            for mode in ('execute', 'sensitivity'): self.completed(task, mode)
        self.assertEqual('ALL_COMPLETED', self.decide()['action'])
        self.assertEqual('ALL_COMPLETED', self.decide(boot=False)['action'])

    def test_pending_interruption_is_not_full_acceptance(self):
        for task in ('one', 'two'):
            self.state['launches'].append({'task': task, 'mode': 'execute', 'status': 'LAUNCH_INTENT'})
        self.assertEqual('FINISHED_WITH_PENDING_INTERRUPTED', self.decide()['action'])

    def test_durable_intent_survives_actual_process_exit_without_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'state.json'
            script = "import sys,os;sys.path.insert(0,sys.argv[1]);from p6_boot_recovery import atomic;atomic(sys.argv[2],{'launches':[{'task':'one','mode':'execute','status':'LAUNCH_INTENT'}]});os._exit(37)"
            result = subprocess.run([sys.executable, '-c', script, str(SCRIPTS), str(path)], capture_output=True)
            self.assertEqual(37, result.returncode)
            self.state = json.loads(path.read_bytes())
            self.assertEqual('two', self.decide()['task'])

    def test_journal_resume_keeps_history_and_rejects_corrupt_or_partial_tail(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'events'
            first = Journal(path); first.append('ARMED', {'count': 10})
            old = path.read_bytes(); second = Journal(path); second.append('RECOVER', {'count': 11})
            self.assertTrue(path.read_bytes().startswith(old)); self.assertEqual(2, Journal(path).sequence)
            with path.open('ab') as file: file.write(b'{"partial":')
            bad = path.read_bytes()
            with self.assertRaises(ValueError): Journal(path)
            self.assertEqual(bad, path.read_bytes())

    def test_hash_chain_detects_edit_to_previous_event(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'events'; Journal(path).append('ARMED', {'count': 10})
            path.write_bytes(path.read_bytes().replace(b'"count":10', b'"count":99'))
            with self.assertRaises(ValueError): Journal(path)

    def test_journal_intent_survives_crash_before_state_replacement(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'events'; Journal(path).append('LAUNCH_INTENT', {'id': 'owned', 'task': 'one', 'mode': 'execute'})
            self.state = {'launches': Journal(path).launch_intents()}
            self.assertEqual('two', self.decide()['task'])

    def test_real_cross_process_singleton_and_release_after_process_death(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'lock'
            script = "import sys;sys.path.insert(0,sys.argv[1]);from p6_boot_recovery import singleton;\nwith singleton(sys.argv[2]): print('owned')"
            with singleton(path):
                other = subprocess.run([sys.executable, '-c', script, str(SCRIPTS), str(path)], capture_output=True)
                self.assertNotEqual(0, other.returncode); self.assertNotIn(b'owned', other.stdout)
            other = subprocess.run([sys.executable, '-c', script, str(SCRIPTS), str(path)], capture_output=True)
            self.assertEqual(0, other.returncode)

    def test_state_paths_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError): contained(Path(td), '../outside')

    def test_simulated_boot_runs_real_fixture_processes_only_for_unstarted_phases(self):
        # A real subprocess dispatch with synthetic inventory, never a provider call.
        with tempfile.TemporaryDirectory() as td:
            project = Path(td); scripts = project / 'scripts'; scripts.mkdir()
            runner = scripts / 'run_p6_main.py'
            runner.write_text("import sys,json;from pathlib import Path\np=Path('dispatches');p.open('a').write(sys.argv[1]+' '+sys.argv[3]+'\\n');print(json.dumps({'run_id':'fixture-'+sys.argv[1]}))\n")
            folder = project / '.local-workbench/recovery/fixture'; folder.mkdir(parents=True)
            original = project / 'batch.json'; original.write_text(json.dumps({'manifest_sha256': 'a'*64, 'attempts': []}))
            config = dict(self.config, project=str(project), authorization='HUMAN_APPROVED_LOCAL_BOOT_RECOVERY_20261012',
                          batch_index='batch.json', manifest_file='manifest.json', manifest_sha256='a'*64,
                          original_owner={'ProcessId': 999, 'CreationDate': '2026-01-01T00:00:00Z', 'CommandLine': 'old', 'ExecutablePath': sys.executable},
                          native_boot_id='boot-two', windows_boot='boot-one', python=sys.executable, ledger_floor={}, poll_seconds=0,
                          supervisor_files={name: digest((SCRIPTS/name).read_bytes()) for name in ('p6_boot_recovery.py','p6_recovery_probe_linux.py')})
            atomic(folder/'config.private.json', config); atomic(folder/'enabled.private.json', {'enabled': True})
            self.completed(); self.completed(mode='sensitivity')
            first = copy.deepcopy(self.inv); self.completed('two'); second = copy.deepcopy(self.inv)
            self.completed('two', 'sensitivity'); third = copy.deepcopy(self.inv)
            for inv in (first, second, third): inv.update(native_boot_id='boot-two', ledger={'floor': {}, 'requests': 7, 'cash_bound_nano': 15})
            from unittest.mock import patch
            with patch('p6_boot_recovery.validate_sources', return_value={'deepseek_inference_requests': 10000, 'api_cash_usd': 100}), \
                 patch('p6_boot_recovery.host_identity', return_value={'boot': 'boot-two'}), \
                 patch('p6_boot_recovery.windows_controllers', return_value=[]), \
                 patch('p6_boot_recovery.native', side_effect=[first, second, third]), \
                 patch('p6_boot_recovery.subprocess.check_output', return_value=b''), patch('p6_boot_recovery.time.sleep'):
                supervise(folder/'config.private.json', execute=True)
            self.assertEqual(['execute two', 'sensitivity two'], (project/'dispatches').read_text().splitlines())
            journal = Journal(folder/'events.private.ndjson')
            self.assertEqual(2, len(journal.launch_intents())); self.assertEqual('ALL_COMPLETED', json.loads((folder/'state.private.json').read_bytes())['status'])


class NativeInventoryControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.base = self.root / 'private'; (self.base / 'main-launches').mkdir(parents=True)
        self.proc = self.root / 'proc'; (self.proc / 'sys/kernel/random').mkdir(parents=True)
        (self.proc / 'sys/kernel/random/boot_id').write_text('boot-one')
        self.ledger = self.root / 'ledger.json'
        self.auth = probe.sha(json.dumps({}, sort_keys=True, separators=(',', ':')).encode())
        self.value = {'phase': 'P6_MAIN_LOCAL_20261011', 'authorization_sha256': self.auth,
                      'requests': [{'index': 1, 'experiment': 'old-role', 'observed_at': 'first', 'charge_bound_nano': 600}],
                      'codex_turns': [{'experiment': 'old-subscription', 'model': 'gpt-6.1-sol', 'observed_at': 'first'}], 'cash_bound_nano': 600}
        self.ledger.write_text(json.dumps(self.value))
        self.config = {'native_boot_id': 'boot-one', 'batch_started_unix': 1, 'authorization_sha256': self.auth,
                       'manifest_sha256': 'a'*64, 'runner_source_sha256': {}, 'entrypoint_sha256': 'e'*64}
        self.patches = [patch.object(probe, 'BASE', self.base), patch.object(probe, 'LEDGER', self.ledger), patch.object(probe, 'PROC', self.proc)]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def add_run(self, *, completed=True, pid=123):
        name = 'p6-main-execute-one-20261012T125459Z'
        (self.base / 'main-launches' / (name+'.json')).write_text(json.dumps({'run_id': name, 'pid': pid, 'process_start_ticks': '99', 'started_unix': 2}))
        root = self.base / 'main-runs' / name; (root / 'control').mkdir(parents=True)
        (root / 'control/run-contract.json').write_text(json.dumps({'task': {'task_id': 'one'}, 'mode': 'execute', 'budget': {}, 'source_sha256': {}, 'entrypoint_sha256': 'e'*64, 'manifest': {'manifest_sha256': 'a'*64}}))
        if completed:
            (root / 'receipt.json').write_text(json.dumps({'status': 'MAIN_TASK_COMPLETED', 'task_id': 'one', 'run_id': name}))
            for arm in 'ABCDEF': (root / ('arm-'+arm+'.json')).write_text(json.dumps({'arm': arm, 'outcome': 'FAIL'}))
        return root

    def process(self, pid, parent, command, ticks='99'):
        p = self.proc / str(pid); p.mkdir()
        fields = ['S', str(parent)] + ['0']*17 + [ticks]
        (p / 'stat').write_text(str(pid)+' (python) '+' '.join(fields))
        (p / 'cmdline').write_bytes(command)

    def test_budget_prefix_can_settle_but_cannot_reset_or_rewrite_identity(self):
        first = probe.inventory(self.config); self.config['ledger_floor'] = first['ledger']['floor']
        self.value['requests'][0]['charge_bound_nano'] = 300; self.value['cash_bound_nano'] = 300
        self.ledger.write_text(json.dumps(self.value)); self.assertEqual(300, probe.inventory(self.config)['ledger']['cash_bound_nano'])
        self.value['requests'][0]['experiment'] = 'rewritten'; self.ledger.write_text(json.dumps(self.value))
        with self.assertRaises(ValueError): probe.inventory(self.config)

    def test_corrupt_cash_sum_is_not_auto_repaired_or_refunded(self):
        self.value['cash_bound_nano'] = 0; self.ledger.write_text(json.dumps(self.value))
        before = self.ledger.read_bytes()
        with self.assertRaises(ValueError): probe.inventory(self.config)
        self.assertEqual(before, self.ledger.read_bytes())

    def test_completed_receipt_missing_one_arm_is_not_accepted(self):
        root = self.add_run(); (root/'arm-F.json').unlink()
        with self.assertRaises(ValueError): probe.inventory(self.config)

    def test_native_timeout_parent_and_runtime_child_are_one_owned_controller(self):
        self.add_run(completed=False)
        cmd = b'/usr/bin/timeout\0/opt/workbench/source/p6_main_runtime_linux.py\0'
        self.process(123, 1, cmd); self.process(124, 123, b'python\0/opt/workbench/source/p6_main_runtime_linux.py\0')
        inventory = probe.inventory(self.config)
        self.assertEqual(1, len(inventory['active_main_runs'])); self.assertEqual([], inventory['unowned_main_pids'])

    def test_pid_reuse_across_boot_is_not_alive(self):
        self.add_run(completed=False); self.process(123, 1, b'timeout\0/opt/workbench/source/p6_main_runtime_linux.py\0')
        self.config['native_boot_id'] = 'previous-boot'
        self.assertEqual([], probe.inventory(self.config)['active_main_runs'])

    def test_launch_without_contract_blocks_instead_of_assuming_unstarted(self):
        root = self.add_run(completed=False); (root/'control/run-contract.json').unlink()
        self.assertEqual('LAUNCH_UNCERTAIN', probe.inventory(self.config)['runs'][0]['status'])


if __name__ == '__main__': unittest.main()
