"""H8-E: trust boundary + real-fast-signal regression tests. [SOUND]

Regression coverage for the bugs found and fixed during review of
`horizon/capture_verify.py` (see its module docstring erratums 1-4):
(1) using the conservative c_eff bound as if it were an absolute speed
ceiling, wrongly REJECTING a genuine, honest signal that happened to travel
faster than 0.6c but still well below vacuum c, and reading `c_eff`
directly from the untrusted `capture` object rather than trusted caller
input; (2) the claimed emission time/position were never bound into what a
receipt actually signs, letting an attacker pair a legitimately-signed
receipt with a self-chosen `t0_ns`/`p0_nm`; (3) a negative raw elapsed time
was REJECTED before the declared clock uncertainty was applied in the
claimant's favor; (4) a capture with no receipts, or with the same node's
receipt repeated, could reach a non-REJECTED aggregate, and no coverage
check existed for a caller that requires a specific node set.
"""
import copy
import json
import os
import unittest

from horizon.build_frame import load_registry
from horizon.capture_verify import bound_event_hash, classify, verify_capture
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

    def test_tampering_claimed_emission_after_signing_is_rejected(self):
        # a legitimately-signed capture whose t0_ns/p0_nm are changed after
        # the fact (e.g. to claim emission from the receiving node's own
        # position, trivially satisfying the light-cone gate for any
        # receipt) must be REJECTED - the receipts no longer match the
        # bound event hash for the new claim.
        cap = _load("h8_capture_ntp.json")
        forged = copy.deepcopy(cap)
        forged["p0_nm"] = list(self.reg["us-west-2"]["pos_nm"])  # co-locate with a receiver
        res = verify_capture(forged, self.reg)
        self.assertEqual(res["aggregate"], "REJECTED")
        self.assertTrue(all(p["witness"].get("gate") == "event_binding"
                            for p in res["per_receipt"]))

    def test_tampering_claimed_emission_time_after_signing_is_rejected(self):
        cap = _load("h8_capture_ntp.json")
        forged = copy.deepcopy(cap)
        forged["t0_ns"] = cap["t0_ns"] - 10 ** 9  # claim an earlier emission
        res = verify_capture(forged, self.reg)
        self.assertEqual(res["aggregate"], "REJECTED")
        self.assertTrue(all(p["witness"].get("gate") == "event_binding"
                            for p in res["per_receipt"]))

    def test_bound_event_hash_changes_with_the_claim(self):
        h1 = bound_event_hash("payload123", 0, (0, 0, 0))
        h2 = bound_event_hash("payload123", 0, (1, 0, 0))
        h3 = bound_event_hash("payload123", 1, (0, 0, 0))
        self.assertNotEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_empty_capture_rejected(self):
        cap = _load("h8_capture_ntp.json")
        empty = {**cap, "receipts": []}
        res = verify_capture(empty, self.reg)
        self.assertEqual(res["aggregate"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "nonempty_receipts")

    def test_duplicated_single_receipt_rejected(self):
        # a single valid receipt, repeated, must not manufacture apparent
        # multi-node corroboration.
        cap = _load("h8_capture_ntp.json")
        one = copy.deepcopy(cap)
        one["receipts"] = [one["receipts"][0], one["receipts"][0]]
        res = verify_capture(one, self.reg)
        self.assertEqual(res["aggregate"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "distinct_sources")

    def test_single_real_node_capture_rejected_under_required_coverage(self):
        # a single genuinely-valid receipt from one real node, with no
        # tampering at all, must still be REJECTED once the trusted caller
        # requires full coverage of the known registry (H8's own "genuine
        # multi-node capture" claim, enforced by scripts/run_h8.py).
        cap = _load("h8_capture_ntp.json")
        one = copy.deepcopy(cap)
        one["receipts"] = [one["receipts"][0]]
        res = verify_capture(one, self.reg, required_node_ids=set(self.reg.keys()))
        self.assertEqual(res["aggregate"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "node_coverage")
        # ...but is otherwise a perfectly valid single-node observation
        # when the caller does not require full coverage.
        res_uncovered = verify_capture(one, self.reg)
        self.assertNotEqual(res_uncovered.get("witness", {}).get("gate"), "node_coverage")

    def test_negative_raw_dt_within_clock_budget_not_spuriously_rejected(self):
        # co-located node, raw dt slightly negative purely from clock skew
        # within the declared u_ns budget - must not be REJECTED outright;
        # the adjusted time is comfortably non-negative.
        res = classify(1_000_000, (0, 0, 0), 999_999, (0, 0, 0), u_ns=10)
        self.assertNotEqual(res["verdict"], "REJECTED")

    def test_negative_raw_dt_beyond_clock_budget_still_rejected(self):
        # genuinely impossible even with the full clock-uncertainty benefit
        d_m = 475_000
        p0 = (0, 0, 0)
        p1 = (d_m * 1_000_000_000, 0, 0)
        res = classify(10 ** 9, p0, 0, p1, u_ns=10)  # arrives ~1s "before" emission
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["reason"], "below_vacuum_floor")


if __name__ == "__main__":
    unittest.main()
