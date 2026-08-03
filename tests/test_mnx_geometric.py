"""MNX-B: causal memory under GEOMETRIC (light-cone) ordering. [SOUND]"""
import unittest
from mnemesis.memory import CausalMemory, GeometricOrdering
from horizon.geometry import C_NM_PER_NS


def clk(t, x=0, y=0, z=0):
    return {"time_ns": t, "pos_nm": [x, y, z]}


class TestGeometricMemory(unittest.TestCase):
    def setUp(self):
        self.m = CausalMemory(GeometricOrdering())

    def test_causal_supersession_admitted(self):
        r1 = self.m.put("cfg", "v1", "A", clk(0, 0, 0))
        # a later write inside the future cone supersedes v1
        r2 = self.m.put("cfg", "v2", "A", clk(1_000_000, 0, 0),
                        supersedes=[r1["wid"]])
        self.assertEqual(r2["verdict"], "ADMITTED")
        g = self.m.get("cfg")
        self.assertEqual(g["status"], "RESOLVED")
        self.assertEqual(g["value"], "v2")

    def test_supersede_non_ancestor_rejected(self):
        # w1 at a far position, w2 spacelike-separated cannot claim to supersede it
        r1 = self.m.put("cfg", "v1", "A", clk(0, 0, 0))
        far = C_NM_PER_NS  # 1 light-ns away
        r2 = self.m.put("cfg", "v2", "B", clk(0, far, 0),  # simultaneous+distant
                        supersedes=[r1["wid"]])
        self.assertEqual(r2["verdict"], "REJECTED")
        self.assertEqual(r2["reason"], "supersedes_non_ancestor")
        self.assertIn("witness", r2)

    def test_concurrent_writes_conflict_with_provenance(self):
        # two spacelike writes to the same key, neither superseding the other
        self.m.put("cfg", "vA", "A", clk(0, 0, 0))
        self.m.put("cfg", "vB", "B", clk(0, C_NM_PER_NS, 0))
        g = self.m.get("cfg")
        self.assertEqual(g["status"], "CONFLICT")
        self.assertEqual(len(g["candidates"]), 2)
        vals = {c["value"] for c in g["candidates"]}
        self.assertEqual(vals, {"vA", "vB"})

    def test_explicit_resolution_collapses_conflict(self):
        rA = self.m.put("cfg", "vA", "A", clk(0, 0, 0))
        self.m.put("cfg", "vB", "B", clk(0, C_NM_PER_NS, 0))
        # a resolver strictly in the future of BOTH picks vA
        far_future = clk(10_000_000, 0, 0)  # 10 ms later at origin: cone covers both
        res = self.m.resolve("cfg", rA["wid"], "C", far_future)
        self.assertEqual(res["verdict"], "ADMITTED")
        g = self.m.get("cfg")
        self.assertEqual(g["status"], "RESOLVED")
        self.assertEqual(g["value"], "vA")

    def test_provenance_present(self):
        r = self.m.put("k", "v", "A", clk(5, 0, 0))
        self.assertIn("provenance", r)
        p = r["provenance"]
        self.assertEqual(p["observer"], "A")
        self.assertEqual(p["value"], "v")
        self.assertIn("clock", p)


if __name__ == "__main__":
    unittest.main()
