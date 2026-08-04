"""H9-A: independent differential timing fuzz. [SOUND]

Reuses RT-A (`redteam.attacks.attack_timing_fuzz`) rather than standing up a
second, weaker independent oracle: RT-A already cross-checks
`horizon.geometry.causally_admissible` against a DELIBERATELY DIFFERENT
algorithm (`decimal.Decimal`-based real-number arithmetic) concentrated near
each sampled pair's exact light-cone boundary, across scales from
terrestrial to interplanetary - a strict superset of what a boundary-only,
single-magnitude fuzzer would cover. See docs/redteam-spec.md, RT-A.
"""
import random
import unittest

from redteam import SEED
from redteam.attacks import attack_timing_fuzz


class TestFuzz(unittest.TestCase):
    def test_zero_misclassifications(self):
        report = attack_timing_fuzz(random.Random(SEED), trials=5000)
        self.assertEqual(report["bypasses"], [],
                         f"kernel disagreed with independent reference on "
                         f"{len(report['bypasses'])}/{report['trials']} trials")


if __name__ == "__main__":
    unittest.main()
