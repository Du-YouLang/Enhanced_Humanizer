def weighted_mean(pairs):
    """Return sum(value * weight) / sum(weight) for an iterable of pairs.

    Consume the iterable once. Negative weights and zero total weight
    (including empty input) raise ValueError.
    """
    numerator = 0
    denominator = 0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be non-negative")
        numerator += value * weight
        denominator += weight

    if denominator == 0:
        raise ValueError("total weight must be non-zero")
    return numerator / denominator
