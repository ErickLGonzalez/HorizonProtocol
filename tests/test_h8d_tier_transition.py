"""H8-D: tier transition APPARATUS_LIMITED -> ADMITTED, and verifier hygiene. [SOUND]

The honest transition node is us-east-2 (Ohio, ~475 km from origin): its ~2.6 ms
one-way flight at fiber speed cannot be resolved by NTP-tier clocks (~5 ms error)
but IS resolved by PTP-tier clocks (~50 us). The co-located emitter (us-east-1,
zero flight distance) stays APPARATUS_LIMITED at every tier -- a node with no
time-of-flight can never be distance-attested, which is correct physics, not a
defect.
"""
import json
import os
import unittest

from horizon import build_frame
from horizon.build_frame import load_registry
from horizon.capture_verify import verify_capture

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


class TestTierTransition(unittest.TestCase):
    def setUp(self):
        _, self.reg, _ = load_registry()

    def _reg_at(self, tier):
        return {k: {**v, "u_ns": build_frame.TIERS[tier], "tier": tier}
                for k, v in self.reg.items()}

    def _verdict(self, tier, node_id):
        cap = _load(f"h8_capture_{tier.lower()}.json")
        res = verify_capture(cap, self._reg_at(tier))
        return {p["node_id"]: p["verdict"] for p in res["per_receipt"]}[node_id]

    def test_ohio_transitions_ntp_to_ptp(self):
        self.assertEqual(self._verdict("NTP", "us-east-2"), "APPARATUS_LIMITED")
        self.assertEqual(self._verdict("PTP", "us-east-2"), "ADMITTED")

    def test_colocated_emitter_never_resolved(self):
        # zero-flight node is apparatus-limited at every tier (correct physics)
        self.assertEqual(self._verdict("NTP", "us-east-1"), "APPARATUS_LIMITED")
        self.assertEqual(self._verdict("PTP", "us-east-1"), "APPARATUS_LIMITED")

    def test_distant_nodes_admitted_both_tiers(self):
        # flight >> clock error at both tiers
        for tier in ("NTP", "PTP"):
            self.assertEqual(self._verdict(tier, "eu-west-1"), "ADMITTED")

    def test_verifier_excludes_live_capture(self):
        import inspect

        import horizon.capture_verify as cv
        src = inspect.getsource(cv)
        self.assertNotIn("measure_now", src)


if __name__ == "__main__":
    unittest.main()
