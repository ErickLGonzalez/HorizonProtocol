"""H8-E: trust boundary + real-fast-signal regression tests. [SOUND]

Regression coverage for the two bugs found and fixed during review of the
originally-shipped `horizon/capture_verify.py` (see its module docstring
erratum): (1) using the conservative c_eff bound as if it were an absolute
speed ceiling, wrongly REJECTING a genuine, honest signal that happened to
travel faster than 0.6c but still well below vacuum c; (2) reading `c_eff`
directly from the untrusted `capture` object being classified, letting a
forger declare a superluminal bound to force an otherwise-impossible receipt
ADMITTED.
"""
import json
import os
import unittest

from horizon.build_frame import load_registry
from horizon.capture_verify import classify, verify_capture
from horizon.geometry import C_NM_PER_NS

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


class TestTrustBoundary(unittest.TestCase):
    def setUp(self):
        _, self.reg, _ = load_registry()

    def test_declared_c_eff_in_capture_has_no_effect_on_classification(self):
        # a forger declaring a superluminal c_eff inside the capture blob
        # must not change a single verdict: c_eff is trusted caller input,
        # never read from the untrusted capture itself.
        cap = _load("h8_capture_ntp.json")
        honest = verify_capture(cap, self.reg)
        forged = dict(cap)
        forged["c_eff"] = [10 ** 9, 1]  # declared faster than vacuum c
        evil = verify_capture(forged, self.reg)
        self.assertEqual([p["verdict"] for p in honest["per_receipt"]],
                         [p["verdict"] for p in evil["per_receipt"]])

    def test_declared_c_eff_cannot_admit_an_otherwise_impossible_receipt(self):
        # construct a receipt that is impossibly early for its true distance
        # (below the vacuum floor even with full clock-uncertainty benefit),
        # then try to force ADMITTED by declaring a superluminal c_eff.
        p0 = (0, 0, 0)
        p1 = (500_000 * 1_000_000_000, 0, 0)  # 500 km
        too_early = 100  # nanoseconds - far below any physical floor
        res = classify(0, p0, too_early, p1, u_ns=1000,
                       c_eff_num=10 ** 9, c_eff_den=1)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["reason"], "below_vacuum_floor")

    def test_real_fast_signal_below_conservative_bound_is_not_rejected(self):
        # a signal genuinely travelling at 0.8c (faster than the conservative
        # 3/5 c_eff fiber bound, but well below vacuum c - honest, not
        # forged) must never be REJECTED merely for beating the conservative
        # bound; a sufficiently precise tier should ADMIT it outright.
        d_m = 475_000
        p0 = (0, 0, 0)
        p1 = (d_m * 1_000_000_000, 0, 0)
        t_08c = int((d_m * 1_000_000_000) / (0.8 * C_NM_PER_NS))
        for u_ns in (1_000, 50_000):
            res = classify(0, p0, t_08c, p1, u_ns)
            self.assertEqual(res["verdict"], "ADMITTED",
                             f"u_ns={u_ns}: {res}")

    def test_genuinely_impossible_arrival_still_rejected_at_tight_tiers(self):
        # sanity check the fix didn't just make everything permissive: an
        # arrival faster than vacuum c is still REJECTED when the tier's
        # clock is precise enough to resolve the discrepancy.
        d_m = 475_000
        p0 = (0, 0, 0)
        p1 = (d_m * 1_000_000_000, 0, 0)
        t_ftl = int((d_m * 1_000_000_000) / (1.5 * C_NM_PER_NS))
        for u_ns in (1_000, 50_000):
            res = classify(0, p0, t_ftl, p1, u_ns)
            self.assertEqual(res["verdict"], "REJECTED",
                             f"u_ns={u_ns}: {res}")


if __name__ == "__main__":
    unittest.main()
