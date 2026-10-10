def weighted_mean(pairs):
    """Return the weighted mean of an iterable of (value, weight) pairs.

    Raise ValueError for negative weights or a zero total weight.
    """
    weighted_total = 0
    total_weight = 0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be nonnegative")
        weighted_total += value * weight
        total_weight += weight

    if total_weight == 0:
        raise ValueError("total weight must be positive")
    return weighted_total / total_weight
