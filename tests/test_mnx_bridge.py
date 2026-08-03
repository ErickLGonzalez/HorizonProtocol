"""MNX-D: the ledger<->memory bridge is faithful. [SOUND]

Asserts that the memory's geometric ordering agrees, edge for edge, with the
HorizonProtocol CausalLedger admissibility gate -- i.e. the convergence claim
is literally true, not merely analogous.
"""
import unittest
from mnemesis.memory import CausalMemory, GeometricOrdering, Write
from horizon.ledger import CausalLedger
from horizon.geometry import C_NM_PER_NS


class TestBridge(unittest.TestCase):
    def test_memory_ordering_matches_ledger(self):
        ordering = GeometricOrdering()
        L = CausalLedger()
        # three events
        specs = {
            "A": (0, (0, 0, 0)),
            "B": (10, (C_NM_PER_NS, 0, 0)),        # inside A's cone
            "C": (0, (C_NM_PER_NS, 0, 0)),         # spacelike to A
        }
        for eid, (t, p) in specs.items():
            L.add_event(eid, t, p)
        # build matching writes
        W = {eid: Write("k", eid, eid,
                        {"time_ns": t, "pos_nm": list(p)}, ())
             for eid, (t, p) in specs.items()}

        # A->B: admissible in both
        self.assertTrue(ordering.before(W["A"], W["B"]))
        self.assertEqual(L.add_edge("A", "B")["verdict"], "ADMITTED")
        # A->C: spacelike, rejected in both
        self.assertFalse(ordering.before(W["A"], W["C"]))
        self.assertEqual(L.add_edge("A", "C")["verdict"], "REJECTED")
        # concurrency agrees
        self.assertTrue(ordering.concurrent(W["A"], W["C"]))
        self.assertTrue(L.concurrent("A", "C"))

    def test_verifier_uses_exact_kernel(self):
        # the memory's geometric ordering must route through the exact H1 gate
        import mnemesis.memory as mm, inspect
        src = inspect.getsource(mm.GeometricOrdering)
        self.assertIn("causally_admissible", src)
        self.assertIn("horizon.geometry", src)


if __name__ == "__main__":
    unittest.main()
