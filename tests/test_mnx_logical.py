"""MNX-C: causal memory under LOGICAL (vector-clock) ordering. [SOUND]"""
import unittest
from mnemesis.memory import CausalMemory, LogicalOrdering


def vc(**kw):
    return {"vc": dict(kw)}


class TestLogicalMemory(unittest.TestCase):
    def setUp(self):
        self.m = CausalMemory(LogicalOrdering())

    def test_happens_before_supersession(self):
        r1 = self.m.put("k", "v1", "n1", vc(n1=1))
        r2 = self.m.put("k", "v2", "n1", vc(n1=2), supersedes=[r1["wid"]])
        self.assertEqual(r2["verdict"], "ADMITTED")
        self.assertEqual(self.m.get("k")["value"], "v2")

    def test_concurrent_conflict(self):
        self.m.put("k", "vA", "n1", vc(n1=1))
        self.m.put("k", "vB", "n2", vc(n2=1))
        g = self.m.get("k")
        self.assertEqual(g["status"], "CONFLICT")
        self.assertEqual(len(g["candidates"]), 2)

    def test_supersede_concurrent_rejected(self):
        r1 = self.m.put("k", "vA", "n1", vc(n1=1))
        # n2's write is concurrent, cannot claim to supersede n1's
        r2 = self.m.put("k", "vB", "n2", vc(n2=1), supersedes=[r1["wid"]])
        self.assertEqual(r2["verdict"], "REJECTED")
        self.assertEqual(r2["reason"], "supersedes_non_ancestor")


if __name__ == "__main__":
    unittest.main()
