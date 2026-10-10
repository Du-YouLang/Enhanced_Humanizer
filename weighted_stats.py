def weighted_mean(pairs):
    values = list(pairs)
    return sum(value for value, weight in values) / len(values)
