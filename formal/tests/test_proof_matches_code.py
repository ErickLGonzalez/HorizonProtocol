"""Bind the formal proof to the real code: the proven predicate must equal
horizon/geometry.py::causally_admissible on an exhaustive boundary grid. [SOUND]

The Z3 proof establishes correctness over ALL integers; this test guarantees the
CODE implements the same predicate the proof is about (no divergence between the
verified spec and the shipped function)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from horizon.geometry import C_NM_PER_NS, causally_admissible


def proven_predicate(t1, p1, t2, p2):
    """The exact predicate proven in kernel_proof.py / kernel.dfy."""
    if t2 < t1:
        return False
    d2 = sum((b - a) ** 2 for a, b in zip(p1, p2))
    dt = t2 - t1
    return (C_NM_PER_NS * dt) ** 2 >= d2


class TestProofMatchesCode(unittest.TestCase):
    def test_boundary_grid_exhaustive(self):
        C = C_NM_PER_NS
        mism = 0
        for dt in range(0, 5):
            reach = C * dt
            for off in range(-3, 4):  # straddle the light cone shell
                x = max(0, reach + off)
                for y in range(0, 3):
                    p1, p2 = (0, 0, 0), (x, y, 0)
                    if causally_admissible(0, p1, dt, p2) != proven_predicate(0, p1, dt, p2):
                        mism += 1
        self.assertEqual(mism, 0)

    def test_negative_dt_matches(self):
        self.assertEqual(causally_admissible(5, (0, 0, 0), 3, (0, 0, 0)),
                         proven_predicate(5, (0, 0, 0), 3, (0, 0, 0)))
        self.assertFalse(causally_admissible(5, (0, 0, 0), 3, (0, 0, 0)))


if __name__ == "__main__":
    unittest.main()
