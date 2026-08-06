"""SP0-A..D: worldline refactor — moving-node foundation. [SOUND]

See docs/sp0-spec.md for the full contract and the repo-history record
these tests build on (int-vs-float benchmark #10, federated reorder
measurement, causal-substrate null, weak-form causal-divergence theorem).
The frozen kernel (`causally_admissible` / `admissibility_witness`) is
never modified by SP-0; these tests exercise only the additive
`Worldline` types and the `causally_admissible_wl` wrapper.
"""
import ast
import os
import unittest

from horizon.geometry import C_NM_PER_NS, causally_admissible
from horizon.worldline import FixedWorldline, LinearWorldline, causally_admissible_wl

from benchmark.int_vs_float.boundary_gen import MAGNITUDES_NM, boundary_pairs
from benchmark.int_vs_float.float_gate import causally_admissible_float

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTERPLANETARY = "interplanetary (~78,000,000 km, Earth-Mars opposition)"


class TestSP0AFixedWorldlineEquivalence(unittest.TestCase):
    """A `FixedWorldline` reproduces today's fixed-node predicate exactly —
    the constant-worldline special case (F2: any disagreement is a
    refactor break)."""

    def test_agrees_with_frozen_kernel_across_every_boundary_offset(self):
        for label in MAGNITUDES_NM:
            for bv in boundary_pairs(label):
                a = FixedWorldline(bv["p1"])
                b = FixedWorldline(bv["p2"])
                got = causally_admissible_wl(a, bv["t1"], b, bv["t2"])
                expected = causally_admissible(bv["t1"], bv["p1"], bv["t2"], bv["p2"])
                self.assertEqual(got, expected, f"{label} k={bv['offset_nm']}")
                self.assertEqual(got, bv["exact_admissible"])

    def test_agrees_on_hand_picked_stationary_cases(self):
        # null ray boundary and one nm beyond it, from H1-A
        p2_on_cone = (C_NM_PER_NS, 0, 0)
        self.assertTrue(causally_admissible_wl(
            FixedWorldline((0, 0, 0)), 0, FixedWorldline(p2_on_cone), 1))
        p2_beyond = (C_NM_PER_NS + 1, 0, 0)
        self.assertFalse(causally_admissible_wl(
            FixedWorldline((0, 0, 0)), 0, FixedWorldline(p2_beyond), 1))

    def test_position_at_ignores_time_argument(self):
        w = FixedWorldline((7, -3, 42))
        for t in (-10**12, 0, 1, 10**12):
            self.assertEqual(w.position_at(t), (7, -3, 42))


