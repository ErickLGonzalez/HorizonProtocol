"""D0-B: coordination-free commit + conflict retention. [SOUND]"""
import unittest
from causalstore.store import CausalStore
from causalstore.ordering import GeometricOrdering, LogicalOrdering
from causalstore.geometry import C_NM_PER_NS


def clk(t, x=0, u=1000): return {"time_ns": t, "pos_nm": [x, 0, 0], "u_ns": u}
FAR = C_NM_PER_NS * 20_000_000  # 20 light-ms away


class TestStore(unittest.TestCase):
    def setUp(self):
        self.s = CausalStore(GeometricOrdering())

    def test_disjoint_keys_all_coordination_free(self):
        for i in range(10):
            r = self.s.write(f"k{i}", str(i), "n", clk(i, x=FAR*i))
            self.assertFalse(r.coordinated)
        self.assertEqual(self.s.coordination_free_rate(), 1.0)

    def test_spacelike_same_key_retained_as_conflict(self):
        # two simultaneous, far-apart writes to the SAME key -> concurrent
        self.s.write("acct", "NY", "ny", clk(0, x=0))
        self.s.write("acct", "LDN", "london", clk(0, x=FAR))
        r = self.s.read("acct")
        self.assertEqual(r["status"], "CONFLICT")
        self.assertEqual(len(r["candidates"]), 2)

    def test_causal_supersede_no_coordination(self):
        r1 = self.s.write("x", "v1", "n", clk(0, x=0))
        # later write inside the future cone supersedes v1, no coordination
        r2 = self.s.write("x", "v2", "n", clk(1_000_000, x=0),
                          supersedes=[r1.event_id])
        self.assertEqual(r2.verdict, "ADMITTED")
        self.assertFalse(r2.coordinated)
        self.assertEqual(self.s.read("x")["value"], "v2")

    def test_supersede_non_ancestor_rejected(self):
        r1 = self.s.write("x", "v1", "ny", clk(0, x=0))
        # spacelike write cannot claim to supersede
        r2 = self.s.write("x", "v2", "ldn", clk(0, x=FAR),
                          supersedes=[r1.event_id])
        self.assertEqual(r2.verdict, "REJECTED")

    def test_nothing_lost_on_coordination_free(self):
        # even coordination-free concurrent writes are all retained
        self.s.write("acct", "A", "ny", clk(0, x=0))
        self.s.write("acct", "B", "ldn", clk(0, x=FAR))
        self.s.write("acct", "C", "tokyo", clk(0, x=FAR*2))
        r = self.s.read("acct")
        vals = {c["value"] for c in r["candidates"]}
        self.assertEqual(vals, {"A", "B", "C"})  # nothing dropped

    def test_stale_write_dominated_by_frontier_rejected(self):
        # Regression for the fixed bug (see store.py module erratum): write()
        # used to classify a new write's relation to the frontier by checking
        # only "after the whole frontier" or "concurrent with the whole
        # frontier", falling through to conflict-retention for anything else -
        # including a write causally BEFORE an already-current frontier
        # member. That let a stale write resurrect a superseded value as a
        # live CONFLICT candidate. Reproduced with vector clocks: A, then B
        # superseding A, then C carrying A's OLD vector clock.
        s = CausalStore(LogicalOrdering())
        rA = s.write("k", "A", "n1", {"vc": {"n1": 1}})
        rB = s.write("k", "B", "n1", {"vc": {"n1": 2}}, supersedes=[rA.event_id])
        rC = s.write("k", "C", "n1", {"vc": {"n1": 1}})  # stale: same vc as superseded A
        self.assertEqual(rC.verdict, "REJECTED")
        self.assertEqual(rC.witness["reason"],
                         "stale_write_dominated_by_existing_frontier")
        self.assertIn(rB.event_id, rC.witness["dominating_event_ids"])
        # the true current value must remain the sole, uncontaminated frontier
        r = s.read("k")
        self.assertEqual(r["status"], "RESOLVED")
        self.assertEqual(r["value"], "B")

    def test_retried_write_is_idempotent_not_a_spurious_conflict(self):
        # Regression for the fixed bug (see store.py module erratum 2): a
        # retry of the exact same write (same key/value/origin/clock, hence
        # the same deterministic event_id) used to be classified as
        # "concurrent with itself" (equal clocks -> before() False both
        # ways) and appended as a second frontier entry sharing the first
        # one's event_id, producing a permanent spurious CONFLICT.
        s = CausalStore(LogicalOrdering())
        clock = {"vc": {"n1": 1}}
        r1 = s.write("k", "v", "n1", clock)
        r2 = s.write("k", "v", "n1", clock)
        self.assertEqual(r1.event_id, r2.event_id)
        self.assertEqual(r2.mode, "duplicate_ignored")
        self.assertFalse(r2.coordinated)
        r = s.read("k")
        self.assertEqual(r["status"], "RESOLVED")
        self.assertEqual(r["value"], "v")
        self.assertEqual(s.stats["total"], 1)  # the retry must not double-count


if __name__ == "__main__":
    unittest.main()
