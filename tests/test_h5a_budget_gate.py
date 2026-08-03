"""H5-A: uncertainty-budgeted gate math - dual-floor boundary
correctness. [SOUND]"""
import unittest

from horizon.geometry import min_light_time_ns
from horizon.measure import (C_EFF_DEN, C_EFF_NUM, classify_measured_receipt,
                             min_transit_time_ns_eff)

P0 = (0, 0, 0)
P1 = (30_000_000_000_000, 0, 0)  # 30 km along x
U_NS = 50_000


class TestBudgetGate(unittest.TestCase):
    def test_at_typical_floor_with_zero_offset_is_admitted(self):
        typical_floor = min_transit_time_ns_eff(P0, P1)
        res = classify_measured_receipt(0, P0, typical_floor, P1, 0)
        self.assertEqual(res["verdict"], "ADMITTED")
        self.assertEqual(res["witness"]["dt_adjusted_ns"], typical_floor)

    def test_below_vacuum_floor_even_with_u_is_rejected(self):
        vacuum_floor = min_light_time_ns(P0, P1)
        t_recv = vacuum_floor - U_NS - 1  # dt_adjusted = vacuum_floor - 1
        res = classify_measured_receipt(0, P0, t_recv, P1, U_NS)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertLess(res["witness"]["dt_adjusted_ns"],
                        res["witness"]["vacuum_floor_ns"])

    def test_between_floors_is_apparatus_limited(self):
        vacuum_floor = min_light_time_ns(P0, P1)
        typical_floor = min_transit_time_ns_eff(P0, P1)
        self.assertLess(vacuum_floor, typical_floor)
        midpoint = (vacuum_floor + typical_floor) // 2
        res = classify_measured_receipt(0, P0, midpoint, P1, 0)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        w = res["witness"]
        self.assertGreaterEqual(w["dt_adjusted_ns"], w["vacuum_floor_ns"])
        self.assertLess(w["dt_adjusted_ns"], w["typical_floor_ns"])

    def test_exactly_at_vacuum_floor_is_not_rejected(self):
        vacuum_floor = min_light_time_ns(P0, P1)
        res = classify_measured_receipt(0, P0, vacuum_floor, P1, 0)
        self.assertNotEqual(res["verdict"], "REJECTED")

    def test_one_ns_below_vacuum_floor_is_rejected(self):
        vacuum_floor = min_light_time_ns(P0, P1)
        res = classify_measured_receipt(0, P0, vacuum_floor - 1, P1, 0)
        self.assertEqual(res["verdict"], "REJECTED")

    def test_clock_uncertainty_can_move_a_receipt_out_of_rejected(self):
        vacuum_floor = min_light_time_ns(P0, P1)
        # 1 ns below the vacuum floor with no uncertainty: REJECTED
        rejected = classify_measured_receipt(0, P0, vacuum_floor - 1, P1, 0)
        self.assertEqual(rejected["verdict"], "REJECTED")
        # the same raw receipt, but with enough declared uncertainty to
        # cover the 1 ns shortfall, is no longer rejectable
        admitted_or_limited = classify_measured_receipt(0, P0, vacuum_floor - 1,
                                                        P1, 1)
        self.assertNotEqual(admitted_or_limited["verdict"], "REJECTED")

    def test_zero_distance_requires_zero_transit_time(self):
        self.assertEqual(min_light_time_ns(P0, P0), 0)
        self.assertEqual(min_transit_time_ns_eff(P0, P0), 0)

    def test_frozen_c_eff_is_slower_than_vacuum(self):
        # c_eff = c * 3/5 must be strictly slower than vacuum c, so its
        # transit-time floor is strictly LARGER (takes longer) than the
        # vacuum floor for any nonzero separation - this is the gap that
        # becomes the APPARATUS_LIMITED band
        vacuum_floor = min_light_time_ns(P0, P1)
        typical_floor = min_transit_time_ns_eff(P0, P1)
        self.assertLess(C_EFF_NUM, C_EFF_DEN)
        self.assertGreater(typical_floor, vacuum_floor)


if __name__ == "__main__":
    unittest.main()
