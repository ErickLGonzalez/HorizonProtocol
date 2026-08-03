"""H3-C: the honest break - classical collusion DEFEATS position
verification (Chandran-Goyal-Moriarty-Ostrovsky 2009). [SOUND]

The colluder pair MUST succeed. A run where the attack fails is a test
FAILURE: it would mean the simulation is dishonest about the known
impossibility of classical position verification against collusion.
"""
import unittest
from horizon.distance import P_CLAIM, PROC_NS, VERIFIERS, multilateration
from horizon.db_sim import (COLLUDER_COVERAGE, COLLUDER_PAIR,
                            COLLUDER_POSITIONS, run_session)
from horizon.geometry import dist2


class TestCollusionBreak(unittest.TestCase):
    def test_colluders_strictly_closer_to_covered_verifiers(self):
        for vid, v in VERIFIERS.items():
            agent = COLLUDER_POSITIONS[COLLUDER_COVERAGE[vid]]
            self.assertLess(dist2(agent, v), dist2(P_CLAIM, v), vid)

    def test_no_agent_is_at_the_claimed_position(self):
        for pos in COLLUDER_POSITIONS.values():
            self.assertNotEqual(tuple(pos), tuple(P_CLAIM))
            self.assertGreater(dist2(pos, P_CLAIM), 0)

    def test_attack_succeeds_expected(self):
        sess = run_session(COLLUDER_PAIR)
        self.assertTrue(all(sess["strictly_closer_check"].values()))
        res = multilateration(sess["measurements"], PROC_NS, P_CLAIM)
        # every verifier's bound satisfied although no prover is at P_CLAIM
        self.assertEqual(res["verdict"], "ADMITTED",
                         "collusion attack unexpectedly failed - the "
                         "simulation would be dishonest about the known "
                         "classical impossibility (CGMO 2009)")
        self.assertEqual(res["failing_verifiers"], [])
        for vid in VERIFIERS:
            self.assertEqual(res["per_verifier"][vid]["verdict"], "ADMITTED")

    def test_gate_verdict_is_expected_attack_success(self):
        sess = run_session(COLLUDER_PAIR)
        res = multilateration(sess["measurements"], PROC_NS, P_CLAIM)
        verdict = ("EXPECTED_ATTACK_SUCCESS" if res["verdict"] == "ADMITTED"
                   else "FAIL")
        self.assertEqual(verdict, "EXPECTED_ATTACK_SUCCESS")


if __name__ == "__main__":
    unittest.main()
