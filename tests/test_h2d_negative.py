"""H2-D: negative controls - cheat, apparatus, tamper. [SOUND]"""
import unittest
from horizon.commitment import (DT_RESP_NS, isolation_gate, verify_reveal,
                                verify_transcript_chain)
from horizon.commit_sim import CHEAT_FLIP, HONEST, run_session


class TestNegativeControls(unittest.TestCase):
    def test_cheat_flip_rejected_at_round_1(self):
        sess = run_session(CHEAT_FLIP, b=0)
        self.assertNotEqual(sess["reveal"]["b"], 0)  # cheater claims flipped bit
        res = verify_reveal(sess["rounds"], sess["reveal"]["b"],
                            sess["reveal"]["secrets"])
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "chain_consistency")
        # round 0 is self-consistent by construction (a_0 back-solved);
        # the forged a_0 breaks the chain exactly at round 1
        self.assertEqual(res["witness"]["failing_round"], 1)

    def test_cheat_flip_other_bit(self):
        sess = run_session(CHEAT_FLIP, b=1)
        res = verify_reveal(sess["rounds"], sess["reveal"]["b"],
                            sess["reveal"]["secrets"])
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["failing_round"], 1)

    def test_misconfigured_geometry_apparatus_limited(self):
        site_close = (1_000_000_000, 0, 0)  # 1 m from origin
        res = isolation_gate((0, 0, 0), site_close, DT_RESP_NS)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertTrue(res["exact_witness"]["admissible"])
        # a scenario aggregate must therefore be REJECTED, never PASS
        scenario_aggregate = ("REJECTED" if res["verdict"] != "PASS" else "PASS")
        self.assertEqual(scenario_aggregate, "REJECTED")

    def test_tampered_transcript_rejected(self):
        sess = run_session(HONEST, b=1)
        rounds = [dict(r) for r in sess["rounds"]]
        rounds[4]["y"] = (rounds[4]["y"] + 1) % (2 ** 61 - 1)
        res = verify_transcript_chain(rounds, sess["transcript_hashes"])
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "transcript_hash_chain")
        self.assertEqual(res["witness"]["failing_round"], 4)


if __name__ == "__main__":
    unittest.main()
