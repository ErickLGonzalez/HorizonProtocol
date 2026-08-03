"""H4-C: statistical smoke test. [HEURISTIC - located warning]

This is a smoke test, not a randomness certification; causal
independence != statistical quality.
"""
import unittest
from horizon.beacon_sim import build_full_beacon, statistical_sanity


class TestStatisticalSanity(unittest.TestCase):
    def test_frozen_beacon_bit_balance_in_window(self):
        cert, _ = build_full_beacon()
        res = statistical_sanity(bytes.fromhex(cert["beacon_value_hex"]))
        self.assertEqual(res["tag"], "HEURISTIC")
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["window"], [96, 160])
        self.assertGreaterEqual(res["popcount"], 96)
        self.assertLessEqual(res["popcount"], 160)

    def test_warning_present(self):
        res = statistical_sanity(b"\x00" * 32)
        self.assertIn("not a randomness certification", res["warning"])
        self.assertEqual(res["verdict"], "FAIL")  # all-zero fails the window


if __name__ == "__main__":
    unittest.main()
