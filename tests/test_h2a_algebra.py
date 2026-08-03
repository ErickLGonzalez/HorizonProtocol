"""H2-A: chain algebra round-trip and tamper rejection. [SOUND]"""
import unittest
from horizon.commitment import (P_FIELD, K_SUSTAIN, SEED_H2, derive_secrets,
                                derive_challenges, commit_response,
                                sustain_response, verify_reveal)


def honest_rounds(b):
    secrets = derive_secrets(SEED_H2, K_SUSTAIN)
    challenges = derive_challenges(SEED_H2, K_SUSTAIN)
    rounds = []
    for k in range(K_SUSTAIN + 1):
        y = (commit_response(secrets[0], b, challenges[0]) if k == 0
             else sustain_response(secrets[k], secrets[k - 1], challenges[k]))
        rounds.append({"k": k, "r": challenges[k], "y": y})
    return rounds, secrets


class TestChainAlgebra(unittest.TestCase):
    def test_round_trip_both_bits(self):
        for b in (0, 1):
            rounds, secrets = honest_rounds(b)
            res = verify_reveal(rounds, b, secrets, K_SUSTAIN)
            self.assertEqual(res["verdict"], "ADMITTED")
            self.assertEqual(res["rounds_checked"], K_SUSTAIN + 1)

    def test_flipped_bit_rejected(self):
        rounds, secrets = honest_rounds(1)
        res = verify_reveal(rounds, 0, secrets, K_SUSTAIN)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "chain_consistency")
        self.assertEqual(res["witness"]["failing_round"], 0)
        self.assertNotEqual(res["witness"]["lhs_transcript_y"],
                            res["witness"]["rhs_recomputed"])

    def test_altered_secret_rejected_at_its_round(self):
        rounds, secrets = honest_rounds(0)
        tampered = list(secrets)
        tampered[3] = (tampered[3] + 1) % P_FIELD
        res = verify_reveal(rounds, 0, tampered, K_SUSTAIN)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["failing_round"], 3)

    def test_secret_count_gate(self):
        rounds, secrets = honest_rounds(0)
        res = verify_reveal(rounds, 0, secrets[:-1], K_SUSTAIN)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "secret_count")

    def test_truncated_rounds_rejected(self):
        # a transcript truncated to an honest prefix must not be ADMITTED
        rounds, secrets = honest_rounds(0)
        res = verify_reveal(rounds[:-1], 0, secrets[:-1], K_SUSTAIN)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "round_count")

    def test_empty_rounds_rejected(self):
        res = verify_reveal([], 0, [], K_SUSTAIN)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "round_count")

    def test_duplicate_round_index_rejected(self):
        rounds, secrets = honest_rounds(0)
        tampered = list(rounds)
        tampered[-1] = dict(tampered[-1])
        tampered[-1]["k"] = tampered[-2]["k"]  # duplicate an earlier index
        res = verify_reveal(tampered, 0, secrets, K_SUSTAIN)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "round_sequence")

    def test_skipped_round_index_rejected(self):
        rounds, secrets = honest_rounds(0)
        tampered = list(rounds)
        tampered[-1] = dict(tampered[-1])
        tampered[-1]["k"] = K_SUSTAIN + 1  # skip past the end of the range
        res = verify_reveal(tampered, 0, secrets, K_SUSTAIN)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "round_sequence")


if __name__ == "__main__":
    unittest.main()
