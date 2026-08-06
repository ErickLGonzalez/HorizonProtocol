"""SP3-A..E: proper-time divergence, reconciled by lineage + the light
cone, never by comparing clocks. [SOUND]

See docs/sp3-spec.md for the positioning record (weak-form causal-
divergence theorem), the weak-field proper-time model, the reconciliation
rule, and the registered falsifiers. Builds on SP-0 (Worldline, #11),
SP-1 (occultation/light-delay, #12), and SP-2 (uncertainty envelope /
two-floor gate). The frozen kernel and every prior SP module are never
modified here, only imported.
"""
import math
import unittest

from horizon.geometry import C_NM_PER_NS, causally_admissible
from horizon.worldline import FixedWorldline, LinearWorldline, causally_admissible_wl
from horizon.occultation import occultation_interval
from horizon.uncertainty import TrajectoryEnvelope
from horizon.proper_time import weak_field_rate, ProperTimeClock, ProperTimeStamp
from horizon.reconcile import Event, reconcile


class TestSP3AProperTimeRateIsExactRational(unittest.TestCase):
    def setUp(self):
        self.v = C_NM_PER_NS // 10  # 0.1c
        self.rate_ship = weak_field_rate(self.v * self.v, 0)
        self.rate_ground = weak_field_rate(0, 0)
        self.ship_clock = ProperTimeClock("ship", *self.rate_ship)
        self.ground_clock = ProperTimeClock("ground", *self.rate_ground)

    def test_rate_matches_hand_computed_weak_field_formula(self):
        c2 = C_NM_PER_NS * C_NM_PER_NS
        expected_ship = (2 * c2 - self.v * self.v, 2 * c2)
        self.assertEqual(self.rate_ship, expected_ship)
        self.assertEqual(self.rate_ground, (2 * c2, 2 * c2))

    def test_stationary_clock_matches_coordinate_time_exactly(self):
        for t in (0, 1_000, 1_000_000):
            self.assertEqual(self.ground_clock.tau_at(t), t)

    def test_moving_clock_accumulates_less_proper_time(self):
        for t in (1_000, 10_000, 1_000_000):
            dt = t
            expected = (self.rate_ship[0] * dt) // self.rate_ship[1]
            self.assertEqual(self.ship_clock.tau_at(t), expected)
            self.assertLess(self.ship_clock.tau_at(t), self.ground_clock.tau_at(t))

    def test_two_nodes_at_different_velocities_diverge(self):
        # exact hand reference at t=1,000,000: ship ticks at (2c^2-v^2)/2c^2
        t = 1_000_000
        tau_ground = t
        tau_ship = ((2 * C_NM_PER_NS**2 - self.v**2) * t) // (2 * C_NM_PER_NS**2)
        self.assertEqual(self.ground_clock.tau_at(t), tau_ground)
        self.assertEqual(self.ship_clock.tau_at(t), tau_ship)
        self.assertGreater(tau_ground - tau_ship, 0)

    def test_zero_velocity_zero_potential_rate_is_exactly_one(self):
        self.assertEqual(weak_field_rate(0, 0), (2 * C_NM_PER_NS**2, 2 * C_NM_PER_NS**2))

    def test_negative_v_squared_rejected(self):
        with self.assertRaises(ValueError):
            weak_field_rate(-1, 0)

    def test_runtime_float_inputs_rejected(self):
        with self.assertRaises(TypeError):
            weak_field_rate(1.0, 0)
        with self.assertRaises(TypeError):
            ProperTimeClock("x", 1.0, 1)
        with self.assertRaises(TypeError):
            ProperTimeClock("x", 1, 1).tau_at(1.0)
        with self.assertRaises(TypeError):
            ProperTimeStamp("x", 1.0)

    def test_zero_rate_denominator_rejected(self):
        with self.assertRaises(ValueError):
            ProperTimeClock("x", 1, 0)


