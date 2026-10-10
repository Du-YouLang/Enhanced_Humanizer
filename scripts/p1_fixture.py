"""Preserved frozen synthetic task shared by P1 and P2."""

TASK='Fix weighted_mean in weighted_stats.py to compute sum(value * weight) / sum(weight). Handle any iterable of (value, weight), including generators; reject negative weights and zero total weight with ValueError. Read files, edit code, run python -m unittest -v, and make a Git commit. Do not edit test_weighted_stats.py or install dependencies or spawn subagents. Finish in one turn and report the commit/tests.'
SOURCE='def weighted_mean(pairs):\n    values = list(pairs)\n    return sum(value for value, weight in values) / len(values)\n'
TESTS='''import unittest
from weighted_stats import weighted_mean
class TestWeighted(unittest.TestCase):
    def test_weighting(self): self.assertAlmostEqual(weighted_mean([(2,1),(8,3)]),6.5)
    def test_generator(self): self.assertEqual(weighted_mean((p for p in [(2,1),(4,1)])),3)
    def test_negative(self):
        with self.assertRaises(ValueError): weighted_mean([(2,-1),(4,2)])
    def test_zero(self):
        with self.assertRaises(ValueError): weighted_mean([(1,0)])
    def test_empty(self):
        with self.assertRaises(ValueError): weighted_mean([])
'''
