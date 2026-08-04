"""H8-B: honest capture -> ADMITTED or APPARATUS_LIMITED, never spurious REJECT. [SOUND]"""
import json
import os
import unittest

from horizon.build_frame import load_registry
from horizon.capture_verify import verify_capture

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


class TestHonest(unittest.TestCase):
    def setUp(self):
        _, self.reg, _ = load_registry()

    def test_honest_ntp_no_spurious_reject(self):
        cap = _load("h8_capture_ntp.json")
        res = verify_capture(cap, self.reg)
        for p in res["per_receipt"]:
            self.assertIn(p["verdict"], ("ADMITTED", "APPARATUS_LIMITED"))

    def test_ntp_is_apparatus_limited_somewhere(self):
        # at NTP tier, the near-zero-distance emitter cannot be resolved
        cap = _load("h8_capture_ntp.json")
        res = verify_capture(cap, self.reg)
        self.assertIn("APPARATUS_LIMITED",
                      [p["verdict"] for p in res["per_receipt"]])


if __name__ == "__main__":
    unittest.main()
