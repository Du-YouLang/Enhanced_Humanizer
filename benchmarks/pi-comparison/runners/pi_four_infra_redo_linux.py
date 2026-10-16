"""Four human-authorized fresh Pi trials, using the existing fenced full-main executor."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from p6_pi_four_redo_scope import validate_targets, RUN_PATTERN


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(plan):
    sys.path.insert(0, plan['executor'])
    import pi_full_main_linux as core
    body = dict(plan)
    expected = body.pop('plan_sha256')
    if core.digest(body) != expected:
        raise ValueError('Four-trial plan digest changed')
    for path, expected in {**plan['source_sha256'], **plan['retained_sha256']}.items():
        if sha(path) != expected:
            raise ValueError('Frozen source or retained evidence changed: ' + path)
    validate_targets(plan, [read(r['result_path']) for r in plan['originals']])
    core.validate_bindings(plan['executor_payload'])
    if plan['executor_payload']['plan']['authorized_paid_cells'] != plan['cells']:
        raise ValueError('Executor paid scope differs')
    from p6_network_policy import retry10_transport
    retry10_transport(plan['executor_payload']['plan']['deepseek_transport_policy'])
    before, current = read(plan['ledger_archive']), read(core.pi.LEDGER)
    if (current['requests'][:len(before['requests'])] != before['requests']
            or current['codex_turns'][:len(before['codex_turns'])] != before['codex_turns']):
        raise ValueError('Original cumulative ledger prefix changed')
    return core


def execute(payload):
    plan = payload['plan']
    core = bind(plan)
    core.pi.protect_memory()
    if os.getuid() == 0:
        raise RuntimeError('Non-root local WSL required')
    with (core.pi.BASE / 'full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        core.pi.quiet()
        if payload['mode'] == 'controls':
            gate = core.require_controls(plan['executor_payload'])
            result = {'status': 'PASS_FOUR_AUTHORIZED_TRIAL_BINDINGS', 'plan_sha256': plan['plan_sha256'],
                      'executor_controls': gate, 'new_model_calls': 0, 'ledger_sha256': sha(core.pi.LEDGER)}
            core.exclusive(plan['controls_receipt'], result)
            return result
        if payload['mode'] != 'execute' or not re.fullmatch(RUN_PATTERN, payload['run_id']):
            raise ValueError('Exact supplemental run ID and mode required')
        gate = read(plan['controls_receipt'])
        if gate['status'] != 'PASS_FOUR_AUTHORIZED_TRIAL_BINDINGS' or gate['plan_sha256'] != plan['plan_sha256']:
            raise ValueError('Actual exact-source controls required')
        run_id = payload['run_id']
        root = core.pi.RUNS / run_id
        marker = Path(plan['single_use_marker'])
        # Re-entry may only reuse completed journal steps from this exact run.
        # An uncertain model.started stage is rejected by the existing Journal.
        if marker.exists():
            if read(marker) != {'run_id': run_id, 'plan_sha256': plan['plan_sha256']}:
                raise ValueError('Authorization already consumed by another run')
            if read(root / 'plan.json') != plan:
                raise ValueError('Existing supplemental plan changed')
            if (root / 'receipt.json').exists():
                raise ValueError('Closed supplemental run cannot be replayed')
        else:
            if root.exists():
                raise ValueError('Uncertain supplemental directory exists without its marker')
            core.exclusive(marker, {'run_id': run_id, 'plan_sha256': plan['plan_sha256']})
            root.mkdir()
            (root / 'control').mkdir()
            (root / 'control/canary').write_text('controller only')
            core.exclusive(root / 'plan.json', plan)
            core.exclusive(root / 'ledger-before.private.json', read(core.pi.LEDGER))
        journal = core.Journal(root / 'control/stages')
        executor_payload = {**plan['executor_payload'], 'run_id': run_id, 'key': payload.get('key')}
        results = []
        status = 'FOUR_AUTHORIZED_TRIALS_COMPLETED'
        for index, cell in enumerate(plan['cells']):
            name = cell['task_id']+'-'+cell['profile']+'-'+cell['provider']
            # Subscription trials have their own reservations and no API cash charge.
            # Cash cannot be silently expanded for either DeepSeek trial.
            if cell['provider'] == 'deepseek' and not (root / 'control/stages' / (name+'-cell.completed.json')).exists():
                ledger = core.MainLedger(core.pi.LEDGER, plan['executor_payload']['budget'])
                state = read(core.pi.LEDGER)
                if len(state['requests']) >= ledger.requests or state['cash_bound_nano'] + ledger.request_reserve > ledger.cash_nano:
                    status = 'CUMULATIVE_BUDGET_STOP'
                    break
            row = journal.run(name+'-cell', lambda c=cell: core.run_cell(root, executor_payload, c, journal))
            results.append(row)
            progress = root / ('progress-'+str(index+1).zfill(3)+'.json')
            if not progress.exists():
                core.exclusive(progress, {'completed_new_trials': len(results), 'total_new_trials': 4, 'last': row})
            # A closed infrastructure failure is preserved and the other expressly
            # authorized cells still receive their one trial; no same-cell loop.
        for path, expected in plan['retained_sha256'].items():
            if sha(path) != expected:
                raise ValueError('Original evidence changed during supplemental trials')
        receipt = {'status': status, 'results': results, 'completed_new_trials': len(results), 'total_new_trials': 4,
                   'plan_sha256': plan['plan_sha256'], 'authorization': plan['authorization'],
                   'original_matrix_preserved': True, 'originals': plan['originals'],
                   'previous_supplemental_trial_preserved': True,
                   'analysis_policy': 'SEPARATE_FRESH_TRIALS_DO_NOT_OVERWRITE_OR_POOL_ORIGINALS',
                   'cause_attribution': 'HUMAN_NETWORK_OR_SERVICE_HYPOTHESES_NOT_INDEPENDENTLY_PROVEN',
                   'api_cash_actual': 'unavailable', 'external_release_authorized': False,
                   'ledger_after_sha256': sha(core.pi.LEDGER)}
        core.exclusive(root / 'receipt.json', receipt)
        return {k: v for k, v in receipt.items() if k not in ('results', 'originals')}


if __name__ == '__main__':
    payload=json.load(sys.stdin)
    try:
        print(json.dumps(execute(payload), ensure_ascii=False), flush=True)
    except Exception as error:
        run_id=payload.get('run_id','')
        if payload.get('mode')=='execute' and re.fullmatch(RUN_PATTERN,run_id):
            root=Path('/opt/workbench/benchmark/private/pi-comparison')/run_id
            if root.exists():
                # Error type/stage receipts suffice; never serialize credentials.
                import time
                from pi_full_protocol import exclusive
                exclusive(root/('failure-'+str(time.time_ns())+'.json'),
                          {'status':'INFRA_RECONCILIATION_REQUIRED','error_type':type(error).__name__,
                           'automatic_model_replay':False,'originals_preserved':True})
        raise
