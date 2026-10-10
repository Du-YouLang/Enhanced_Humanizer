def weighted_mean(pairs):
    weighted_total = 0.0
    weight_total = 0.0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be non-negative")
        weighted_total += value * weight
        weight_total += weight
    if weight_total == 0:
        raise ValueError("total weight must be non-zero")
    return weighted_total / weight_total
