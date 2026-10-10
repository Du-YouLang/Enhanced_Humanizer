class WeightedMean:
    """Accumulate a weighted mean without retaining individual observations.

    add() and merge() update this accumulator; result() leaves it unchanged.
    An empty or all-zero-weight accumulator has no result.
    """

    def __init__(self):
        self._numerator = 0
        self._denominator = 0

    def add(self, value, weight):
        """Add one observation, rejecting negative weights."""
        if weight < 0:
            raise ValueError("weights must be non-negative")
        self._numerator += value * weight
        self._denominator += weight

    def merge(self, other):
        """Combine another WeightedMean's totals without changing it."""
        self._numerator += other._numerator
        self._denominator += other._denominator

    def result(self):
        """Return the current mean, rejecting zero total weight."""
        if self._denominator == 0:
            raise ValueError("total weight must be non-zero")
        return self._numerator / self._denominator


def weighted_mean(pairs):
    """Return sum(value * weight) / sum(weight) for an iterable of pairs.

    Consume the iterable once. Negative weights and zero total weight
    (including empty input) raise ValueError.
    """
    accumulator = WeightedMean()
    for value, weight in pairs:
        accumulator.add(value, weight)
    return accumulator.result()


def weighted_mean_many(groups):
    """Return a list with one weighted mean per group in ``groups``.

    Each group is any iterable of (value, weight) pairs accepted by
    weighted_mean, including one-shot generators. The outer iterable is
    also consumed once and may itself be a generator; an empty outer
    iterable yields an empty list. Errors from an individual group
    (negative weights or zero total weight) propagate unchanged.
    """
    return [weighted_mean(group) for group in groups]
