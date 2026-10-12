"""Acceptance cases for immutable original tests and separate new regressions."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_gate_policy import GENERATION_RULES, protected_changes


class PublicGatePolicyTests(unittest.TestCase):
    def test_new_test_file_allowed_but_existing_append_or_delete_protected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base/'test_requests.py').write_text('original test bytes')
            self.assertEqual(protected_changes(['test_requests.py', 'test_regression.py'], base), ['test_requests.py'])
            self.assertIn('Do not append tests to an existing file', GENERATION_RULES)
            self.assertIn('NEW file', GENERATION_RULES)

    def test_nested_original_tests_and_fixtures_are_protected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            names = ['sympy/core/tests/test_basic.py', 'pkg/conftest.py', 'pkg/value_test.py', 'pkg/testing/data.txt']
            for name in names:
                path = base/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('original')
            self.assertEqual(protected_changes(names+['pkg/implementation.py'], base), names)

    def test_dependency_and_owner_protection_do_not_block_new_regressions(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); (base/'pyproject.toml').write_text('original')
            self.assertEqual(protected_changes(['pyproject.toml', 'trainer.py', 'tests/new.py'], base, ['trainer.py']), ['pyproject.toml', 'trainer.py'])
