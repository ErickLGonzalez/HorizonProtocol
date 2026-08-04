"""H9-B: H8 signed-capture replay attack. [SOUND]"""
import random
import unittest

from redteam import SEED
from redteam.attacks import attack_h8_replay_fuzz


class TestReplay(unittest.TestCase):
    def test_no_accepted_forgeries(self):
        report = attack_h8_replay_fuzz(random.Random(SEED), trials=1000)
        self.assertEqual(report["bypasses"], [])


if __name__ == "__main__":
    unittest.main()
