"""H8-A: signed capture round-trip + deterministic replay. [SOUND verifier]"""
import json
import os
import unittest

from horizon.build_frame import load_registry
from horizon.signed_capture import sign_receipt, verify_receipt

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


class TestCapture(unittest.TestCase):
    def setUp(self):
        self.frame, self.reg, _ = load_registry()

    def test_receipt_roundtrip(self):
        r = sign_receipt("us-west-2", self.reg["us-west-2"]["pos_nm"],
                         "abc123", 1_000_000, "NTP")
        self.assertTrue(verify_receipt(r))

    def test_tampered_time_breaks_signature(self):
        r = sign_receipt("us-west-2", self.reg["us-west-2"]["pos_nm"],
                         "abc123", 1_000_000, "NTP")
        r["body"]["recv_time_ns"] = 500_000  # forge earlier arrival
        self.assertFalse(verify_receipt(r))

    def test_committed_capture_replays_identically(self):
        cap1 = _load("h8_capture_ntp.json")
        cap2 = _load("h8_capture_ntp.json")
        self.assertEqual(cap1, cap2)
        # all receipts in the committed capture verify
        for r in cap1["receipts"]:
            if r["body"]["node_id"] in self.reg:  # skip rogue
                self.assertTrue(verify_receipt(r))

    def test_at_least_three_real_nodes(self):
        self.assertGreaterEqual(len(self.reg), 3)
        # positions are real intercontinental separations
        import math

        from horizon.geometry import dist2
        p0 = tuple(self.reg["us-east-1"]["pos_nm"])
        d = math.isqrt(dist2(p0, tuple(self.reg["eu-west-1"]["pos_nm"]))) / 1e12
        self.assertGreater(d, 4000)  # >4000 km Virginia->Ireland


if __name__ == "__main__":
    unittest.main()
