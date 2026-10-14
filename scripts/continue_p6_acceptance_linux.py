"""Continue frozen PC-ALM acceptance only. No credentials or model generation.

This supplemental entry is outside the immutable main source deployment. It
reuses exact retained candidate/selection records and completed acceptance files.
An unfinished numerical evaluation restarts in the original scientific fence;
arbitrary live training state is not a checkpoint.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import time

BASE = Path('/opt/workbench/benchmark/private/main-runs')
LEDGER = Path('/opt/workbench/state/p6-main-local-20261011/ledger.json')
ROLES = {'DS0': 'native-ds', 'A': 'pool-A', 'B': 'pool-B', 'C': 'pool-C',
         'M': 'reviewer', 'D': 'native-sol', 'E': 'relay', 'F': 'enhanced-relay'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def read(path):
    return json.loads(Path(path).read_bytes())


def program_identity(candidate):
    return digest({'patch': candidate.get('patch'), 'source': candidate.get('source')})


def validate_truth(candidate, truth):
    if (truth['program_identity'] != program_identity(candidate) or
            truth['worker_status'] != candidate['worker_status'] or
            truth['public_verdict'] != candidate['verdict']):
        raise ValueError('Retained acceptance does not match the frozen candidate')
    if truth['acceptance']['verdict'] not in ('PASS', 'FAIL', 'INDETERMINATE'):
        raise ValueError('Retained acceptance is not terminal')


def shutdown_interruption(name, truth, mtime, pause):
    """Only exact shutdown signal evidence can exclude a late synthetic FAIL."""
    a = truth['acceptance']
    return (name not in pause['completed_private_acceptance_files'] and
            pause['at_unix'] <= mtime <= pause['at_unix'] + 15 and
            a.get('error_type') == 'InterruptedError' and
            a.get('reason') == 'Owned main controller interrupted by signal 15' and
            a.get('verdict') == 'FAIL' and a.get('elapsed_seconds') == 0)


def recover_truth(candidates, existing, grader, save):
    """Reusing FAIL/INDETERMINATE is as mandatory as reusing PASS."""
    accepted = {}
    for cid, truth in existing.items():
        validate_truth(candidates[cid], truth)
        candidate = candidates[cid]
        if candidate['verdict'] == 'PASS' and candidate['worker_status'] == 'COMPLETED':
            identity = program_identity(candidate)
            if identity in accepted and accepted[identity] != truth['acceptance']:
                raise ValueError('Conflicting acceptance of the same program')
            accepted[identity] = truth['acceptance']
    truth = dict(existing)
    for cid, candidate in candidates.items():
        if cid in truth:
            continue
        identity = program_identity(candidate)
        if candidate['verdict'] != 'PASS' or candidate['worker_status'] != 'COMPLETED':
            checked = {'verdict': 'FAIL', 'private_execution': 'NOT_RUN_PUBLIC_HARD_GATE_FAILED',
                       'elapsed_seconds': 0, 'reason': 'Original public hard gate failed'}
        else:
            if identity not in accepted:
                try:
                    accepted[identity] = grader(candidate)
                except (ValueError, OSError, KeyError, TypeError) as error:
                    accepted[identity] = {'verdict': 'FAIL', 'error_type': type(error).__name__,
                                         'reason': str(error)[:500], 'elapsed_seconds': 0}
            checked = accepted[identity]
        item = {'program_identity': identity, 'worker_status': candidate['worker_status'],
                'public_verdict': candidate['verdict'], 'acceptance': checked}
        validate_truth(candidate, item)
        save(cid, item)
        truth[cid] = item
    return truth, len(accepted)


def incomplete_timing(row):
    """No reconstructing lost monotonic intervals by summing parallel workers."""
    row['metrics'].update(end_to_end_seconds='unavailable', model_and_public_check_seconds='unavailable',
                          human_interventions='unavailable', human_seconds='unavailable')
    row['reason'] += '; acceptance continued after human shutdown; original wall intervals unavailable'
    row['timing_availability'] = 'Original per-arm monotonic intervals were not checkpointed; exclude from timing comparisons'
    return row


@contextmanager
def lock(path):
    import fcntl
    with Path(path).open('a+b') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def no_models(*args, **kwargs):
    raise PermissionError('Acceptance continuation cannot launch a model or read a credential')


def sources(contract):
    for path, expected in contract['source_sha256'].items():
        if sha(Path(path).read_bytes()) != expected:
            raise ValueError('Frozen native source changed: ' + path)
    if contract.get('key') or contract['mode'] != 'execute' or contract['task']['task_id'] != 'SCI-PC-ALM':
        raise ValueError('Only a credential-free frozen PC-ALM execution can continue')


def load(root):
    """Verify full source evidence and selection hashes without re-running public tests."""
    contract = read(root / 'control/run-contract.json')
    sources(contract)
    sys.path[:0] = ['/opt/workbench/source', '/opt/workbench/source/src']
    import p6_main_runtime_linux as main
    import p6_runtime_linux as shared
    from p6_main_budget import authorization, task_limits
    from p6_science_main_linux import task as science_task
    from p6_gate_policy import GENERATION_RULES
    from workbench.benchmark import check_manifest
    _, budget_sha = authorization(contract['budget'])
    check_manifest(contract['manifest'])
    if contract['manifest']['budget_authorization_sha256'] != budget_sha:
        raise ValueError('Original budget/manifest binding changed')
    task = science_task(contract)
    task['prompt'] += '\n' + GENERATION_RULES
    if sha(task['prompt'].encode()) != contract['public_prompt_sha256']:
        raise ValueError('Frozen public prompt changed')
    prep = read(root / 'preparation.json')
    if prep['env_sha256'] != task['seal']['env_sha256'] or prep['base_commit'] != task['base_commit']:
        raise ValueError('Original environment or baseline changed')
    workers = {name: read(root / name / 'controller-outcome.json')
               for name in [*ROLES.values(), 'judge-input', 'judge-merge']}
    candidates = {cid: read(root / role / 'candidate-private.json') for cid, role in ROLES.items()}
    decision = workers['reviewer'].get('answer', {}).get('decision', {})
    considered = decision.get('considered_candidates', [])
    if workers['reviewer']['status'] == 'COMPLETED' and (
            not isinstance(considered, list) or not all(isinstance(c, str) for c in considered) or
            sorted(considered) != ['A', 'B', 'C'] or decision.get('action') != 'IMPLEMENTED'):
        candidates['M']['verdict'] = 'FAIL'
    for cid, c in candidates.items():
        role = ROLES[cid]; expected = root / role
        if c['id'] != cid or Path(c['root']) != expected or Path(workers[role]['work']) != expected / 'code':
            raise ValueError('Retained role paths or identity changed')
        if workers[role]['scope'] != root.name + '/' + role or c['worker_status'] != workers[role]['status']:
            raise ValueError('Retained worker identity changed')
        patch, source = shared.program_evidence(expected / 'code', task['base_commit'])
        if patch != c['patch'] or source != c['source']:
            raise ValueError('Frozen complete candidate evidence changed: ' + cid)
    shared.ACTIVE.clear()
    shared.ACTIVE.update(root=root, task=task, payload=contract, key='', workers=workers,
                         contract_sha256=digest(contract), preparation=prep, main_phase=True, defer_hidden=True,
                         active_seconds=task_limits(contract['budget'], contract['task'])['active_seconds'])
    shared.LEDGER_PATH = LEDGER
    pool = read(root / 'frozen-public-pool.json'); expanded = read(root / 'frozen-expanded-public-pool.json')
    if shared.public_pool([candidates[c] for c in 'ABC']) != pool or shared.public_pool(
            [candidates[c] for c in 'ABCM'], 'JUDGE_COMPARISON') != expanded:
        raise ValueError('Frozen public pools changed')
    judgments = read(root / 'judgments.json'); merges = read(root / 'merge-judgments.json')
    best = shared.select(pool, judgments['J0'])
    enhanced = main.enhanced_selection(pool, expanded, judgments['J3'], merges['J3'])
    selected = {'A': candidates['DS0'], 'B': candidates.get(best), 'C': candidates.get(enhanced),
                **{arm: candidates[arm] for arm in 'DEF'}}
    freeze = read(root / 'frozen-selections.json')
    actual = {'heads': {arm: c.get('head_commit') if c else None for arm, c in selected.items()},
              'public_candidate_hashes': {arm: digest(c) if c else None for arm, c in selected.items()},
              'hidden_results_seen': False}
    if freeze != actual:
        raise ValueError('Original pre-acceptance selection changed')
    shared.ACTIVE['enhancement_judge_incomplete'] = judgments['J3']['status'] != 'COMPLETED' or merges['J3']['status'] != 'COMPLETED'
    for name in ('launch', 'job', 'lav', 'judge'):
        setattr(main, name, no_models)
    for name in ('launch', 'prepare_job', 'candidate', 'judge'):
        setattr(shared, name, no_models)
    return contract, candidates, selected, workers, main, shared


def input_files(root):
    names = ['control/run-contract.json', 'control/human-shutdown-pause.json', 'preparation.json',
             'frozen-public-pool.json', 'frozen-expanded-public-pool.json', 'frozen-selections.json',
             'judgments.json', 'merge-judgments.json', 'merge-ablation-public.json']
    names += [role + '/controller-outcome.json' for role in [*ROLES.values(), 'judge-input', 'judge-merge']]
    names += [role + '/candidate-private.json' for role in ROLES.values()]
    names += [p.name for p in root.glob('private-acceptance-*.json')]
    return {name: sha((root / name).read_bytes()) for name in sorted(names)}


def prepare(root, folder):
    if root.parent != BASE or root.is_symlink():
        raise ValueError('Exact original native main run required')
    if (root / 'receipt.json').exists() or list(root.glob('arm-*.json')):
        raise ValueError('Already finalized or partially finalized task cannot prepare a new continuation')
    pause = read(root / 'control/human-shutdown-pause.json')
    if pause['status'] != 'HUMAN_PAUSED_FOR_SHUTDOWN' or not (root / 'frozen-selections.json').exists():
        raise ValueError('Human pause after frozen selections is required')
    contract, candidates, selected, workers, _, _ = load(root)
    interrupted = {}
    for p in root.glob('private-acceptance-*.json'):
        cid = p.stem.removeprefix('private-acceptance-'); value = read(p)
        validate_truth(candidates[cid], value)
        if shutdown_interruption(p.name, value, p.stat().st_mtime, pause):
            interrupted[cid] = {'original_sha256': sha(p.read_bytes()),
                                'recovered_output': 'control/acceptance-recovered-' + cid + '.json',
                                'reason': 'Exact SIGTERM shutdown receipt is preserved but excluded from model failure'}
    folder.mkdir(parents=True, exist_ok=False)
    plan = {'authorization': 'HUMAN_CONTINUE_AFTER_SHUTDOWN_20261013', 'source_run': str(root),
            'supplement_sha256': sha(Path(__file__).read_bytes()), 'inputs': input_files(root),
            'ledger_sha256': sha(LEDGER.read_bytes()), 'model_replays': 0, 'model_calls': 0,
            'incomplete_evaluation_policy': 'Restart only unfinished acceptance, preserve partial outputs; no live training checkpoint',
            'original_model_wall_intervals': 'unavailable', 'manifest_sha256': contract['manifest']['manifest_sha256']}
    plan['interrupted_acceptances'] = interrupted
    from p2_candidates import exclusive_json
    exclusive_json(folder / 'plan.json', plan)
    return plan


def execute(folder):
    plan = read(folder / 'plan.json'); root = Path(plan['source_run'])
    if plan['authorization'] != 'HUMAN_CONTINUE_AFTER_SHUTDOWN_20261013' or root.parent != BASE:
        raise ValueError('Missing explicit continuation authorization or original run')
    if sha(Path(__file__).read_bytes()) != plan['supplement_sha256']:
        raise ValueError('Supplement changed after preparation')
    with lock(folder / 'acceptance.lock'):
        for name, expected in plan['inputs'].items():
            if sha((root / name).read_bytes()) != expected:
                raise ValueError('Original retained input changed: ' + name)
        contract, candidates, selected, workers, main, shared = load(root)
        from p6_boot_recovery import Journal
        from p2_candidates import exclusive_json
        journal = Journal(folder / 'events.ndjson')
        writes = {v['detail']['name']: v['detail']['sha256'] for v in journal.entries
                  if v['event'] == 'WRITE_INTENT'}

        def unchanged():
            if sha(LEDGER.read_bytes()) != plan['ledger_sha256']:
                raise ValueError('Acceptance-only continuation observed a changed model ledger')
            sources(contract)

        def save(name, value):
            raw = (json.dumps(value, indent=2) + '\n').encode()
            expected = sha(raw); path = root / name
            if path.exists():
                if writes.get(name) != expected or sha(path.read_bytes()) != expected:
                    raise ValueError('Existing recovery output is not its durable write intent')
                return
            unchanged()
            journal.append('WRITE_INTENT', {'name': name, 'sha256': expected})
            exclusive_json(path, value)
            writes[name] = expected
            journal.append('WRITE_COMPLETED', {'name': name, 'sha256': expected})

        unchanged()
        existing = {}
        for p in root.glob('private-acceptance-*.json'):
            if p.name not in plan['inputs'] and writes.get(p.name) != sha(p.read_bytes()):
                raise ValueError('Unbound new acceptance file')
            cid = p.stem.removeprefix('private-acceptance-')
            if cid not in plan.get('interrupted_acceptances', {}):
                existing[cid] = read(p)
        for cid, info in plan.get('interrupted_acceptances', {}).items():
            p = root / info['recovered_output']
            if p.exists():
                if writes.get(info['recovered_output']) != sha(p.read_bytes()):
                    raise ValueError('Unbound recovered acceptance')
                existing[cid] = read(p)
        if (root / 'receipt.json').exists():
            if writes.get('receipt.json') != sha((root / 'receipt.json').read_bytes()):
                raise ValueError('Unbound final receipt')
            return read(root / 'receipt.json')
        journal.append('CONTINUE_ACCEPTANCE_ONLY', {'cached': list(existing), 'model_calls': 0})
        started = time.monotonic()

        def grade(candidate):
            unchanged()
            journal.append('GRADE_STARTED', {'id': candidate['id'], 'program_identity': program_identity(candidate)})
            from p6_science_main_linux import test
            value = test(Path(candidate['root']) / 'code', True)
            unchanged()
            return value

        def save_truth(cid, item):
            info = plan.get('interrupted_acceptances', {}).get(cid)
            name = info['recovered_output'] if info else 'private-acceptance-' + cid + '.json'
            save(name, item)
        truth, unique = recover_truth(candidates, existing, grade, save_truth)
        save('private-candidate-acceptance.json', truth)
        scope = lambda name: workers[name]['scope']
        scopes = {'A': [scope('native-ds')], 'B': [scope('pool-' + c) for c in 'ABC'],
                  'D': [scope('native-sol')]}
        scopes['C'] = scopes['B'] + [scope(n) for n in ('judge-input', 'reviewer', 'judge-merge')]
        scopes['E'] = scopes['A'] + [scope('relay')]
        scopes['F'] = scopes['C'] + [scope('enhanced-relay')]
        provenance = {'plan_sha256': sha((folder / 'plan.json').read_bytes()),
                      'supplement_sha256': plan['supplement_sha256'], 'model_replays': 0,
                      'model_calls': 0, 'original_inputs': plan['inputs'],
                      'excluded_shutdown_acceptances': plan.get('interrupted_acceptances', {})}
        from workbench.benchmark import validate_result
        results = []
        original_writer = main.exclusive_json
        try:
            # Reuse the frozen classification, then correct unavailable intervals
            # before the result is written or exposed. A scratch 0 is never persisted.
            main.exclusive_json = lambda path, row: None
            for arm, candidate in selected.items():
                row = main.record(arm, candidate, scopes[arm], 0,
                                  truth[candidate['id']]['acceptance'] if candidate else None)
                incomplete_timing(row)
                row['acceptance_recovery'] = provenance
                row['evidence_sha256'] = digest({'candidate': candidate, 'acceptance': truth[candidate['id']] if candidate else None,
                                                 'scopes': scopes[arm], 'run': root.name, 'recovery': provenance})
                validate_result(row, contract['manifest'], shared.ACTIVE['preparation'])
                save('arm-' + arm + '.json', row)
                results.append(row)
        finally:
            main.exclusive_json = original_writer
        limits = __import__('p6_main_budget').task_limits(contract['budget'], contract['task'])
        receipt = {'status': 'MAIN_TASK_COMPLETED', 'task_id': 'SCI-PC-ALM', 'run_id': root.name, 'results': results,
                   'model_activity_seconds': 'unavailable', 'controller_end_to_end_seconds': 'unavailable',
                   'common_generation_timeout_seconds': limits['role_seconds'], 'model_activity_time_cap_seconds': limits['active_seconds'],
                   'judgments': {k: v['status'] for k, v in read(root / 'judgments.json').items()},
                   'benchmark_oracle_audit_seconds': 'unavailable', 'private_unique_program_evaluations': unique,
                   'full_tool_trace_sensitivity': 'PENDING_SEPARATE_SAME_POOL_REVIEW', 'failures_preserved': True,
                   'api_cash_usd': 'unavailable', 'acceptance_recovery': provenance,
                   'recovery_elapsed_seconds': time.monotonic() - started, 'reused_acceptances': list(existing)}
        save('receipt.json', receipt)
        journal.append('COMPLETED', {'receipt_sha256': sha((root / 'receipt.json').read_bytes()), 'model_calls': 0})
        return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'execute'))
    p.add_argument('--folder', type=Path, required=True)
    p.add_argument('--run', type=Path)
    args = p.parse_args()
    if os.name != 'posix' or os.getuid() == 0:
        raise SystemExit('Non-root project native runtime required')
    if not args.folder.resolve().is_relative_to(Path('/opt/workbench/recovery')):
        raise SystemExit('Private project recovery folder required')
    value = prepare(args.run, args.folder) if args.mode == 'prepare' else execute(args.folder)
    print(json.dumps({k: v for k, v in value.items() if k != 'results'}), flush=True)
