import unittest
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
