"""Read-only paired judge changes for unchanged programs and different evidence."""
from itertools import combinations


def paired_judgments(source, traced, identity, truth):
    original = identity['original_pool_hash']
    trace = identity['trace_pool_hash']
    objects = identity['unchanged_candidate_objects']
    ids = [v['id'] for v in objects]
    if len(ids) != len(set(ids)) or original == trace:
        raise ValueError('Distinct evidence and unique unchanged programs required')
    rows = {}
    for name in sorted(set(source) | set(traced)):
        left, right = source.get(name), traced.get(name)
        if left and left['pool_hash'] != original or right and right['pool_hash'] != trace:
            raise ValueError('Sensitivity judgment is bound to the wrong evidence pool')
        row = {'source_status': left['status'] if left else 'NOT_RUN',
               'trace_status': right['status'] if right else 'NOT_RUN'}
        comparable = left and right and left['status'] == right['status'] == 'COMPLETED'
        row['status'] = 'COMPARABLE' if comparable else 'INDETERMINATE'
        if comparable:
            for judgment in (left, right):
                if len(judgment['ranking']) != len(ids) or set(judgment['ranking']) != set(ids):
                    raise ValueError('Sensitivity cannot change candidate coverage')
            a, b = ({v: n for n, v in enumerate(j['ranking'])} for j in (left, right))
            pairs = [(a[x] < a[y]) == (b[x] < b[y]) for x, y in combinations(ids, 2)]
            row['pairwise_order_agreement'] = sum(pairs)/len(pairs) if pairs else 'unavailable'
        else:
            row['pairwise_order_agreement'] = 'unavailable'
        for field in ('raw_selected', 'eligible_selected'):
            selections = [j.get(field) if j else None for j in (left, right)]
            if any(v is not None and v not in ids for v in selections):
                raise ValueError('Selected program is absent from the unchanged pool')
            row[field+'_changed'] = selections[0] != selections[1] if comparable else 'unavailable'
            for mode, selected in zip(('source', 'trace'), selections):
                verdict = truth.get(selected, {}).get('verdict', 'unavailable')
                row[mode+'_'+field] = selected
                row[mode+'_'+field+'_oracle_verdict'] = verdict
                row[mode+'_'+field+'_accepted'] = verdict == 'PASS' if verdict in ('PASS', 'FAIL', 'TIMEOUT') else 'unavailable'
        rows[name] = row
    return {'identity': identity, 'judges': rows,
            'interpretation': 'Paired evidence sensitivity on the same programs; new independent scoring sessions, no candidate replay. A single pair cannot separate evidence effects from scoring variability. Missing/blocked judges and no eligible selection are not zero accuracy.'}
