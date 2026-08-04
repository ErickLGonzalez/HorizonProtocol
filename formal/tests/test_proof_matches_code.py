"""Bind the formal proof to the real code. [SOUND]

Two separate bindings, since the Z3 proof establishes two separate things
about ABSTRACT variables and neither, by itself, says anything about what
this repository's actual Python functions compute:

  (1) T1 (faithfulness) is about the predicate SHAPE `(c*dt)^2 >= D`; this
      test confirms `horizon.geometry.causally_admissible` computes exactly
      that shape by sampling it against an independent re-implementation
      across representative magnitudes.
  (2) T5 (min-light-time minimality) is about ANY value `m` that already
      satisfies the two witness conditions - it proves such an `m` is
      minimal, but never itself claims `horizon.geometry.min_light_time_ns`
      actually RETURNS such a value (see erratum below). This test checks
      that directly.

(Erratum: an earlier version of this file's `test_boundary_grid_exhaustive`
sampled only a small, fixed-magnitude grid (dt in 0..4, a few nanometers of
offset) while its name and the module's original docstring implied this
"guarantees" no divergence - overclaiming exhaustiveness a finite sample
over an infinite integer domain cannot provide (that is exactly what the Z3
proof, not this test, is for: T1 covers every integer input by construction,
this test only ever covers the ones it samples). A real divergence at an
untested magnitude - e.g. only at interplanetary scale, or only for a
specific large dt - would have passed silently. Renamed and reworded to be
honest about what sampling can and cannot establish, and widened to sample
multiple magnitudes (small, terrestrial, interplanetary) rather than one.

Separately, T5 was never bound to `min_light_time_ns` at all: an
implementation that always returned an incorrect value could leave T5 and
the Z3 proof suite PROVEN while the certificate implied the boundary-
corrected search algorithm itself was verified. `test_min_light_time_matches_witness_sample`
closes that gap by checking the actual function's output against T5's
exact witness conditions across the same multi-scale sample.

Neither test is a substitute for the proof; both exist because the proof is
about the mathematics, and these confirm the CODE is an instance of that
mathematics, on a representative sample - a coding-level divergence (a
typo, an off-by-one, a wrong constant) is exactly the failure mode a proof
about the abstract predicate cannot, by itself, catch.)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from horizon.geometry import C_NM_PER_NS, causally_admissible, min_light_time_ns

# Representative magnitudes: small integers, terrestrial (~1000 km), and
# interplanetary (~Earth-Mars) distances in nanometers - chosen to exercise
# both the tiny boundary-grid case and genuine bignum squaring, matching the
# multi-scale sampling `redteam.attacks.attack_timing_fuzz` (RT-A) already
# uses against this same predicate.
M_TO_NM = 1_000_000_000
MAGNITUDES_NM = (0, 1_000 * M_TO_NM, 225_000_000_000 * M_TO_NM)


def proven_predicate(t1, p1, t2, p2):
    """The exact predicate proven in kernel_proof.py / kernel.dfy."""
    if t2 < t1:
        return False
    d2 = sum((b - a) ** 2 for a, b in zip(p1, p2))
    dt = t2 - t1
    return (C_NM_PER_NS * dt) ** 2 >= d2


class TestProofMatchesCode(unittest.TestCase):
    def test_boundary_grid_sample(self):
        # NOT exhaustive over all integers (see module erratum) - a
        # boundary-concentrated sample across several representative
        # magnitudes, catching a coding-level divergence the Z3 proof
        # (which covers every integer input, but only for the abstract
        # predicate shape) would not itself catch.
        C = C_NM_PER_NS
        mism = 0
        for base_nm in MAGNITUDES_NM:
            for dt in range(0, 5):
                reach = C * dt
                for off in range(-3, 4):  # straddle the light cone shell
                    x = max(0, base_nm + reach + off)
                    for y in range(0, 3):
                        p1, p2 = (base_nm, 0, 0), (x, y, 0)
                        if causally_admissible(0, p1, dt, p2) != proven_predicate(0, p1, dt, p2):
                            mism += 1
        self.assertEqual(mism, 0)

    def test_negative_dt_matches(self):
        self.assertEqual(causally_admissible(5, (0, 0, 0), 3, (0, 0, 0)),
                         proven_predicate(5, (0, 0, 0), 3, (0, 0, 0)))
        self.assertFalse(causally_admissible(5, (0, 0, 0), 3, (0, 0, 0)))

    def test_min_light_time_matches_witness_sample(self):
        # T5 proves: IF m satisfies the witness conditions, m is minimal.
        # It never claims min_light_time_ns's actual return value satisfies
        # those conditions (see module erratum) - checked directly here.
        C = C_NM_PER_NS
        cases = []
        for base_nm in MAGNITUDES_NM:
            for off in (0, 1, 2, 3, 100, -1, -50):
                x = max(0, base_nm + off)
                cases.append(((0, 0, 0), (x, 0, 0)))
            cases.append(((base_nm, 0, 0), (base_nm, 0, 0)))  # zero distance
        for p1, p2 in cases:
            m = min_light_time_ns(p1, p2)
            d2 = sum((b - a) ** 2 for a, b in zip(p1, p2))
            self.assertGreaterEqual(m, 0, (p1, p2))
            self.assertGreaterEqual((C * m) ** 2, d2, (p1, p2, m, d2))
            if m > 0:
                self.assertLess((C * (m - 1)) ** 2, d2, (p1, p2, m, d2))


if __name__ == "__main__":
    unittest.main()
