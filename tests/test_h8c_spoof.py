"""H8-C: live spoof control -> REJECTED. [SOUND]"""
import json
import os
import unittest

from horizon.build_frame import load_registry
from horizon.capture_verify import verify_capture

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


class TestSpoof(unittest.TestCase):
    def setUp(self):
        _, self.reg, _ = load_registry()

    def test_rogue_key_spoof_rejected(self):
        cap = _load("h8_capture_spoof.json")
        res = verify_capture(cap, self.reg)
        self.assertEqual(res["aggregate"], "REJECTED")
        # the spoofed us-west-2 receipt fails the signature gate
        spoofed = [p for p in res["per_receipt"] if p["node_id"] == "us-west-2"][0]
        self.assertEqual(spoofed["verdict"], "REJECTED")
        self.assertEqual(spoofed["witness"]["gate"], "signature")


if __name__ == "__main__":
    unittest.main()
