class WeightedMean:
    """Accumulate a weighted mean without retaining the input values."""

    def __init__(self):
        self._weighted_sum = 0
        self._total_weight = 0

    def add(self, value, weight):
        """Add one observation with a non-negative weight."""
        if weight < 0:
            raise ValueError("weights must be non-negative")
        self._weighted_sum += value * weight
        self._total_weight += weight

    def merge(self, other):
        """Combine another accumulator's totals without modifying it."""
        self._weighted_sum += other._weighted_sum
        self._total_weight += other._total_weight

    def result(self):
        """Return the current mean, raising if the total weight is zero."""
        if self._total_weight == 0:
            raise ValueError("total weight must be non-zero")
        return self._weighted_sum / self._total_weight


def weighted_mean(pairs):
    accumulator = WeightedMean()
    for value, weight in pairs:
        accumulator.add(value, weight)
    return accumulator.result()