class TestSP3BNoClockComparisonOrdering(unittest.TestCase):
    """The theorem's "no shared now" enforced in code: comparing
    ProperTimeStamps from two DIFFERENT nodes must raise, not silently
    return an answer (F2 - the core rule this sprint exists to forbid)."""

    def setUp(self):
        self.ship_clock = ProperTimeClock("ship", *weak_field_rate(
            (C_NM_PER_NS // 10) ** 2, 0))
        self.ground_clock = ProperTimeClock("ground", *weak_field_rate(0, 0))

    def test_cross_node_less_than_raises(self):
        a = self.ship_clock.stamp_at(1000)
        b = self.ground_clock.stamp_at(1000)
        with self.assertRaises(ValueError):
            a < b
        with self.assertRaises(ValueError):
            b < a

    def test_cross_node_all_comparisons_raise(self):
        a = self.ship_clock.stamp_at(1000)
        b = self.ground_clock.stamp_at(1000)
        for op in (lambda: a <= b, lambda: a > b, lambda: a >= b, lambda: a == b):
            with self.assertRaises(ValueError):
                op()

    def test_same_node_comparison_is_fine(self):
        a = self.ship_clock.stamp_at(1000)
        b = self.ship_clock.stamp_at(2000)
        self.assertTrue(a < b)
        self.assertFalse(a > b)
        self.assertTrue(a == self.ship_clock.stamp_at(1000))

    def test_no_code_path_in_reconcile_reads_proper_time_stamp_for_its_verdict(self):
        # attach WILDLY misleading proper-time stamps (ship "before" ground
        # by tau, though physically/causally ground is before ship - same
        # construction as SP3-C) and confirm the verdict is identical
        # whether or not proper_time_stamp is even supplied.
        v = C_NM_PER_NS // 10
        ship_wl = LinearWorldline((0, 0, 0), 0, (v, 0, 0))
        ground_wl = FixedWorldline(ship_wl.position_at(1_000_000))
        ground_vc, ship_vc = {"ground": 1}, {"ground": 1, "ship": 1}

        with_stamps = reconcile(
            Event("ground", ground_vc, 1_000_000, ground_wl,
                 ProperTimeStamp("ground", 999_999_999)),
            Event("ship", ship_vc, 1_000_005, ship_wl,
                 ProperTimeStamp("ship", 1)))  # absurdly "earlier" by tau
        without_stamps = reconcile(
            Event("ground", ground_vc, 1_000_000, ground_wl),
            Event("ship", ship_vc, 1_000_005, ship_wl))
        self.assertEqual(with_stamps["verdict"], without_stamps["verdict"])
        self.assertEqual(with_stamps["witness"]["physical_check"],
                         without_stamps["witness"]["physical_check"])
        self.assertFalse(with_stamps["witness"]["proper_time_used_for_ordering"])


class TestSP3CLineageAndConeOrderDespiteDivergence(unittest.TestCase):
    """Headline: the ship's clock has drifted far enough behind ground's
    that a naive tau comparison gives the WRONG order, but lineage + the
    light cone recover the correct one."""

    def setUp(self):
        self.v = C_NM_PER_NS // 10
        self.ship_clock = ProperTimeClock("ship", *weak_field_rate(self.v * self.v, 0))
        self.ground_clock = ProperTimeClock("ground", *weak_field_rate(0, 0))
        self.ship_wl = LinearWorldline((0, 0, 0), 0, (self.v, 0, 0))
        self.t_g = 1_000_000
        self.t_s = 1_000_005
        # ground station co-located with the ship's position at t_g (e.g. a
        # relay beacon the ship passes) so the light-cone check only has to
        # cross the SHORT gap between the two events, not the ship's whole
        # accumulated flight since t=0
        self.ground_wl = FixedWorldline(self.ship_wl.position_at(self.t_g))

    def test_tau_comparison_would_give_the_wrong_order(self):
        tau_g = self.ground_clock.tau_at(self.t_g)
        tau_s = self.ship_clock.tau_at(self.t_s)
        self.assertLess(self.t_g, self.t_s)  # ground's event IS earlier in coordinate time
        self.assertLess(tau_s, tau_g)        # but naive tau comparison says the OPPOSITE

    def test_lineage_and_cone_recover_the_correct_order(self):
        self.assertTrue(causally_admissible_wl(
            self.ground_wl, self.t_g, self.ship_wl, self.t_s))
        ev_ground = Event("ground", {"ground": 1}, self.t_g, self.ground_wl,
                          self.ground_clock.stamp_at(self.t_g))
        ev_ship = Event("ship", {"ground": 1, "ship": 1}, self.t_s, self.ship_wl,
                        self.ship_clock.stamp_at(self.t_s))
        res = reconcile(ev_ground, ev_ship)
        self.assertEqual(res["verdict"], "BEFORE")
        self.assertEqual(res["witness"]["physical_check"]["verdict"], "ADMITTED")
        self.assertFalse(res["witness"]["proper_time_used_for_ordering"])


class TestSP3DConcurrentUnderDivergence(unittest.TestCase):
    """Zero false-supersession (#548, under relativistic clocks): a
    genuinely concurrent pair is retained, never force-ordered - whether
    because there is no lineage claim at all, or because a lineage claim
    exists but the light cone forbids it (F3: never silently trusted)."""

    def test_no_lineage_edge_is_concurrent(self):
        ev_a = Event("a", {"a": 1}, 0, FixedWorldline((0, 0, 0)))
        ev_b = Event("b", {"b": 1}, 0, FixedWorldline((C_NM_PER_NS * 10, 0, 0)))
        res = reconcile(ev_a, ev_b)
        self.assertEqual(res["verdict"], "CONCURRENT")
        self.assertEqual(res["witness"]["reason"], "no_lineage_edge_either_direction")

    def test_lineage_claim_the_light_cone_forbids_is_not_trusted(self):
        # ground's write claims (via vector clock) to precede the ship's,
        # but the ship has been cruising since t=0 and is already far
        # beyond where light from ground's event could reach by t_s - the
        # claim is physically impossible and must NOT be silently admitted
        v = C_NM_PER_NS // 10
        ground_wl = FixedWorldline((0, 0, 0))
        ship_wl = LinearWorldline((100, 0, 0), 0, (v, 0, 0))
        t_g, t_s = 1_000, 1_005
        self.assertFalse(causally_admissible_wl(ground_wl, t_g, ship_wl, t_s))
        ev_ground = Event("ground", {"ground": 1}, t_g, ground_wl)
        ev_ship = Event("ship", {"ground": 1, "ship": 1}, t_s, ship_wl)
        res = reconcile(ev_ground, ev_ship)
        self.assertEqual(res["verdict"], "CONCURRENT")
        self.assertEqual(res["witness"]["reason"],
                         "lineage_claims_an_edge_the_light_cone_forbids")
        self.assertEqual(res["witness"]["physical_check"]["verdict"], "REJECTED")


class TestSP3EnvelopeOnEitherSide(unittest.TestCase):
    """reconcile() must handle an uncertain CAUSAL SOURCE, not just an
    uncertain target: a lineage-earlier event whose position is only known
    via a TrajectoryEnvelope must still resolve to BEFORE/AFTER/
    APPARATUS_LIMITED via the physical check, never crash."""

    def test_uncertain_source_exact_target_resolves_without_crashing(self):
        ground = FixedWorldline((0, 0, 0))
        source_env = TrajectoryEnvelope(FixedWorldline((100, 0, 0)), 0, 1000, 1)
        # lineage: the uncertain-position event is the ANCESTOR
        ev_source = Event("ship", {"ship": 1}, 100, source_env)
        ev_target = Event("ground", {"ship": 1, "ground": 1}, 200, ground)
        res = reconcile(ev_source, ev_target)
        self.assertEqual(res["verdict"], "BEFORE")
        phys = res["witness"]["physical_check"]
        self.assertEqual(phys["verdict"], "ADMITTED")
        self.assertEqual(phys["radius1_nm"], source_env.radius_at(100))
        self.assertEqual(phys["radius2_nm"], 0)


def _closed_form_ymax(dx, r):
    def down(y):
        return y * y * (dx * dx - r * r) <= r * r * dx * dx
    q = (r * r * dx * dx) // (dx * dx - r * r)
    y = math.isqrt(q)
    while down(y + 1):
        y += 1
    while not down(y):
        y -= 1
    return y


class TestSP3EFullStack(unittest.TestCase):
    """SP-1 occultation + SP-2 uncertainty + SP-3 proper time, combined:
    a ship flies behind a body (occultation geometry decides the last
    confirmed contact), its position afterward is only known via a growing
    SP-2 envelope, and its clock has diverged from ground's throughout.
    reconcile() returns the honest verdict from lineage + the physical
    check (here, the two-floor gate over the envelope) - never from
    comparing the divergent clocks, which are attached for provenance only.
    """

    def setUp(self):
        self.v = C_NM_PER_NS // 10
        dx = C_NM_PER_NS * 500
        r = dx * 3 // 10
        y_max = _closed_form_ymax(dx, r)
        y0 = -3 * y_max
        t_hi = (6 * y_max) // self.v
        self.ship_wl = LinearWorldline((dx, y0, 0), 0, (0, self.v, 0))
        self.ground_wl = FixedWorldline((0, 0, 0))
        body = FixedWorldline((dx, 0, 0))
        self.t_enter, self.t_exit = occultation_interval(
            0, t_hi, self.ship_wl, self.ground_wl, body, r)
        # last confirmed contact is BEFORE the ship enters occultation; no
        # new fix has arrived by query time, so the envelope has grown
        # across the entire blackout plus the time since reconnect
        self.env = TrajectoryEnvelope(self.ship_wl, self.t_enter, 100_000, 1)
        self.t2 = self.t_exit + 500
        self.t1 = 6_247  # a ground write shortly before the query time

        self.ship_clock = ProperTimeClock("ship", *weak_field_rate(self.v * self.v, 0))
        self.ground_clock = ProperTimeClock("ground", *weak_field_rate(0, 0))

    def test_envelope_straddles_and_reconcile_is_honest(self):
        ev_ground = Event("ground", {"ground": 1}, self.t1, self.ground_wl,
                          self.ground_clock.stamp_at(self.t1))
        ev_ship = Event("ship", {"ground": 1, "ship": 1}, self.t2, self.env,
                        self.ship_clock.stamp_at(self.t2))
        res = reconcile(ev_ground, ev_ship)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        phys = res["witness"]["physical_check"]
        self.assertEqual(phys["verdict"], "APPARATUS_LIMITED")
        self.assertIn("radius_nm", phys)  # came from two_floor over the envelope
        self.assertFalse(res["witness"]["proper_time_used_for_ordering"])
        # the divergent clocks are real (informational) but play no role:
        self.assertNotEqual(
            self.ground_clock.tau_at(self.t1), self.ship_clock.tau_at(self.t2))

    def test_tighter_envelope_resolves_what_was_straddling(self):
        # a fresh, tight envelope anchored at t_exit (i.e. a much better
        # position estimate right at reconnect) resolves the SAME lineage
        # edge definitively - showing the straddle above is a genuine
        # property of the wide, stale envelope, not an artifact of
        # reconcile() itself (the SP2-E narrowing effect, through the
        # full stack)
        tight_env = TrajectoryEnvelope(self.ship_wl, self.t_exit, 1, 1)
        self.assertLess(tight_env.radius_at(self.t2), self.env.radius_at(self.t2))
        ev_ground = Event("ground", {"ground": 1}, self.t1, self.ground_wl)
        ev_ship = Event("ship", {"ground": 1, "ship": 1}, self.t2, tight_env)
        res = reconcile(ev_ground, ev_ship)
        self.assertEqual(res["verdict"], "BEFORE")
        self.assertEqual(res["witness"]["physical_check"]["verdict"], "ADMITTED")


if __name__ == "__main__":
    unittest.main()
