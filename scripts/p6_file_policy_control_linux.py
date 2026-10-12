"""Zero-model real Git/public/private controls for the public file policy.

Uses authorized public reference code only. It cannot launch a model or read
credentials and must write a fresh control directory. Old receipts are preserved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import p6_main_runtime_linux as main
import p6_runtime_linux as shared
from p2_candidates import exclusive_json


def check(root):
    if os.getuid() == 0 or not root.resolve().is_relative_to(shared.BASE/'private'):
        raise ValueError('Non-root project-private control directory required')
    root.mkdir()
    ledger = Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
    before = hashlib.sha256(ledger.read_bytes()).hexdigest()
    index = json.loads((shared.BASE/'science/private/public-main-controls-frozen-v2.json').read_text())
    entry = next(e for e in index['tasks'] if e['task_id'] == 'SWEL-psf__requests-1963')
    receipt = json.loads(Path(entry['receipt']).read_text())
    task = main.public_task({'task': {'task_id': receipt['task_id'], 'base_commit': receipt['base_commit']}})
    shared.ACTIVE.clear()
    shared.ACTIVE.update(root=root, task=task, deadline=time.monotonic()+600, main_phase=True, defer_hidden=True)
    shared.test_source = main.public_test
    gold = Path(receipt['gold'])
    results = {}
    with task['fixture_context'] as url:
        shared.ACTIVE['fixture_url'] = url
        for name in ('original-preserved', 'new-regression-file', 'existing-test-appended', 'unchanged-baseline'):
            role = root/name; role.mkdir(); work = role/'code'; (role/'home').mkdir()
            shared.clone(task['base'], work, 'control/'+name, trusted=True)
            if name != 'unchanged-baseline':
                (work/'requests/sessions.py').write_bytes((gold/'requests/sessions.py').read_bytes())
                extra = []
                if name == 'new-regression-file':
                    (work/'test_control_new.py').write_text('def test_additional_control():\n    assert True\n')
                    extra = ['test_control_new.py']
                if name == 'existing-test-appended':
                    with (work/'test_requests.py').open('ab') as f:
                        f.write(b'\n# append-only zero-model control\n')
                    extra = ['test_requests.py']
                shared.trusted_git(work, 'add', 'requests/sessions.py', *extra)
                shared.trusted_git(work, 'commit', '-m', 'Controlled source and file policy case')
            value = shared.candidate(name, {'work': str(work), 'status': 'COMPLETED',
                'scope': 'ZERO_MODEL_FILE_POLICY_CONTROL/'+name, 'wall_seconds': 0})
            private = main.public_test(work, True) if value['verdict'] == 'PASS' else None
            results[name] = {'public_verdict': value['test_report']['verdict'], 'candidate_verdict': value['verdict'],
                'protected_paths': value['protected_paths_modified'], 'known_failures': value['known_failures'],
                'private_verdict': private['verdict'] if private else 'NOT_RUN', 'head': value['head_commit'],
                'source_evidence_sha256': value['committed_patch_sha256']}
    expected = {'original-preserved': 'PASS', 'new-regression-file': 'PASS',
                'existing-test-appended': 'FAIL', 'unchanged-baseline': 'FAIL'}
    after = hashlib.sha256(ledger.read_bytes()).hexdigest()
    passed = (all(results[k]['candidate_verdict'] == v for k, v in expected.items()) and
              all(results[k]['private_verdict'] == 'PASS' for k in ('original-preserved', 'new-regression-file')) and before == after)
    proof = {'status': 'PASS' if passed else 'FAIL', 'model_requests': 0, 'uid': os.getuid(),
        'ledger_sha256_before': before, 'ledger_sha256_after': after, 'results': results,
        'control_receipt_sha256': hashlib.sha256(Path(entry['receipt']).read_bytes()).hexdigest(),
        'source_sha256': {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                          for m in (main, shared, __import__('p6_gate_policy'))},
        'control_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'evidence_kind': 'ZERO_MODEL_REAL_GIT_AND_FENCED_EVALUATION_CONTROL_NOT_MAIN_ACCEPTANCE'}
    exclusive_json(root/'receipt.json', proof)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    proof = check(parser.parse_args().output)
    print(json.dumps(proof))
    raise SystemExit(0 if proof['status'] == 'PASS' else 1)