class TestSP0BLinearExactness(unittest.TestCase):
    """A `LinearWorldline` returns exact integer positions matching
    hand-computed reference arithmetic; no float enters the path (F1/F4)."""

    def test_integer_velocity_matches_hand_computed_reference(self):
        p0 = (1_000_000, -2_000_000, 3)
        t0 = 500
        v = (10, -7, 0)  # whole nm/ns
        w = LinearWorldline(p0, t0, v)
        for t in (500, 501, 1000, -500, 10**9):
            dt = t - t0
            expected = (p0[0] + v[0] * dt, p0[1] + v[1] * dt, p0[2] + v[2] * dt)
            got = w.position_at(t)
            self.assertEqual(got, expected)
            self.assertTrue(all(isinstance(c, int) for c in got))

    def test_rational_velocity_is_exact_and_floored(self):
        # 1/3 nm per ns on the x axis: exact rational, floor-divided
        p0 = (0, 0, 0)
        t0 = 0
        v = ((1, 3), (0, 1), (0, 1))
        w = LinearWorldline(p0, t0, v)
        for t, expected_x in [(0, 0), (1, 0), (2, 0), (3, 1), (4, 1), (5, 1), (6, 2),
                               (-1, -1), (-3, -1), (-4, -2)]:
            got = w.position_at(t)
            self.assertEqual(got, (expected_x, 0, 0), f"t={t}")
            self.assertIsInstance(got[0], int)

    def test_negative_denominator_normalized_same_as_positive(self):
        w_pos = LinearWorldline((0, 0, 0), 0, ((1, 3), (0, 1), (0, 1)))
        w_neg = LinearWorldline((0, 0, 0), 0, ((-1, -3), (0, 1), (0, 1)))
        for t in range(-10, 10):
            self.assertEqual(w_pos.position_at(t), w_neg.position_at(t))

    def test_zero_denominator_rejected(self):
        with self.assertRaises(ValueError):
            LinearWorldline((0, 0, 0), 0, ((1, 0), (0, 1), (0, 1)))

    def test_t0_offset_and_reversal_are_exact(self):
        # a ship coasting at exactly c/2 (integer nm/ns) from a nonzero t0
        v_half_c = C_NM_PER_NS // 2
        w = LinearWorldline((1_000, 2_000, 3_000), 1_000_000, (v_half_c, 0, 0))
        self.assertEqual(w.position_at(1_000_000), (1_000, 2_000, 3_000))
        self.assertEqual(w.position_at(1_000_001), (1_000 + v_half_c, 2_000, 3_000))
        self.assertEqual(w.position_at(999_999), (1_000 - v_half_c, 2_000, 3_000))

    def test_no_float_in_worldline_module_ast(self):
        # float-guard tie-in (F1): parse horizon/worldline.py directly and
        # confirm zero float literals, true-division, sqrt/float() calls.
        path = os.path.join(ROOT, "horizon", "worldline.py")
        with open(path) as f:
            tree = ast.parse(f.read(), filename=path)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                violations.append(("float literal", node.lineno))
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                violations.append(("true division", node.lineno))
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name in ("sqrt", "float"):
                    violations.append((f"{name}() call", node.lineno))
        self.assertEqual(violations, [])


