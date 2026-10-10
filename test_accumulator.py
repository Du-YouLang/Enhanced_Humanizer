import unittest

from weighted_stats import WeightedMean, weighted_mean


class TestAccumulator(unittest.TestCase):
    def test_incremental_add_and_result(self):
        accumulator = WeightedMean()
        accumulator.add(2, 1)
        self.assertEqual(accumulator.result(), 2)
        accumulator.add(8, 3)
        self.assertEqual(accumulator.result(), 6.5)
        self.assertEqual(accumulator.result(), 6.5)
        accumulator.add(100, 0)
        self.assertEqual(accumulator.result(), 6.5)

    def test_negative_weight_leaves_accumulator_unchanged(self):
        accumulator = WeightedMean()
        accumulator.add(2, 1)
        with self.assertRaisesRegex(ValueError, "weights must be non-negative"):
            accumulator.add(8, -1)
        self.assertEqual(accumulator.result(), 2)

    def test_empty_and_zero_weight(self):
        accumulator = WeightedMean()
        with self.assertRaisesRegex(ValueError, "total weight must be non-zero"):
            accumulator.result()
        accumulator.add(10, 0)
        with self.assertRaisesRegex(ValueError, "total weight must be non-zero"):
            accumulator.result()
        accumulator.add(4, 2)
        self.assertEqual(accumulator.result(), 4)

    def test_merge_uses_totals_and_preserves_source(self):
        left = WeightedMean()
        right = WeightedMean()
        left.add(2, 1)
        right.add(8, 3)
        right.add(4, 2)
        left.merge(right)
        self.assertEqual(left.result(), weighted_mean([(2, 1), (8, 3), (4, 2)]))
        self.assertEqual(right.result(), 6.4)
        right.add(100, 1)
        self.assertEqual(left.result(), 34 / 6)

    def test_merge_empty_and_self(self):
        accumulator = WeightedMean()
        accumulator.merge(WeightedMean())
        with self.assertRaises(ValueError):
            accumulator.result()
        source = WeightedMean()
        source.add(3, 2)
        accumulator.merge(source)
        accumulator.merge(WeightedMean())
        accumulator.merge(accumulator)
        accumulator.add(9, 2)
        self.assertEqual(accumulator.result(), 5)


if __name__ == "__main__":
    unittest.main()
