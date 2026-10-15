"""Supplemental fresh trial; never overwrite or silently resume an old cell."""
import fcntl,hashlib,json,os,sys,time
from pathlib import Path
from pi_network_redo_policy import validate_redo


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(plan):
    body=dict(plan);expected=body.pop('plan_sha256')
    sys.path.insert(0,plan['executor'])
    import pi_full_main_linux as core
    if core.digest(body)!=expected:raise ValueError('Redo plan changed')
    for path,h in {**plan['source_sha256'],**plan['original_evidence_sha256']}.items():
        if sha(path)!=h:raise ValueError('Redo source/original evidence changed')
    original=read(plan['original_result']);validate_redo(plan,original)
    core.validate_bindings(plan['executor_payload']);core.require_controls(plan['executor_payload'])
    if plan['cell'] not in plan['executor_payload']['plan']['cells']:
        raise ValueError('Redo task is outside the original frozen task set')
    from p6_network_policy import retry10_transport
    retry10_transport(plan['executor_payload']['plan']['deepseek_transport_policy'])
    old=read(plan['ledger_archive']);current=read(core.pi.LEDGER)
    if current['requests'][:len(old['requests'])]!=old['requests'] or current['codex_turns'][:len(old['codex_turns'])]!=old['codex_turns']:
        raise ValueError('Original cumulative ledger prefix changed')
    return core


def execute(payload):
    plan=payload['plan'];core=bind(plan);core.pi.protect_memory()
    if os.getuid()==0:raise RuntimeError('Non-root local WSL required')
    if payload['mode']=='controls':
        return {'status':'PASS_ONE_CELL_REDO_BINDINGS','model_calls':0,'cell':plan['cell'],
                'original_preserved':True,'ledger_sha256':sha(core.pi.LEDGER)}
    if payload['mode']!='execute':raise ValueError('Unknown redo mode')
    # The same lock as the active finite Pi controller. Never preempt it.
    with (core.pi.BASE/'full-main-owner.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        core.pi.quiet()
        if not Path(plan['after_run_receipt']).is_file():raise ValueError('Prior active controller lacks a closed receipt')
        ledger=core.MainLedger(core.pi.LEDGER,plan['executor_payload']['budget'])
        state=read(core.pi.LEDGER)
        if len(state['requests'])>=10000 or state['cash_bound_nano']+ledger.request_reserve>250_000_000_000:
            return {'status':'BLOCKED_CUMULATIVE_BUDGET','model_calls':0,'original_preserved':True,'redo_started':False}
        run_id=payload['run_id']
        if not __import__('re').fullmatch(r'formal-network-redo-[0-9TZ]+',run_id):raise ValueError('Exact supplemental run ID required')
        # One durable marker per human authorization; a crash never permits
        # silent dispatch again. An operator must reconcile uncertain starts.
        core.exclusive(Path(plan['single_use_marker']),{'run_id':run_id,'plan_sha256':plan['plan_sha256'],'automatic_replay':False})
        root=core.pi.RUNS/run_id;root.mkdir();(root/'control').mkdir();(root/'control/canary').write_text('controller only')
        core.exclusive(root/'plan.json',plan)
        core.exclusive(root/'ledger-before.private.json',state)
        journal=core.Journal(root/'control/stages')
        p={**plan['executor_payload'],'run_id':run_id,'key':payload['key']}
        row=core.run_cell(root,p,plan['cell'],journal)
        # The original formal matrix is immutable. This is a separate trial.
        supplement={'status':'AUTHORIZED_NETWORK_REDO_COMPLETED','result':row,
            'original_run':plan['original_run'],'original_result_sha256':plan['original_evidence_sha256'][plan['original_result']],
            'original_outcome':read(plan['original_result'])['outcome'],'original_result_preserved':True,
            'authorization':plan['authorization'],'fresh_role_seconds':900,'fresh_role_requests':1000,
            'new_trials':1,'network_cause':'USER_REPORTED_LOCAL_SATURATION_NOT_INDEPENDENTLY_PROVEN',
            'analysis_policy':'SEPARATE_AUTHORIZED_FRESH_TRIAL_DO_NOT_OVERWRITE_OR_POOL_ORIGINAL',
            'external_release_authorized':False,'api_cash_actual':'unavailable'}
        for path,h in plan['original_evidence_sha256'].items():
            if sha(path)!=h:raise ValueError('Original evidence changed during redo')
        core.exclusive(root/'receipt.json',supplement)
        return {'status':supplement['status'],'outcome':row['outcome'],'root':str(root)}


if __name__=='__main__':print(json.dumps(execute(json.load(sys.stdin)),ensure_ascii=False),flush=True)