class TestSP0CMovingNodeAdmissibility(unittest.TestCase):
    """The gate evaluates `position_at(t_event)` for each endpoint: a signal
    admissible against the evaluated positions is ADMITTED, one that would
    require FTL closure is REJECTED — including an interplanetary-scale
    case where the nanometer lattice matters."""

    def test_ship_moving_toward_signal_source_is_admitted(self):
        # ground station fixed at origin; ship coasts along +x at c/2,
        # starting far enough away that a naive "ship never moves" check
        # would reject, but the ship's actual (moving) position at the
        # signal's arrival time is well within the light cone.
        ground = FixedWorldline((0, 0, 0))
        v_half_c = C_NM_PER_NS // 2
        ship = LinearWorldline((C_NM_PER_NS * 100, 0, 0), 0, (-v_half_c, 0, 0))
        t1 = 0
        t2 = 300  # ship has coasted to x = 100c - 150c/1... compute exactly below
        ship_pos_at_t2 = ship.position_at(t2)
        # sanity: ship has moved from 100c toward the origin
        self.assertLess(ship_pos_at_t2[0], C_NM_PER_NS * 100)
        # admissible iff (c*dt)^2 >= dist^2 against the EVALUATED position
        expected = causally_admissible(t1, (0, 0, 0), t2, ship_pos_at_t2)
        got = causally_admissible_wl(ground, t1, ship, t2)
        self.assertEqual(got, expected)

    def test_stationary_evaluation_would_wrongly_reject_but_moving_is_admitted(self):
        # construct a case where the ship's position AT t0 (if frozen) is
        # outside the light cone reachable by t2, but its actual position
        # at t2 (after coasting inward) is inside it -- proves the gate is
        # really using position_at(t_event), not a frozen snapshot.
        t1, t2 = 0, 10
        far_x = C_NM_PER_NS * 1000  # unreachable from origin in 10 ns if stationary
        self.assertFalse(causally_admissible(t1, (0, 0, 0), t2, (far_x, 0, 0)))
        # ship starts at far_x but is already coasting inward fast enough
        # that by t2 it sits well inside the reachable cone (near the origin)
        v_in = -(far_x // 10 - 1)  # lands near x=10nm by t2, well inside c*t2
        ship = LinearWorldline((far_x, 0, 0), t1, (v_in, 0, 0))
        ground = FixedWorldline((0, 0, 0))
        got = causally_admissible_wl(ground, t1, ship, t2)
        expected = causally_admissible(t1, (0, 0, 0), t2, ship.position_at(t2))
        self.assertEqual(got, expected)
        self.assertTrue(got)

    def test_interplanetary_scale_nanometer_lattice_matters(self):
        # reuse the exact interplanetary boundary vector: place the moving
        # node's worldline so it passes through the precise on-cone point
        # at t2, then nudge by 1 nm -- admitted on-cone, rejected 1nm past.
        bv_on = next(b for b in boundary_pairs(INTERPLANETARY) if b["offset_nm"] == 0)
        bv_past = next(b for b in boundary_pairs(INTERPLANETARY) if b["offset_nm"] == 1)
        ground = FixedWorldline(bv_on["p1"])
        for bv in (bv_on, bv_past):
            # ship starts at the origin-side event and coasts exactly to
            # bv["p2"] by t2 (rational velocity, exact by construction)
            dx, dy, dz = bv["p2"]
            ship = LinearWorldline(
                (0, 0, 0), bv["t1"],
                ((dx, bv["t2"]), (dy, bv["t2"]), (dz, bv["t2"])))
            self.assertEqual(ship.position_at(bv["t2"]), bv["p2"])
            got = causally_admissible_wl(ground, bv["t1"], ship, bv["t2"])
            self.assertEqual(got, bv["exact_admissible"], f"offset={bv['offset_nm']}")
        self.assertTrue(causally_admissible_wl(
            ground, bv_on["t1"],
            LinearWorldline((0, 0, 0), bv_on["t1"],
                             tuple((c, bv_on["t2"]) for c in bv_on["p2"])),
            bv_on["t2"]))
        self.assertFalse(causally_admissible_wl(
            ground, bv_past["t1"],
            LinearWorldline((0, 0, 0), bv_past["t1"],
                             tuple((c, bv_past["t2"]) for c in bv_past["p2"])),
            bv_past["t2"]))


class TestSP0DIntegerNecessityTieIn(unittest.TestCase):
    """Ties SP-0 to the merged int-vs-float benchmark (#10): at
    interplanetary distance, evaluating a moving node's worldline in
    float64 flips the verdict at an offset where the integer worldline
    does not."""

    def test_float_worldline_evaluation_flips_verdict_integer_does_not(self):
        bv = next(b for b in boundary_pairs(INTERPLANETARY) if b["offset_nm"] == 1000)
        self.assertFalse(bv["exact_admissible"])  # 1000 nm past the null cone: spacelike

        # the moving node's worldline evaluates EXACTLY to bv["p2"] at t2
        dx, dy, dz = bv["p2"]
        ship = LinearWorldline(
            (0, 0, 0), bv["t1"],
            ((dx, bv["t2"]), (dy, bv["t2"]), (dz, bv["t2"])))
        ground = FixedWorldline(bv["p1"])

        integer_verdict = causally_admissible_wl(ground, bv["t1"], ship, bv["t2"])
        self.assertFalse(integer_verdict, "integer worldline must reject the spacelike pair")

        evaluated_p2 = ship.position_at(bv["t2"])
        self.assertEqual(evaluated_p2, bv["p2"])  # exact, no drift from the reference

        float_verdict = causally_admissible_float(
            bv["t1"], bv["p1"], bv["t2"], evaluated_p2, precision="float64", eps=0.0)
        self.assertTrue(float_verdict,
                         "float64 evaluation of the same worldline-derived point "
                         "wrongly admits a spacelike pair at interplanetary scale")
        self.assertNotEqual(integer_verdict, float_verdict)


if __name__ == "__main__":
    unittest.main()
