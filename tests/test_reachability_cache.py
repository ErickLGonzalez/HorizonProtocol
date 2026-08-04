"""precedes_fast() must agree with precedes() (the reference) on every query,
including as edges are added incrementally (cache invalidation). [SOUND, PERF]
"""
import random
import unittest

from horizon.geometry import C_NM_PER_NS
from horizon.ledger import CausalLedger
from horizon.reachability_cache import build_adjacency, precedes_fast


class TestReachabilityCache(unittest.TestCase):
    def _chain_ledger(self, n):
        L = CausalLedger()
        for i in range(n):
            L.add_event(f"E{i}", i * 10, (i * C_NM_PER_NS, 0, 0))
        for i in range(n - 1):
            r = L.add_edge(f"E{i}", f"E{i + 1}")
            self.assertEqual(r["verdict"], "ADMITTED")
        return L

    def test_agrees_on_a_chain(self):
        n = 30
        L = self._chain_ledger(n)
        for i in range(n):
            for j in range(n):
                self.assertEqual(L.precedes(f"E{i}", f"E{j}"),
                                 L.precedes_fast(f"E{i}", f"E{j}"),
                                 f"disagreement on E{i}->E{j}")

    def test_agrees_after_incremental_edges(self):
        # cache must invalidate correctly as new edges are admitted, not
        # just be correct once at the end
        L = CausalLedger()
        rng = random.Random("RC-TEST-SEED")
        n = 25
        for i in range(n):
            L.add_event(f"N{i}", i * 10, (i * C_NM_PER_NS, 0, 0))
        pairs = [(i, i + 1) for i in range(n - 1)]
        rng.shuffle(pairs)
        for i, j in pairs:
            L.add_edge(f"N{i}", f"N{j}")
            # spot-check agreement immediately after each incremental edge
            a, b = rng.randrange(n), rng.randrange(n)
            self.assertEqual(L.precedes(f"N{a}", f"N{b}"),
                             L.precedes_fast(f"N{a}", f"N{b}"))

    def test_agrees_with_concurrent_and_unreachable_pairs(self):
        L = CausalLedger()
        L.add_event("A", 0, (0, 0, 0))
        L.add_event("B", 10, (C_NM_PER_NS, 0, 0))
        L.add_event("C", 0, (C_NM_PER_NS, 0, 0))  # spacelike to A - never admitted
        L.add_edge("A", "B")
        L.add_edge("A", "C")  # rejected (concurrent)
        for a, b in [("A", "B"), ("B", "A"), ("A", "C"), ("C", "A"),
                    ("A", "A"), ("B", "C")]:
            self.assertEqual(L.precedes(a, b), L.precedes_fast(a, b), f"{a}->{b}")

    def test_precedes_fast_never_true_for_self(self):
        L = self._chain_ledger(5)
        for i in range(5):
            self.assertFalse(L.precedes_fast(f"E{i}", f"E{i}"))

    def test_build_adjacency_matches_edge_set(self):
        edges = {("a", "b"), ("a", "c"), ("b", "d")}
        adj = build_adjacency(edges)
        self.assertEqual(set(adj["a"]), {"b", "c"})
        self.assertEqual(set(adj["b"]), {"d"})
        self.assertTrue(precedes_fast(adj, "a", "d"))
        self.assertFalse(precedes_fast(adj, "d", "a"))


if __name__ == "__main__":
    unittest.main()
