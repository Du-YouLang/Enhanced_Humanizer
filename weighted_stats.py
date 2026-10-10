def weighted_mean(pairs):
    total = 0
    total_weight = 0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be non-negative")
        total += value * weight
        total_weight += weight
    if total_weight == 0:
        raise ValueError("total weight must be non-zero")
    return total / total_weight
