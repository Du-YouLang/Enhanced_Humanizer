"""Only unstarted Pi cells may enter this successor; failed cells stay retained."""
def retained_results(receipts):
    """Combine an ordered receipt chain without replacing any previous row."""
    if not receipts:raise ValueError('Retained receipt chain required')
    rows=[]
    for receipt in receipts:
        part=receipt.get('results')
        if not isinstance(part,list) or not part:raise ValueError('Nonempty closed receipt required')
        if receipt.get('prior_completed_cells',len(rows))!=len(rows):raise ValueError('Broken continuation lineage')
        rows.extend(part)
    return rows


def remaining_cells(plan,results):
    completed=[r['cell'] for r in results]
    if not completed or completed!=plan['cells'][:len(completed)]:
        raise ValueError('Exact original completed prefix required')
    if len({(c['task_id'],c['profile'],c['provider'],c['repetition']) for c in completed})!=len(completed):
        raise ValueError('Duplicate original cell')
    if results[-1]['worker_status'] not in ('INFRA_FAIL','INFRA_RETRY_PENDING'):
        raise ValueError('This successor follows a reconciled infrastructure stop only')
    return plan['cells'][len(completed):]


def transport_successor(original,successor):
    """Only a prospective DeepSeek transport amendment; task/budget pins stay."""
    from p6_network_policy import retry10_transport
    retry10_transport(successor['plan'].get('deepseek_transport_policy',{}))
    if original['budget']!=successor['budget']:raise ValueError('Transport cannot change ledger authorization')
    ignored={'source_sha256','entrypoint_sha256','plan_sha256','deepseek_transport_policy'}
    if ({k:v for k,v in original['plan'].items() if k not in ignored}
            !={k:v for k,v in successor['plan'].items() if k not in ignored}):
        raise ValueError('Transport cannot change frozen tasks/time/models/oracles')
    return successor
