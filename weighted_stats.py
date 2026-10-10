def weighted_mean(pairs):
    weighted_sum = 0.0
    total_weight = 0.0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be non-negative")
        weighted_sum += value * weight
        total_weight += weight

    if total_weight == 0:
        raise ValueError("total weight must be non-zero")

    return weighted_sum / total_weight
