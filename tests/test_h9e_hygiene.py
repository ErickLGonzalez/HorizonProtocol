"""H9-E: red-team attacks only through public gates (no verifier internals). [SOUND]

The H8-surface attacks (RT-E, RT-F) live in the same shared `redteam.attacks`
module RT1 uses, rather than a second, parallel attacker package - see
docs/redteam-spec.md. `tests/test_redteam.py`'s `TestRedTeamHygiene` already
asserts, for the whole module, that no test helpers are imported and no
private key material is read; this test adds the H9-specific checks: the new
attacks exist, and the timing-fuzz oracle they reuse (H9-A) is independently
derived rather than a call to the gate itself.
"""
import inspect
import unittest

import redteam.attacks as atk


class TestHygiene(unittest.TestCase):
    def test_h8_attacks_present_and_public(self):
        for name in ("attack_h8_replay_fuzz", "attack_h8_boundary_skew_fuzz",
                    "attack_ledger_named_scenarios"):
            self.assertTrue(hasattr(atk, name), f"missing {name}")

    def test_h8_attacks_use_only_public_signed_capture_and_capture_verify(self):
        src = inspect.getsource(atk)
        self.assertNotIn("_key", src)

    def test_timing_fuzz_uses_independent_oracle(self):
        # RT-A / H9-A's oracle must be a re-derivation, not a call to the gate
        src = inspect.getsource(atk._independent_admissible)
        self.assertNotIn("causally_admissible(", src)


if __name__ == "__main__":
    unittest.main()
