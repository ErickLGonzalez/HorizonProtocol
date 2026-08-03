"""H3-A: single-verifier RTT bounding - honest passes, distant fails. [SOUND]"""
import unittest
from horizon.distance import (P_CLAIM, PROC_NS, VERIFIERS, deadline_ns,
                              rtt_bound_witness)
from horizon.db_sim import DISTANT, DISTANT_POS, HONEST, run_session
from horizon.geometry import dist2


class TestSingleVerifierBounding(unittest.TestCase):
    def test_honest_prover_admitted_everywhere(self):
        sess = run_session(HONEST)
        for vid, v in VERIFIERS.items():
            w = rtt_bound_witness(sess["measurements"][vid], PROC_NS, v, P_CLAIM)
            self.assertEqual(w["verdict"], "ADMITTED", vid)
            self.assertGreaterEqual(w["lhs_c_dt_squared"],
                                    w["rhs_4_dist_squared_nm2"])
            self.assertLessEqual(sess["measurements"][vid],
                                 deadline_ns(v, P_CLAIM, PROC_NS))

    def test_distant_pos_is_farther_from_every_verifier(self):
        for vid, v in VERIFIERS.items():
            self.assertGreater(dist2(DISTANT_POS, v), dist2(P_CLAIM, v), vid)

    def test_distant_prover_rejected_everywhere(self):
        sess = run_session(DISTANT)
        for vid, v in VERIFIERS.items():
            rtt = sess["measurements"][vid]
            w = rtt_bound_witness(rtt, PROC_NS, v, P_CLAIM)
            self.assertEqual(w["verdict"], "REJECTED", vid)
            self.assertEqual(w["gate"], "deadline", vid)
            # the exact violated inequality
            self.assertGreater(rtt, w["deadline_ns"], vid)


if __name__ == "__main__":
    unittest.main()
