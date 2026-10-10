import unittest

from weighted_stats import WeightedMean, weighted_mean, weighted_mean_many


class TestBatchWeightedMean(unittest.TestCase):
    def test_multiple_groups(self):
        groups = [[(2, 1), (8, 3)], [(4, 1)], [(1, 2), (2, 2)]]
        self.assertEqual(weighted_mean_many(groups), [6.5, 4.0, 1.5])

    def test_returns_list(self):
        self.assertIsInstance(weighted_mean_many([]), list)
        self.assertIsInstance(weighted_mean_many([[(2, 1)]]), list)

    def test_empty_outer_iterable(self):
        self.assertEqual(weighted_mean_many([]), [])
        self.assertEqual(weighted_mean_many(iter([])), [])

    def test_generator_outer_iterable(self):
        groups = (group for group in [[(2, 1), (8, 3)], [(4, 1)]])
        self.assertEqual(weighted_mean_many(groups), [6.5, 4.0])

    def test_generator_groups(self):
        groups = [
            (pair for pair in [(2, 1), (8, 3)]),
            (pair for pair in [(4, 1)]),
        ]
        self.assertEqual(weighted_mean_many(groups), [6.5, 4.0])

    def test_matches_weighted_mean_per_group(self):
        groups = [[(2, 1), (8, 3), (4, 2)], [(5, 0), (7, 2)]]
        expected = [weighted_mean(group) for group in groups]
        self.assertEqual(weighted_mean_many(groups), expected)

    def test_negative_weight_raises(self):
        with self.assertRaises(ValueError):
            weighted_mean_many([[(2, 1)], [(4, -1)]])

    def test_empty_group_raises(self):
        with self.assertRaises(ValueError):
            weighted_mean_many([[(2, 1)], []])

    def test_zero_total_weight_raises(self):
        with self.assertRaises(ValueError):
            weighted_mean_many([[(1, 0)]])

    def test_accumulator_still_independent(self):
        accumulator = WeightedMean()
        accumulator.add(2, 1)
        self.assertEqual(weighted_mean_many([[(8, 3)]]), [8.0])
        self.assertEqual(accumulator.result(), 2)


if __name__ == "__main__":
    unittest.main()
