"""Scientific result checks independent of candidate imports and private oracles."""
import math
from statistics import mean, pstdev, stdev


def grid_summary(rows, *, dataset, activation, widths, depths, seeds, deep_narrow):
    """Require complete declared coverage; never derive a region from observed rows.

    Accuracy is a fraction, cosine is dimensionless. Repeated seeds are averaged
    per cell before grid comparisons; sample and population spread are distinct.
    Scientific claim support is separate from numerical implementation fidelity.
    """
    methods = ('bp', 'pc', 'pcalm')
    dimensions = (tuple(widths), tuple(depths), tuple(seeds))
    if any(not values or len(values) != len(set(values)) or any(type(v) is not int or v < 0 for v in values)
           for values in dimensions) or any(v < 1 for v in (*dimensions[0], *dimensions[1])):
        raise ValueError('Distinct, explicit width/depth/seed sets required')
    widths, depths, seeds = dimensions
    region = tuple(tuple(cell) for cell in deep_narrow)
    if not region or len(region) != len(set(region)) or any(w not in widths or d not in depths for w, d in region):
        raise ValueError('The frozen deep/narrow region must be covered by the declared grid')
    expected = {(method, w, d, seed) for method in methods for w in widths for d in depths for seed in seeds}
    observed = {}
    for row in rows:
        if row.get('dataset') != dataset or row.get('activation') != activation:
            continue
        key = (row.get('method'), row.get('width'), row.get('depth'), row.get('seed'))
        if any(type(row.get(k)) is not int for k in ('width','depth','seed')) or key not in expected or key in observed:
            raise ValueError('Duplicate or undeclared scientific run')
        accuracy, cosine = row.get('final_test_acc'), row.get('grad_cos_to_bp')
        # FP32 dot/norm roundoff can put even BP's self-cosine slightly above 1.
        # Preserve observed values, accepting only a fixed 1e-6 boundary tolerance.
        if any(type(v) not in (float,int) or not math.isfinite(v) for v in (accuracy,cosine)) or not 0 <= accuracy <= 1 or not -1.000001 <= cosine <= 1.000001:
            raise ValueError('Finite accuracy fractions and gradient cosine required')
        observed[key] = (accuracy,cosine)
    if set(observed) != expected:
        raise ValueError('Incomplete declared grid/seed/method coverage')
    cells = tuple((w,d) for w in widths for d in depths)
    acc = {(m,w,d): mean(observed[m,w,d,s][0] for s in seeds) for m in methods for w,d in cells}
    cos = {(m,w,d): mean(observed[m,w,d,s][1] for s in seeds) for m in methods for w,d in cells}
    gap = lambda m: [acc['bp',w,d]-acc[m,w,d] for w,d in cells]
    return {
        'grid_cells':len(cells), 'runs':len(observed), 'seeds':list(seeds),
        'deep_narrow_cells':[list(cell) for cell in region],
        'pcalm_gap_to_bp_mean':mean(gap('pcalm')),
        'pcalm_gap_to_bp_max':max(gap('pcalm')),
        'pc_gap_to_bp_mean':mean(gap('pc')),
        'pcalm_minus_pc_deep_narrow_mean':mean(acc['pcalm',w,d]-acc['pc',w,d] for w,d in region),
        'pcalm_minus_pc_cosine_mean':mean(cos['pcalm',w,d]-cos['pc',w,d] for w,d in cells),
        'seed_spread':{
            m:{'ddof0_mean':mean(pstdev(observed[m,w,d,s][0] for s in seeds) for w,d in cells),
               'ddof0_max':max(pstdev(observed[m,w,d,s][0] for s in seeds) for w,d in cells),
               'ddof1_mean':mean(stdev(observed[m,w,d,s][0] for s in seeds) for w,d in cells) if len(seeds)>1 else 'unavailable',
               'ddof1_max':max(stdev(observed[m,w,d,s][0] for s in seeds) for w,d in cells) if len(seeds)>1 else 'unavailable'}
            for m in methods},
        'implementation_fidelity':'NOT_DETERMINED_BY_CLAIM_STATISTICS',
    }


def claim_checks(summary, thresholds):
    """Strict comparisons at pre-frozen thresholds; all five named checks required."""
    specs = {
        'C1':('pcalm_gap_to_bp_mean','lt'),
        'C2':('pcalm_gap_to_bp_max','lt'),
        'C3':('pcalm_minus_pc_deep_narrow_mean','gt'),
        'C4':('pc_gap_to_bp_mean','gt'),
        'C5':('pcalm_minus_pc_cosine_mean','gt'),
    }
    if set(thresholds) != set(specs): raise ValueError('Exactly the five frozen criteria are required')
    checks = {}
    for name,(metric, direction) in specs.items():
        value, limit = summary[metric], thresholds[name]
        if any(type(x) not in (float,int) or not math.isfinite(x) for x in (value,limit)):
            raise ValueError('Finite statistics and thresholds required')
        checks[name] = value < limit if direction == 'lt' else value > limit
    return {'criteria':checks,'claim_supported':all(checks.values()),
            'claim_exit_code':0 if all(checks.values()) else 1,
            'implementation_fidelity':summary['implementation_fidelity']}


def normalized_material_path(name):
    """Normalize Windows manifests without permitting drive names or traversal."""
    from pathlib import PurePosixPath
    if not isinstance(name,str) or not name or ':' in name or '\x00' in name:
        raise ValueError('A relative material path is required')
    name = name.replace('\\','/')
    parts = name.split('/')
    if any(part in ('','.', '..') for part in parts): raise ValueError('Unsafe material path')
    return PurePosixPath(*parts)
