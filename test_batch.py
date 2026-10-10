import unittest

from weighted_stats import weighted_mean_many


class TestWeightedMeanMany(unittest.TestCase):
    def test_list_of_groups(self):
        self.assertEqual(
            weighted_mean_many([[(2, 1), (8, 3)], [(2, 1), (4, 1)]]),
            [6.5, 3],
        )

    def test_preserves_group_order(self):
        groups = [[(1, 1)], [(10, 1), (20, 1)], [(3, 2)]]
        self.assertEqual(weighted_mean_many(groups), [1, 15, 3])

    def test_outer_iterable_generator(self):
        outer = (group for group in [[(2, 1), (4, 1)], [(5, 5)]])
        self.assertEqual(weighted_mean_many(outer), [3, 5])

    def test_inner_generators(self):
        def group(values):
            return ((value, weight) for value, weight in values)

        groups = [group([(2, 1), (8, 3)]), group([(4, 2)])]
        self.assertEqual(weighted_mean_many(groups), [6.5, 4])

    def test_empty_outer_iterable(self):
        self.assertEqual(weighted_mean_many([]), [])
        self.assertEqual(weighted_mean_many(iter([])), [])

    def test_empty_outer_generator(self):
        self.assertEqual(weighted_mean_many(group for group in []), [])

    def test_negative_weight_propagates(self):
        with self.assertRaisesRegex(ValueError, "weights must be non-negative"):
            weighted_mean_many([[(2, 1)], [(8, -1), (4, 2)]])

    def test_zero_weight_group_propagates(self):
        with self.assertRaisesRegex(ValueError, "total weight must be non-zero"):
            weighted_mean_many([[(2, 1)], [(1, 0)]])


if __name__ == "__main__":
    unittest.main()
