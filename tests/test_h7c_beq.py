"""H7-C: bounded-entanglement security tracker (exact fractions). [SOUND]"""
import unittest
from fractions import Fraction
from horizon.beq import (adversary_success_bound, entanglement_threshold,
                         beq_verdict)


class TestBEQ(unittest.TestCase):
    def test_adversary_bound_is_exact_fraction(self):
        b = adversary_success_bound(10, 1, 2)  # (1/2)^10
        self.assertEqual(b, Fraction(1, 1024))

    def test_bound_decays_exponentially(self):
        b5 = adversary_success_bound(5, 3, 4)
        b10 = adversary_success_bound(10, 3, 4)
        self.assertLess(b10, b5)

    def test_invalid_gap_rejected(self):
        with self.assertRaises(ValueError):
            adversary_success_bound(10, 3, 2)  # >1

    def test_threshold_linear(self):
        thr = entanglement_threshold(73)
        self.assertEqual(thr["Q_secure_linear"], 73)

    def test_verdict_meets_target_at_sufficient_rounds(self):
        v = beq_verdict(73, 3, 4)  # (3/4)^73 <= 1e-9
        self.assertEqual(v["verdict"], "CONDITIONAL_BE_Q")
        self.assertTrue(v["meets_target"])

    def test_verdict_insufficient_at_few_rounds(self):
        v = beq_verdict(10, 3, 4)
        self.assertEqual(v["verdict"], "INSUFFICIENT_ROUNDS")
        self.assertFalse(v["meets_target"])

    def test_conditional_label_present(self):
        v = beq_verdict(73, 3, 4)
        self.assertIn("bounded", v["conditional_on"])
        self.assertIn("CGMO2009 (classical impossibility)", v["citations"])


if __name__ == "__main__":
    unittest.main()
