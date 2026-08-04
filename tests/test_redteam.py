"""RT1: independent red-team harness. [SOUND]

Runs every attack class through ONLY the public verify_*/gate API and
asserts zero bypasses. A failure here means an attacker's automated
search found an input that passed a gate it should not have - this is
the "we tried to break it and reported what we found" suite, distinct
from every other test file's cooperative (hand-picked) negative controls.
"""
import random
import unittest

from redteam import SEED
from redteam.attacks import (attack_boundary_fuzz, attack_forgery_fuzz,
                             attack_ledger_cycle_fuzz,
                             attack_measured_certificate_forgery_fuzz,
                             attack_timing_fuzz)


class TestRedTeam(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(SEED)

    def test_timing_fuzz_zero_bypasses(self):
        report = attack_timing_fuzz(self.rng, trials=3000)
        self.assertEqual(report["bypasses"], [],
                         f"kernel disagreed with independent reference on "
                         f"{len(report['bypasses'])}/{report['trials']} trials")

    def test_boundary_fuzz_zero_bypasses(self):
        report = attack_boundary_fuzz(self.rng, trials=2000)
        self.assertEqual(report["bypasses"], [])

    def test_forgery_fuzz_zero_bypasses(self):
        report = attack_forgery_fuzz(self.rng, trials=300)
        self.assertEqual(report["bypasses"], [])

    def test_measured_certificate_forgery_fuzz_zero_bypasses(self):
        report = attack_measured_certificate_forgery_fuzz(self.rng, trials=300)
        self.assertEqual(report["bypasses"], [])

    def test_ledger_cycle_fuzz_zero_bypasses(self):
        report = attack_ledger_cycle_fuzz(self.rng, trials=1000)
        self.assertEqual(report["bypasses"], [])

    def test_deterministic_across_reruns(self):
        r1 = attack_timing_fuzz(random.Random(SEED), trials=200)
        r2 = attack_timing_fuzz(random.Random(SEED), trials=200)
        self.assertEqual(r1, r2)


class TestRedTeamHygiene(unittest.TestCase):
    def test_attacks_module_never_reaches_into_private_station_state(self):
        # the harness must attack through the on-the-wire representation
        # (receipt bodies, MAC hex strings) and public verify_* functions,
        # never by reading a station's private key directly
        import inspect
        import redteam.attacks as atk
        src = inspect.getsource(atk)
        self.assertNotIn("_key", src)

    def test_attacks_module_imports_no_test_helpers(self):
        import ast
        import inspect
        import redteam.attacks as atk
        tree = ast.parse(inspect.getsource(atk))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any(m.startswith("tests") for m in imported), imported)


if __name__ == "__main__":
    unittest.main()
