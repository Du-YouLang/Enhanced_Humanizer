def weighted_mean(pairs):
    total_weight = 0
    weighted_sum = 0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must not be negative")
        weighted_sum += value * weight
        total_weight += weight
    if total_weight == 0:
        raise ValueError("total weight must be non-zero")
    return weighted_sum / total_weight
