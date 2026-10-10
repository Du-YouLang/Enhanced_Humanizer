import unittest

from weighted_stats import WeightedMean, weighted_mean


class TestAccumulator(unittest.TestCase):
    def test_incremental_add(self):
        accumulator = WeightedMean()
        accumulator.add(2, 1)
        self.assertEqual(accumulator.result(), 2)
        accumulator.add(8, 3)
        self.assertEqual(accumulator.result(), 6.5)
        accumulator.add(100, 0)
        self.assertEqual(accumulator.result(), 6.5)

    def test_merge(self):
        left = WeightedMean()
        left.add(2, 1)
        right = WeightedMean()
        right.add(8, 3)
        right.add(4, 2)
        left.merge(right)
        self.assertEqual(left.result(), weighted_mean([(2, 1), (8, 3), (4, 2)]))
        self.assertEqual(right.result(), 6.4)
        left.add(2, 2)
        self.assertEqual(left.result(), 4.75)

    def test_merge_empty(self):
        accumulator = WeightedMean()
        accumulator.add(5, 2)
        accumulator.merge(WeightedMean())
        self.assertEqual(accumulator.result(), 5)
        empty = WeightedMean()
        empty.merge(accumulator)
        self.assertEqual(empty.result(), 5)

    def test_self_merge(self):
        accumulator = WeightedMean()
        accumulator.add(7, 2)
        accumulator.merge(accumulator)
        accumulator.add(3, 4)
        self.assertEqual(accumulator.result(), 5)

    def test_negative_weight_does_not_change_result(self):
        accumulator = WeightedMean()
        accumulator.add(2, 1)
        with self.assertRaises(ValueError):
            accumulator.add(8, -3)
        self.assertEqual(accumulator.result(), 2)

    def test_zero_total_weight(self):
        accumulator = WeightedMean()
        with self.assertRaises(ValueError):
            accumulator.result()
        accumulator.add(5, 0)
        accumulator.merge(WeightedMean())
        with self.assertRaises(ValueError):
            accumulator.result()


if __name__ == "__main__":
    unittest.main()
