"""H9-D: ledger integrity - randomized cycle fuzz plus named scenarios. [SOUND]"""
import random
import unittest

from redteam import SEED
from redteam.attacks import attack_ledger_cycle_fuzz, attack_ledger_named_scenarios


class TestLedger(unittest.TestCase):
    def test_cycle_fuzz_zero_bypasses(self):
        report = attack_ledger_cycle_fuzz(random.Random(SEED), trials=2000)
        self.assertEqual(report["bypasses"], [])

    def test_named_scenarios_zero_bypasses(self):
        report = attack_ledger_named_scenarios()
        self.assertEqual(report["bypasses"], [])


if __name__ == "__main__":
    unittest.main()
