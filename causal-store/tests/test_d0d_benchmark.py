"""D0-D: the coordination-free advantage is real and deterministic. [SOUND]"""
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench"))
from geo_workload import run


class TestBenchmark(unittest.TestCase):
    def test_high_coordination_free_rate(self):
        r = run(n_writes=3000, n_keys=1500)
        # most writes to distinct keys across regions should be coordination-free
        self.assertGreater(r["coordination_free_rate"], 0.7)

    def test_speedup_over_total_order(self):
        r = run(n_writes=3000, n_keys=1500)
        self.assertGreater(r["modeled_avg_latency_ms"]["speedup_x"], 2.0)

    def test_deterministic(self):
        a = run(n_writes=1000, n_keys=500)
        b = run(n_writes=1000, n_keys=500)
        self.assertEqual(a["coordination_free_rate"], b["coordination_free_rate"])


if __name__ == "__main__":
    unittest.main()
