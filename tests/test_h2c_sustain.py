"""H2-C: full sustained run - schedule, windows, chain, hash chain. [SOUND]"""
import unittest
from horizon.commitment import (DT_RESP_NS, DT_ROUND_NS, K_SUSTAIN, SITE_1,
                                SITE_2, isolation_gate, response_in_window,
                                sustained_isolation_gate, verify_reveal,
                                verify_transcript_chain)
from horizon.commit_sim import HONEST, run_session


class TestSustainedRun(unittest.TestCase):
    def setUp(self):
        self.sess = run_session(HONEST, b=1)

    def test_schedule_and_windows(self):
        for rec in self.sess["rounds"]:
            self.assertEqual(rec["t_challenge_ns"], rec["k"] * DT_ROUND_NS)
            w = response_in_window(rec["t_challenge_ns"], rec["t_response_ns"],
                                   DT_RESP_NS)
            self.assertEqual(w["verdict"], "ADMITTED")

    def test_sites_alternate(self):
        for rec in self.sess["rounds"]:
            expect = SITE_1 if rec["k"] % 2 == 0 else SITE_2
            self.assertEqual(tuple(rec["site_nm"]), expect)

    def test_per_round_isolation(self):
        for _ in self.sess["rounds"]:
            self.assertEqual(
                isolation_gate(SITE_1, SITE_2, DT_RESP_NS)["verdict"], "PASS")

    def test_cross_round_isolation(self):
        # the frozen schedule must ALSO be isolated across consecutive
        # rounds at alternating sites, not just within a single window
        res = sustained_isolation_gate(SITE_1, SITE_2, DT_ROUND_NS, DT_RESP_NS)
        self.assertEqual(res["verdict"], "PASS")
        self.assertLess(res["dt_round_plus_resp_ns"], res["one_way_light_time_ns"])

    def test_chain_verifies_at_reveal(self):
        res = verify_reveal(self.sess["rounds"], self.sess["reveal"]["b"],
                            self.sess["reveal"]["secrets"], K_SUSTAIN)
        self.assertEqual(res["verdict"], "ADMITTED")

    def test_transcript_hash_chain(self):
        res = verify_transcript_chain(self.sess["rounds"],
                                      self.sess["transcript_hashes"])
        self.assertEqual(res["verdict"], "ADMITTED")

    def test_binding_duration_recorded(self):
        self.assertEqual(self.sess["binding_duration_ns"],
                         (K_SUSTAIN + 1) * DT_ROUND_NS)
        self.assertGreater(self.sess["binding_duration_ns"], 0)

    def test_determinism(self):
        again = run_session(HONEST, b=1)
        self.assertEqual(self.sess, again)

    def test_verifier_is_standalone(self):
        # trusted-path hygiene: commitment.py must not import the simulator
        import inspect
        import horizon.commitment as c
        self.assertNotIn("commit_sim", inspect.getsource(c))
        self.assertNotIn("simulate", inspect.getsource(c))


if __name__ == "__main__":
    unittest.main()
