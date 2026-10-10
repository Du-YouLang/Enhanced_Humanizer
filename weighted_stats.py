def weighted_mean(pairs):
    """Compute sum(value * weight) / sum(weight) over an iterable of pairs.

    Accepts any iterable of ``(value, weight)`` pairs, including generators.
    Raises ``ValueError`` if any weight is negative or if the total weight is
    zero (including an empty iterable).
    """
    total_weight = 0
    weighted_sum = 0
    for value, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be non-negative")
        weighted_sum += value * weight
        total_weight += weight
    if total_weight == 0:
        raise ValueError("total weight must be non-zero")
    return weighted_sum / total_weight
