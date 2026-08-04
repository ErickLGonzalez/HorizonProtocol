"""H9-C: H8 capture-verify boundary and trust-boundary attack. [SOUND]

`impossible_admitted == 0` is the requirement: no genuinely-impossible
arrival (more than the declared clock uncertainty below the absolute
vacuum floor) may ever be classified ADMITTED, whether the adversary
attacks `classify`'s own `c_eff` parameter or smuggles an adversarial
`c_eff` inside an otherwise-untrusted `capture` blob.
"""
import random
import unittest

from redteam import SEED
from redteam.attacks import attack_h8_boundary_skew_fuzz


class TestBoundarySkew(unittest.TestCase):
    def test_impossible_admitted_zero(self):
        report = attack_h8_boundary_skew_fuzz(random.Random(SEED), trials=1000)
        self.assertEqual(report["bypasses"], [],
                         f"impossible arrival(s) admitted: {report['bypasses'][:5]}")


if __name__ == "__main__":
    unittest.main()
