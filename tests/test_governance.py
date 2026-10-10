"""Safety policy regression checks, with no network or model calls."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_environment import sanitize
from check_push import validate
from check_repository import private_path, traceability_errors, baseline_errors
from generate_traceability import restore_progress


class GovernanceTests(unittest.TestCase):
    def test_regeneration_keeps_acceptance_and_cannot_rewrite_contract(self):
        rows=[{'id':'WF-01','requirement':'baseline','tags':['C'],'implementation_status':'PLANNED'}]
        restore_progress(rows, {'WF-01':{'requirement':'tampered','tags':['F'],'implementation_status':'VERIFIED','phase_evidence':{'P0':'real evidence'}}})
        self.assertEqual(rows[0]['requirement'],'baseline')
        self.assertEqual(rows[0]['tags'],['C'])
        self.assertEqual(rows[0]['implementation_status'],'VERIFIED')
        self.assertEqual(rows[0]['phase_evidence'],{'P0':'real evidence'})

    def test_private_material_cannot_be_tracked(self):
        for name in [".local-workbench/run.json", ".venv/pyvenv.cfg", ".venv-probe/token.txt", "docs/.env.production", "data/patient.csv", "cache/runtime.vhdx", "auth.json", "backup.credentials.yaml", "trace.jsonl"]:
            with self.subTest(name=name):
                self.assertTrue(private_path(name))

    def test_reviewable_project_files_are_allowed(self):
        for name in [".env.example", "docs/upstreams.md", "configs/requirements-p0-windows.lock", "src/workbench/adapters/dsh.py"]:
            with self.subTest(name=name):
                self.assertFalse(private_path(name))

    def test_tokens_are_redacted_before_audit_persistence(self):
        secret = "sk-" + "abcDEF0123456789" * 3
        self.assertNotIn(secret, sanitize("Authorization: " + secret))
        self.assertNotIn("sensitive", sanitize("  Token: sensitive"))

    def test_original_contract_hashes_and_full_id_coverage(self):
        self.assertEqual([], baseline_errors())
        self.assertEqual([], traceability_errors())

    def test_no_push_without_specific_human_authorization(self):
        self.assertTrue(validate("https://github.com/Du-YouLang/Enhanced_Humanizer.git", [], None))

    def test_main_deletion_wrong_remote_and_unknown_refs_are_denied(self):
        approval = {"approved_by": "human_user", "authorization_reference": "test fixture", "owner": "Du-YouLang", "repository": "Enhanced_Humanizer", "allowed_ref_prefixes": ["refs/heads/feature/"]}
        remote = "https://github.com/Du-YouLang/Enhanced_Humanizer.git"
        sha, zero = "a" * 40, "0" * 40
        self.assertTrue(validate(remote, [["refs/heads/main", sha, "refs/heads/main", zero]], approval))
        self.assertTrue(validate(remote, [["(delete)", zero, "refs/heads/feature/x", sha]], approval))
        self.assertTrue(validate("https://github.com/someone/other.git", [], approval))
        self.assertTrue(validate(remote, [["refs/heads/release", sha, "refs/heads/release", zero]], approval))
        self.assertEqual([], validate(remote, [["refs/heads/feature/x", sha, "refs/heads/feature/x", zero]], approval))


if __name__ == "__main__":
    unittest.main()
