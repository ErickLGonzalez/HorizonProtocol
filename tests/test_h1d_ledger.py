"""H1-D: causal ledger admissibility and concurrency. [SOUND, E0]"""
import unittest
from horizon.ledger import CausalLedger
from horizon.geometry import C_NM_PER_NS


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.L = CausalLedger()
        # A at origin, t=0. B 1 light-ns away, t=10 (comfortably inside cone).
        self.L.add_event("A", 0, (0, 0, 0))
        self.L.add_event("B", 10, (C_NM_PER_NS, 0, 0))
        # C: spacelike to A (1 light-ns away but simultaneous)
        self.L.add_event("C", 0, (C_NM_PER_NS, 0, 0))
        # D: strictly inside A's cone via B (chain check)
        self.L.add_event("D", 25, (2 * C_NM_PER_NS, 0, 0))

    def test_admissible_edge_admitted_with_witness(self):
        res = self.L.add_edge("A", "B")
        self.assertEqual(res["verdict"], "ADMITTED")
        self.assertTrue(res["witness"]["admissible"])

    def test_spacelike_edge_rejected_with_exact_witness(self):
        res = self.L.add_edge("A", "C")
        self.assertEqual(res["verdict"], "REJECTED")
        w = res["witness"]
        self.assertEqual(w["dt_ns"], 0)
        self.assertEqual(w["rhs_dist_squared_nm2"], C_NM_PER_NS ** 2)
        self.assertEqual(len(self.L.rejections), 1)

    def test_concurrency_is_symmetric_nonorder(self):
        self.assertTrue(self.L.concurrent("A", "C"))
        self.assertTrue(self.L.concurrent("C", "A"))
        self.assertFalse(self.L.concurrent("A", "B"))

    def test_transitive_reachability(self):
        self.L.add_edge("A", "B")
        self.L.add_edge("B", "D")
        self.assertTrue(self.L.precedes("A", "D"))
        self.assertFalse(self.L.precedes("D", "A"))

    def test_backward_edge_rejected(self):
        res = self.L.add_edge("B", "A")
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertFalse(res["witness"]["strictly_later"])


if __name__ == "__main__":
    unittest.main()
