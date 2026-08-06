"""D0-A: the L2 ordering contract (geometric, logical, hybrid). [SOUND]"""
import unittest
from causalstore.ordering import GeometricOrdering, LogicalOrdering, HybridOrdering
from causalstore.geometry import C_NM_PER_NS, min_light_time_ns


def geo(t, x=0, u=0): return {"clock": {"time_ns": t, "pos_nm": [x, 0, 0], "u_ns": u}}
def vc(**kw): return {"clock": {"vc": dict(kw)}}


class TestOrdering(unittest.TestCase):
    def test_geometric_before_inside_cone(self):
        o = GeometricOrdering()
        a = geo(0, 0)
        b = geo(100, C_NM_PER_NS)  # 100ns later, 1 light-ns away -> in cone
        self.assertTrue(o.before(a, b))
        self.assertFalse(o.before(b, a))

    def test_geometric_concurrent_spacelike(self):
        o = GeometricOrdering()
        a = geo(0, 0)
        b = geo(0, C_NM_PER_NS)  # simultaneous, 1 light-ns apart -> spacelike
        self.assertTrue(o.concurrent(a, b))

    def test_geometric_resolves_only_beyond_uncertainty(self):
        o = GeometricOrdering()
        # 500ns apart but 1000ns combined uncertainty -> cannot resolve
        a = geo(0, 0, u=500)
        b = geo(500, C_NM_PER_NS, u=500)
        self.assertFalse(o.resolves(a, b))
        # widen the gap beyond uncertainty -> resolves
        c = geo(5000, C_NM_PER_NS, u=500)
        self.assertTrue(o.resolves(a, c))

    def test_resolves_compares_margin_to_true_floor_not_raw_elapsed_time(self):
        # Regression for the fixed bug (see ordering.py module erratum): the
        # original formula tested `abs(dt) > combined_u`, which only looks at
        # raw elapsed time. A ~1,000,000km separation has a required light-time
        # floor of ~3,335,641ns; a `dt` just 500ns past that floor has plenty
        # of raw elapsed time (so the old formula said "resolved") but sits
        # well inside a 2000ns combined-uncertainty band around the TRUE
        # floor - exactly the boundary case a resolution check must catch.
        o = GeometricOrdering()
        far_nm = 1_000_000_000_000_000  # ~1,000,000 km
        required_ns = min_light_time_ns((0, 0, 0), (far_nm, 0, 0))
        self.assertEqual(required_ns, 3335641)

        a = geo(0, 0, u=1000)
        b = geo(required_ns + 500, far_nm, u=1000)  # combined_u = 2000
        old_buggy_formula_says_resolved = abs(b["clock"]["time_ns"] - a["clock"]["time_ns"]) > 2000
        self.assertTrue(old_buggy_formula_says_resolved)  # confirms this IS the trap
        self.assertFalse(o.resolves(a, b))  # correct: margin-to-floor is only 500ns

        # widen the margin well beyond the uncertainty band -> now resolves
        c = geo(required_ns + 5000, far_nm, u=1000)
        self.assertTrue(o.resolves(a, c))

    def test_before_returns_false_when_pair_is_unresolved(self):
        # Regression for the fixed bug (see ordering.py erratum 2): before()
        # used to report a definite verdict even when resolves() said the
        # pair was unresolved, contradicting the class's own docstring
        # ("otherwise reports unresolved... caller treats as concurrent").
        # Two co-located writes 1ns apart with 1000ns uncertainty each are
        # unresolved (combined_u=2000ns, required_ns=0).
        o = GeometricOrdering()
        a = geo(0, 0, u=1000)
        b = geo(1, 0, u=1000)
        self.assertFalse(o.resolves(a, b))
        self.assertFalse(o.before(a, b))
        self.assertFalse(o.before(b, a))
        self.assertTrue(o.concurrent(a, b))
        # widen the gap beyond the uncertainty band -> a definite verdict
        c = geo(5000, 0, u=1000)
        self.assertTrue(o.resolves(a, c))
        self.assertTrue(o.before(a, c))

    def test_logical_happens_before(self):
        o = LogicalOrdering()
        self.assertTrue(o.before(vc(n1=1), vc(n1=2, n2=1)))
        self.assertTrue(o.concurrent(vc(n1=1), vc(n2=1)))

    def test_logical_zero_padding_is_antisymmetric_not_double_before(self):
        # Regression for the fixed bug (see ordering.py erratum 3): {"n1": 1}
        # and {"n1": 1, "n2": 0} are the SAME logical instant (n2's absence
        # and an explicit 0 are equivalent), but they are different dicts, so
        # the old `x != y and leq(x, y)` formula reported `before` in BOTH
        # directions at once - antisymmetry violated.
        o = LogicalOrdering()
        a, b = vc(n1=1), vc(n1=1, n2=0)
        self.assertFalse(o.before(a, b))
        self.assertFalse(o.before(b, a))
        self.assertTrue(o.concurrent(a, b))  # equivalent, not strictly ordered

    def test_logical_before_strict_even_with_extra_zero_keys(self):
        o = LogicalOrdering()
        a, b = vc(n1=1, n2=0), vc(n1=2, n2=0)
        self.assertTrue(o.before(a, b))
        self.assertFalse(o.before(b, a))

    def test_hybrid_uses_geometry_when_resolved_logic_when_not(self):
        h = HybridOrdering()
        # events carry both clocks
        a = {"clock": {"time_ns": 0, "pos_nm": [0,0,0], "u_ns": 100, "vc": {"n1":1}}}
        b = {"clock": {"time_ns": 10000, "pos_nm": [C_NM_PER_NS,0,0], "u_ns": 100, "vc":{"n1":2}}}
        self.assertTrue(h.before(a, b))
        self.assertEqual(h.witness(a,b)["mode"], "geometric")
        # unresolvable geometry falls back to logical
        c = {"clock": {"time_ns": 0, "pos_nm": [0,0,0], "u_ns": 100, "vc": {"n1":1}}}
        d = {"clock": {"time_ns": 50, "pos_nm": [C_NM_PER_NS,0,0], "u_ns": 100, "vc":{"n1":2}}}
        self.assertEqual(h.witness(c,d)["mode"], "logical_fallback")
        self.assertTrue(h.before(c, d))  # decided by vc


if __name__ == "__main__":
    unittest.main()
