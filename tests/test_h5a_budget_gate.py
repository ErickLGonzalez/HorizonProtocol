"""H5-A: uncertainty-budgeted gate math - boundary correctness. [SOUND]"""
import unittest

from horizon.measure import (C_EFF_DEN, C_EFF_NUM, RESOLVE_MARGIN_NS,
                             budget_witness, classify_measured_receipt,
                             min_transit_time_ns_eff)

P0 = (0, 0, 0)
P1 = (30_000_000_000_000, 0, 0)  # 30 km along x
U_NS = 50_000


class TestBudgetGate(unittest.TestCase):
    def test_exactly_at_c_eff_limit_with_zero_offset_is_admitted(self):
        required = min_transit_time_ns_eff(P0, P1)
        # zero offset from the c_eff limit itself; U alone must clear the
        # resolve margin for this to be a clean, unambiguous ADMIT
        self.assertGreater(U_NS, RESOLVE_MARGIN_NS)
        res = classify_measured_receipt(0, P0, required, P1, U_NS)
        self.assertEqual(res["verdict"], "ADMITTED")
        self.assertEqual(res["witness"]["margin_ns"], U_NS)
        self.assertTrue(res["witness"]["consistent"])

    def test_impossibly_early_beyond_budget_rejected(self):
        required = min_transit_time_ns_eff(P0, P1)
        t_recv = required - U_NS - RESOLVE_MARGIN_NS - 1
        res = classify_measured_receipt(0, P0, t_recv, P1, U_NS)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertLess(res["witness"]["margin_ns"], -RESOLVE_MARGIN_NS)
        self.assertFalse(res["witness"]["consistent"])

    def test_inside_resolve_margin_is_apparatus_limited(self):
        required = min_transit_time_ns_eff(P0, P1)
        t_recv = required - U_NS  # margin_ns == 0 exactly
        res = classify_measured_receipt(0, P0, t_recv, P1, U_NS)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertEqual(res["witness"]["margin_ns"], 0)

    def test_margin_boundary_is_inclusive_of_apparatus_limited(self):
        required = min_transit_time_ns_eff(P0, P1)
        just_inside = required - U_NS + RESOLVE_MARGIN_NS  # margin == +MARGIN
        just_outside = required - U_NS + RESOLVE_MARGIN_NS + 1  # margin == MARGIN+1
        res_inside = classify_measured_receipt(0, P0, just_inside, P1, U_NS)
        res_outside = classify_measured_receipt(0, P0, just_outside, P1, U_NS)
        self.assertEqual(res_inside["verdict"], "APPARATUS_LIMITED")
        self.assertEqual(res_outside["verdict"], "ADMITTED")

    def test_zero_distance_requires_zero_transit_time(self):
        self.assertEqual(min_transit_time_ns_eff(P0, P0), 0)

    def test_consistent_flag_matches_margin_sign(self):
        w = budget_witness(0, P0, min_transit_time_ns_eff(P0, P1), P1, 0)
        self.assertTrue(w["consistent"])
        self.assertGreaterEqual(w["margin_ns"], 0)

    def test_frozen_c_eff_is_slower_than_vacuum(self):
        # c_eff = c * 3/5 must be strictly slower than vacuum c, so the
        # eff-transit floor is strictly looser in *time required*, i.e.
        # strictly larger, than the vacuum light-time floor for any
        # nonzero separation
        from horizon.geometry import min_light_time_ns
        vac = min_light_time_ns(P0, P1)
        eff = min_transit_time_ns_eff(P0, P1)
        self.assertLess(C_EFF_NUM, C_EFF_DEN)
        self.assertGreater(eff, vac)


if __name__ == "__main__":
    unittest.main()
