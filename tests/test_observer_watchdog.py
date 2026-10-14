import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import p6_observer_watchdog as watchdog


class ObserverWatchdogTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / '.local-workbench'
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.folder = self.project / '.local-workbench/recovery/observer'
        self.folder.mkdir(parents=True)
        interpreter = self.project / 'existing-runtime/python.exe'
        interpreter.parent.mkdir()
        interpreter.with_name('pythonw.exe').write_bytes(b'not executed')
        (self.folder / 'observe.py').write_text('read-only fixture')
        self.inspector = self.folder / 'inspect.py'
        self.inspector.write_text('inspection fixture')
        self.observer = {'project': str(self.project), 'python': str(interpreter),
            'inspector': str(self.inspector), 'mode': 'READ_ONLY_NO_DISPATCH',
            'interval_seconds': 30, 'no_models': True, 'no_ledger_edits': True,
            'no_candidate_replay': True, 'observer_sha256': watchdog.sha(self.folder / 'observe.py'),
            'inspector_sha256': watchdog.sha(self.inspector)}
        self.source = self.folder / 'config.private.json'
        self.source.write_text(json.dumps(self.observer))
        self.path = self.folder / 'watchdog.private.json'
        self.value = {'project': str(self.project), 'watchdog_sha256': watchdog.sha(watchdog.__file__),
            'observer_config': str(self.source), 'observer_config_sha256': watchdog.sha(self.source)}
        self.path.write_text(json.dumps(self.value))
        (self.folder / 'enabled.private.json').write_text('{"enabled":true}')

    def test_preflight_does_not_launch(self):
        with patch.object(watchdog.subprocess, 'Popen', side_effect=AssertionError('No dispatch')):
            self.assertEqual(watchdog.run(self.path, True)['status'], 'PREFLIGHT_PASS')

    def test_human_disable_is_honored_without_restart(self):
        (self.folder / 'enabled.private.json').write_text('{"enabled":false}')
        with patch.object(watchdog.subprocess, 'Popen', side_effect=AssertionError('No dispatch')):
            self.assertEqual(watchdog.run(self.path)['status'], 'DISABLED_BY_OWNER')

    def test_changed_inspector_is_rejected_before_launch(self):
        self.inspector.write_text('changed')
        with patch.object(watchdog.subprocess, 'Popen', side_effect=AssertionError('No dispatch')):
            with self.assertRaisesRegex(ValueError, 'Pinned observer or inspector changed'):
                watchdog.run(self.path)

    def test_dispatch_configuration_and_changed_config_are_rejected(self):
        self.observer['mode'] = 'DISPATCH'
        self.source.write_text(json.dumps(self.observer))
        with self.assertRaisesRegex(ValueError, 'Observer configuration changed'):
            watchdog.run(self.path)
        self.value['observer_config_sha256'] = watchdog.sha(self.source)
        self.path.write_text(json.dumps(self.value))
        with self.assertRaisesRegex(ValueError, 'read-only observer'):
            watchdog.run(self.path)


if __name__ == '__main__':
    unittest.main()
