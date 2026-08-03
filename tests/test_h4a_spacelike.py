"""H4-A: pairwise spacelike separation - verify, don't assume. [SOUND]"""
import unittest
from horizon.beacon import EMITTERS, T_EMIT_NS, pairwise_spacelike_witnesses
from horizon.ledger import CausalLedger


def frozen_emissions():
    return {eid: {"time_ns": T_EMIT_NS, "pos_nm": pos}
            for eid, pos in EMITTERS.items()}


class TestPairwiseSpacelike(unittest.TestCase):
    def test_all_pairs_spacelike_both_directions(self):
        pw = pairwise_spacelike_witnesses(frozen_emissions())
        self.assertEqual(len(pw), 3)  # C(3,2) unordered pairs
        for pair, w in pw.items():
            self.assertTrue(w["spacelike"], pair)
            self.assertFalse(w["witness_forward"]["admissible"], pair)
            self.assertFalse(w["witness_backward"]["admissible"], pair)
            # exact integers present in every witness
            self.assertIsInstance(w["witness_forward"]["rhs_dist_squared_nm2"], int)

    def test_matches_ledger_concurrent(self):
        led = CausalLedger()
        for eid, e in frozen_emissions().items():
            led.add_event(eid, e["time_ns"], e["pos_nm"])
        self.assertTrue(led.concurrent("E1", "E2"))
        self.assertTrue(led.concurrent("E2", "E1"))  # symmetric
        self.assertTrue(led.concurrent("E1", "E3"))
        self.assertTrue(led.concurrent("E2", "E3"))

    def test_timelike_pair_detected(self):
        emissions = frozen_emissions()
        emissions["E4"] = {"time_ns": T_EMIT_NS + 10_000_000,
                           "pos_nm": (1000, 0, 0)}  # timelike to E1
        pw = pairwise_spacelike_witnesses(emissions)
        self.assertFalse(pw["E1|E4"]["spacelike"])
        self.assertTrue(pw["E1|E4"]["witness_forward"]["admissible"])


if __name__ == "__main__":
    unittest.main()
