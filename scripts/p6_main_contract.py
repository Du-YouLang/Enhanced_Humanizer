"""Pure fail-closed selection checks for the frozen main protocol."""
from p2_candidates import validate_pool


def classify_role_completion(worker):
    """Only trusted broker evidence distinguishes a local cap from upstream 402.

    Keep the worker's original failure and error; HTTP status text alone must
    never turn credential, provider, policy or transport failures into a cap.
    """
    value=dict(worker)
    denials=worker.get('broker_denials',[])
    if worker.get('status')=='INFRA_FAIL' and denials and all(
        d.get('reason')=='Role request cap exhausted' for d in denials
    ):
        value.update(status='BUDGET_EXHAUSTED',raw_worker_status='INFRA_FAIL',
                     operational_stop_reason='MAIN_ROLE_REQUEST_CAP')
    return value


def enhanced_selection(original,expanded,input_judgment,merge_judgment):
    validate_pool(original);validate_pool(expanded)
    previous={c['id']:c for c in original['candidates']}
    current={c['id']:c for c in expanded['candidates']}
    if set(current)!=set(previous)|{'M'} or any(current[key]!=value for key,value in previous.items()):
        raise ValueError('Reviewer comparison changed original candidate evidence')
    for pool,judgment in ((original,input_judgment),(expanded,merge_judgment)):
        if judgment.get('pool_hash')!=pool['pool_hash']:raise ValueError('Judgment is for a different pool')
        if judgment.get('status')!='COMPLETED':return None
    selected=merge_judgment.get('eligible_selected')
    if selected is not None and (selected not in current or current[selected]['verdict']!='PASS'):
        raise ValueError('Failed candidate cannot become an enhanced success')
    return selected
