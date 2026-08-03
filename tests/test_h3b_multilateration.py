"""H3-B: 4-verifier multilateration - honest ADMITTED, decoy REJECTED at V3. [SOUND]"""
import unittest
from horizon.distance import P_CLAIM, PROC_NS, VERIFIERS, multilateration
from horizon.db_sim import DECOY, DECOY_POS, HONEST, run_session
from horizon.geometry import dist2


class TestMultilateration(unittest.TestCase):
    def test_honest_admitted(self):
        sess = run_session(HONEST)
        res = multilateration(sess["measurements"], PROC_NS, P_CLAIM)
        self.assertEqual(res["verdict"], "ADMITTED")
        self.assertEqual(res["failing_verifiers"], [])

    def test_decoy_geometry(self):
        # decoy satisfies V1's bound side (closer to V1) but is strictly
        # farther from V3 than the claim
        self.assertLess(dist2(DECOY_POS, VERIFIERS["V1"]),
                        dist2(P_CLAIM, VERIFIERS["V1"]))
        self.assertGreater(dist2(DECOY_POS, VERIFIERS["V3"]),
                           dist2(P_CLAIM, VERIFIERS["V3"]))

    def test_decoy_rejected_naming_v3(self):
        sess = run_session(DECOY)
        res = multilateration(sess["measurements"], PROC_NS, P_CLAIM)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["failing_verifiers"], ["V3"])
        w = res["per_verifier"]["V3"]
        self.assertEqual(w["gate"], "deadline")
        self.assertGreater(w["rtt_ns"], w["deadline_ns"])  # exact integers
        self.assertEqual(res["per_verifier"]["V1"]["verdict"], "ADMITTED")

    def test_verifier_is_standalone(self):
        import inspect
        import horizon.distance as d
        self.assertNotIn("db_sim", inspect.getsource(d))
        self.assertNotIn("simulate", inspect.getsource(d))


if __name__ == "__main__":
    unittest.main()
