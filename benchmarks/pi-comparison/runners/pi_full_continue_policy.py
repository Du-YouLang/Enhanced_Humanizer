"""Only unstarted Pi cells may enter this successor; failed cells stay retained."""
def remaining_cells(plan,results):
    completed=[r['cell'] for r in results]
    if not completed or completed!=plan['cells'][:len(completed)]:
        raise ValueError('Exact original completed prefix required')
    if len({(c['task_id'],c['profile'],c['provider'],c['repetition']) for c in completed})!=len(completed):
        raise ValueError('Duplicate original cell')
    if results[-1]['worker_status'] not in ('INFRA_FAIL','INFRA_RETRY_PENDING'):
        raise ValueError('This successor follows a reconciled infrastructure stop only')
    return plan['cells'][len(completed):]
