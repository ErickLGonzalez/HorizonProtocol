"""H3-D: FTL floor control - RTT below light's round trip REJECTED. [SOUND]"""
import unittest
from horizon.distance import (P_CLAIM, VERIFIERS, min_round_trip_ns,
                              rtt_bound_witness)
from horizon.geometry import C_NM_PER_NS, dist2, min_light_time_ns


class TestFTLFloor(unittest.TestCase):
    def test_ftl_rtt_rejected_every_verifier(self):
        proc = 0  # "prover" claiming zero processing delay
        for vid, v in VERIFIERS.items():
            mrt = min_round_trip_ns(v, P_CLAIM)
            rtt = mrt - 1  # strictly below what light permits
            # spec framing: strictly below 2*min_light_time_ns
            self.assertLess(rtt, 2 * min_light_time_ns(v, P_CLAIM), vid)
            w = rtt_bound_witness(rtt, proc, v, P_CLAIM)
            self.assertEqual(w["verdict"], "REJECTED", vid)
            self.assertEqual(w["gate"], "ftl_floor", vid)
            # exact FTL witness: (c*dt)^2 < 4*d^2 - same physics as H1-E
            self.assertLess(w["lhs_c_dt_squared"], w["rhs_4_dist_squared_nm2"])
            self.assertEqual(w["rhs_4_dist_squared_nm2"], 4 * dist2(v, P_CLAIM))

    def test_min_round_trip_is_minimal(self):
        for v in VERIFIERS.values():
            t = min_round_trip_ns(v, P_CLAIM)
            d2x4 = 4 * dist2(v, P_CLAIM)
            self.assertGreaterEqual((C_NM_PER_NS * t) ** 2, d2x4)
            self.assertLess((C_NM_PER_NS * (t - 1)) ** 2, d2x4)
            self.assertLessEqual(t, 2 * min_light_time_ns(v, P_CLAIM))

    def test_negative_dt_rejected(self):
        w = rtt_bound_witness(10, 25, VERIFIERS["V1"], P_CLAIM)  # rtt < proc
        self.assertEqual(w["verdict"], "REJECTED")
        self.assertEqual(w["gate"], "ftl_floor")


if __name__ == "__main__":
    unittest.main()
