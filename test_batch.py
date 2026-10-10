import unittest

from weighted_stats import weighted_mean, weighted_mean_many


class TestWeightedMeanMany(unittest.TestCase):
    def test_list_of_lists(self):
        self.assertEqual(
            weighted_mean_many([[(2, 1), (8, 3)], [(4, 1), (8, 1)]]),
            [6.5, 6],
        )

    def test_order_is_preserved(self):
        groups = [[(1, 1)], [(10, 1)], [(5, 1)]]
        self.assertEqual(weighted_mean_many(groups), [1, 10, 5])

    def test_empty_outer_iterable(self):
        self.assertEqual(weighted_mean_many([]), [])

    def test_empty_outer_generator(self):
        self.assertEqual(weighted_mean_many(group for group in []), [])

    def test_outer_generator(self):
        groups = (group for group in [[(2, 1), (8, 3)], [(4, 1), (8, 1)]])
        self.assertEqual(weighted_mean_many(groups), [6.5, 6])

    def test_inner_generators_consumed_once(self):
        consumed = []

        def group(pairs):
            for pair in pairs:
                consumed.append(pair)
                yield pair

        result = weighted_mean_many(
            [group([(2, 1), (8, 3)]), group([(4, 1), (8, 1)])]
        )
        self.assertEqual(result, [6.5, 6])
        self.assertEqual(consumed, [(2, 1), (8, 3), (4, 1), (8, 1)])

    def test_nested_generator_of_generators(self):
        def groups():
            yield (pair for pair in [(2, 1), (8, 3)])
            yield (pair for pair in [(4, 1), (8, 1)])

        self.assertEqual(weighted_mean_many(groups()), [6.5, 6])

    def test_single_group_matches_weighted_mean(self):
        group = [(2, 1), (8, 3), (4, 2)]
        self.assertEqual(weighted_mean_many([group]), [weighted_mean(group)])

    def test_negative_weight_propagates(self):
        with self.assertRaisesRegex(ValueError, "weights must be non-negative"):
            weighted_mean_many([[(2, 1)], [(4, -1)]])

    def test_zero_total_weight_propagates(self):
        with self.assertRaisesRegex(ValueError, "total weight must be non-zero"):
            weighted_mean_many([[(2, 1)], [(4, 0)]])

    def test_empty_group_propagates(self):
        with self.assertRaises(ValueError):
            weighted_mean_many([[(2, 1)], []])


if __name__ == "__main__":
    unittest.main()
