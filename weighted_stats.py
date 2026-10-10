def weighted_mean(pairs):
    total_weight = 0
    weighted_sum = 0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be non-negative")
        total_weight += weight
        weighted_sum += value * weight
    if total_weight == 0:
        raise ValueError("total weight must be greater than zero")
    return weighted_sum / total_weight
