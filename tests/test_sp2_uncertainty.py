"""SP2-A..E: trajectory-uncertainty envelope and the two-floor
ADMITTED/REJECTED/APPARATUS_LIMITED gate. [SOUND]

See docs/sp2-spec.md for the positioning record, the envelope model, the
two-floor rule, and the registered falsifiers. Builds on SP-0 (Worldline,
#11) and SP-1 (occultation/light-delay, #12); the frozen kernel and prior
SP modules are never modified here, only imported.

All scenarios use a colinear axis fixture (ground station at the origin,
envelope center on the +x axis) so the envelope's extremal points
(center +/- radius along that axis) are exact integers, letting every
verdict be cross-checked directly against `causally_admissible` at the
literal boundary points - not just trusted from the closed-form derivation
in `horizon.two_floor`.
"""
import unittest

from horizon.geometry import C_NM_PER_NS, causally_admissible
from horizon.worldline import FixedWorldline
from horizon.uncertainty import TrajectoryEnvelope, _ceil_div
from horizon.two_floor import two_floor_verdict

DX = C_NM_PER_NS * 1000  # ~1000 ns light-time scale
NOMINAL = FixedWorldline((DX, 0, 0))
P1 = (0, 0, 0)
T1 = 0


def _extremal_points(envelope, t2):
    center = envelope.center_at(t2)
    r = envelope.radius_at(t2)
    far = (center[0] + r, center[1], center[2])
    near = (max(0, center[0] - r), center[1], center[2])
    return far, near


class TestSP2AEnvelopeGrowthExactAndMonotone(unittest.TestCase):
    def setUp(self):
        self.env = TrajectoryEnvelope(NOMINAL, 100, 500_000, 100)

    def test_radius_matches_hand_reference(self):
        for t in (100, 150, 200, 500, 990):
            dt = t - 100
            expected = 500_000 * dt + _ceil_div(100 * dt * dt, 2)
            got = self.env.radius_at(t)
            self.assertEqual(got, expected, f"t={t}")
            self.assertIsInstance(got, int)

    def test_radius_is_zero_at_contact_time(self):
        self.assertEqual(self.env.radius_at(100), 0)

    def test_radius_is_strictly_monotone_increasing(self):
        ts = [100, 150, 151, 300, 990]
        radii = [self.env.radius_at(t) for t in ts]
        for a, b in zip(radii, radii[1:]):
            self.assertLess(a, b)

    def test_query_before_contact_time_rejected(self):
        with self.assertRaises(ValueError):
            self.env.radius_at(99)

    def test_ceiling_rounding_never_underestimates(self):
        # a_max*dt^2 odd -> exact half is a .5; ceil must round UP, never
        # truncate down, so the envelope never shrinks below the true
        # kinematic bound (F1's "growing only helps APPARATUS_LIMITED,
        # never causes a false ADMIT/REJECT" argument depends on this)
        env = TrajectoryEnvelope(NOMINAL, 0, 0, 1)  # a_max=1, v_unc=0
        # dt=1: a_max*dt^2 = 1, true half = 0.5, must ceil to 1
        self.assertEqual(env.radius_at(1), 1)

    def test_runtime_float_inputs_rejected(self):
        with self.assertRaises(TypeError):
            TrajectoryEnvelope(NOMINAL, 0.0, 1, 1)
        with self.assertRaises(TypeError):
            TrajectoryEnvelope(NOMINAL, 0, 1.0, 1)
        with self.assertRaises(TypeError):
            TrajectoryEnvelope(NOMINAL, 0, 1, 1.0)
        with self.assertRaises(TypeError):
            TrajectoryEnvelope(NOMINAL, 0, 1, 1, u_measured_nm=0.5)

    def test_negative_uncertainty_bounds_rejected(self):
        # v_unc/a_max/u_measured are magnitudes; a negative one would let
        # radius_at return a negative radius, breaking the r >= 0
        # assumption two_floor_verdict's inequalities depend on
        with self.assertRaises(ValueError):
            TrajectoryEnvelope(NOMINAL, 0, -1, 1)
        with self.assertRaises(ValueError):
            TrajectoryEnvelope(NOMINAL, 0, 1, -1)
        with self.assertRaises(ValueError):
            TrajectoryEnvelope(NOMINAL, 0, 1, 1, u_measured_nm=-1)
        with self.assertRaises(TypeError):
            self.env.radius_at(100.0)


class TestSP2BCollapseOnContact(unittest.TestCase):
    def test_collapse_discards_accumulated_growth(self):
        stale = TrajectoryEnvelope(NOMINAL, 100, 500_000, 100)
        grown = stale.radius_at(990)
        self.assertGreater(grown, 0)
        fresh = stale.collapse(990, FixedWorldline((1, 2, 3)), u_measured_nm=0)
        # the fresh envelope's radius at the VERY SAME instant is the
        # measured uncertainty, NOT the old envelope's accumulated growth
        self.assertEqual(fresh.radius_at(990), 0)
        self.assertNotEqual(fresh.radius_at(990), grown)

    def test_growth_resumes_from_the_new_contact_time(self):
        stale = TrajectoryEnvelope(NOMINAL, 100, 500_000, 100)
        fresh = stale.collapse(990, NOMINAL, u_measured_nm=0)
        self.assertEqual(fresh.radius_at(991), 500_000 * 1 + _ceil_div(100 * 1, 2))
        self.assertGreater(fresh.radius_at(1000), fresh.radius_at(991))

    def test_collapse_can_carry_nonzero_measured_uncertainty(self):
        stale = TrajectoryEnvelope(NOMINAL, 100, 500_000, 100)
        fresh = stale.collapse(990, NOMINAL, u_measured_nm=42)
        self.assertEqual(fresh.radius_at(990), 42)

    def test_collapse_preserves_rates_unless_overridden(self):
        stale = TrajectoryEnvelope(NOMINAL, 100, 500_000, 100)
        fresh = stale.collapse(990, NOMINAL, u_measured_nm=0)
        self.assertEqual(fresh.v_unc, stale.v_unc)
        self.assertEqual(fresh.a_max, stale.a_max)
        tighter = stale.collapse(990, NOMINAL, u_measured_nm=0,
                                 v_unc_nm_per_ns=1, a_max_nm_per_ns2=1)
        self.assertEqual(tighter.v_unc, 1)
        self.assertEqual(tighter.a_max, 1)


class TestSP2CThreeVerdicts(unittest.TestCase):
    """Envelope centered DX = C*1000 nm from the origin; t1=0, p1=origin.
    v_unc=500_000, a_max=100, t_c=0 -- chosen (see docs/sp2-spec.md) so the
    three verdicts fall at clean, well-separated t2 values, each
    cross-checked directly against causally_admissible at the exact
    colinear extremal points, not just trusted from the closed form."""

    def setUp(self):
        self.env = TrajectoryEnvelope(NOMINAL, 0, 500_000, 100)

    def _check(self, t2, expected_verdict):
        far, near = _extremal_points(self.env, t2)
        worst_case_ok = causally_admissible(T1, P1, t2, far)
        best_case_ok = causally_admissible(T1, P1, t2, near)
        res = two_floor_verdict(T1, P1, t2, self.env)
        self.assertEqual(res["verdict"], expected_verdict, f"t2={t2}")
        if expected_verdict == "ADMITTED":
            self.assertTrue(worst_case_ok and best_case_ok)
        elif expected_verdict == "REJECTED":
            self.assertFalse(worst_case_ok or best_case_ok)
        else:
            self.assertFalse(worst_case_ok)
            self.assertTrue(best_case_ok)
        return res

    def test_envelope_fully_outside_even_in_vacuum_is_rejected(self):
        self._check(900, "REJECTED")

    def test_envelope_straddling_the_cone_is_apparatus_limited(self):
        self._check(1000, "APPARATUS_LIMITED")

    def test_envelope_fully_inside_the_cone_is_admitted(self):
        self._check(1050, "ADMITTED")

    def test_negative_dt_is_unconditionally_rejected(self):
        # t2 < t1: every in-envelope position fails regardless of distance
        # (the kernel's own dt<0 short-circuit) - the degenerate REJECT case
        res = two_floor_verdict(500, P1, 100, self.env)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["reason"], "negative_dt")

    def test_negative_dt_rejected_even_when_t2_precedes_envelope_contact(self):
        # regression: the negative-dt check must run BEFORE radius_at is
        # ever called on either side, since radius_at raises for a query
        # time before that envelope's OWN contact time - a t2 that is both
        # earlier than t1 AND earlier than the envelope's t_c must still
        # cleanly resolve to REJECTED, not propagate a ValueError
        env = TrajectoryEnvelope(NOMINAL, 500, 1000, 1)
        res = two_floor_verdict(1000, P1, 100, env)  # t2=100 < t1 and < t_c=500
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["reason"], "negative_dt")

    def test_runtime_float_t1_or_position_component_rejected(self):
        with self.assertRaises(TypeError):
            two_floor_verdict(0.0, P1, 100, self.env)
        with self.assertRaises(TypeError):
            two_floor_verdict(T1, (0.0, 0, 0), 100, self.env)


class TestSP2FUncertaintyOnBothSides(unittest.TestCase):
    """two_floor_verdict must account for uncertainty on the CAUSAL
    SOURCE, not just the target: a TrajectoryEnvelope passed as `p1` is
    resolved to its center/radius exactly like the `envelope` argument,
    and the two radii are summed."""

    def test_envelope_as_p1_does_not_crash_and_sums_radii(self):
        source_env = TrajectoryEnvelope(FixedWorldline((100, 0, 0)), 0, 1000, 1)
        target = FixedWorldline((0, 0, 0))
        target_env = TrajectoryEnvelope(target, 0, 0, 0)  # zero-radius envelope
        res_plain = two_floor_verdict(100, (100, 0, 0), 200, target_env)
        res_uncertain_source = two_floor_verdict(100, source_env, 200, target_env)
        self.assertNotEqual(res_plain["witness"]["radius_nm"],
                            res_uncertain_source["witness"]["radius_nm"])
        self.assertEqual(res_uncertain_source["witness"]["radius1_nm"],
                         source_env.radius_at(100))
        self.assertEqual(res_uncertain_source["witness"]["radius_nm"],
                         source_env.radius_at(100) + target_env.radius_at(200))

    def test_definite_definite_matches_causally_admissible_exactly(self):
        # r1=r2=0 must collapse to the plain kernel boolean, no straddle
        for t2, expected in ((999, False), (1000, True), (1050, True)):
            p2 = NOMINAL.position_at(t2)
            expected_verdict = "ADMITTED" if expected else "REJECTED"
            res = two_floor_verdict(T1, P1, t2, p2)
            self.assertEqual(res["verdict"], expected_verdict, f"t2={t2}")
            self.assertEqual(res["witness"]["radius_nm"], 0)


class TestSP2DTwoFloorAsymmetry(unittest.TestCase):
    """REJECT must fire ONLY against the absolute vacuum floor (best case
    across the WHOLE envelope), never against a naive single-point check.
    t2=999 below is chosen so the nominal CENTER point alone already fails
    causally_admissible, but the envelope's near edge (best case) still
    passes - a naive point-estimate gate would wrongly REJECT here; the
    honest verdict is APPARATUS_LIMITED (F2)."""

    def setUp(self):
        self.env = TrajectoryEnvelope(NOMINAL, 0, 500_000, 100)

    def test_center_point_failing_does_not_force_rejected(self):
        t2 = 999
        center = self.env.center_at(t2)
        self.assertFalse(causally_admissible(T1, P1, t2, center),
                         "sanity: the naive point-estimate really does fail here")
        far, near = _extremal_points(self.env, t2)
        self.assertTrue(causally_admissible(T1, P1, t2, near),
                        "sanity: but SOME in-envelope position is admissible")
        res = two_floor_verdict(T1, P1, t2, self.env)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertNotEqual(res["verdict"], "REJECTED")

    def test_rejected_only_when_the_near_edge_itself_fails(self):
        t2 = 900  # even the envelope's closest point still fails
        far, near = _extremal_points(self.env, t2)
        self.assertFalse(causally_admissible(T1, P1, t2, near))
        res = two_floor_verdict(T1, P1, t2, self.env)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["reason"],
                         "best_case_in_envelope_still_fails_vacuum_floor")


class TestSP2EUncertaintyShrinksApparatusLimitedBand(unittest.TestCase):
    """Tighter uncertainty parameters (smaller v_unc/a_max) AND a fresher
    contact (smaller elapsed time since t_c) both narrow the band of t2
    values that resolve to APPARATUS_LIMITED - the physical analogue of
    LCC's 2*epsilon <= dmin resolution bound (see docs/sp2-spec.md)."""

    def setUp(self):
        self.loose = TrajectoryEnvelope(NOMINAL, 0, 500_000, 100)

    def test_tighter_rate_bounds_resolve_what_was_straddling(self):
        tight = TrajectoryEnvelope(NOMINAL, 0, 100, 1)
        for t2, expected_tight in ((999, "REJECTED"), (1001, "ADMITTED")):
            loose_v = two_floor_verdict(T1, P1, t2, self.loose)["verdict"]
            tight_v = two_floor_verdict(T1, P1, t2, tight)["verdict"]
            self.assertEqual(loose_v, "APPARATUS_LIMITED", f"t2={t2}")
            self.assertEqual(tight_v, expected_tight, f"t2={t2}")
            self.assertLess(tight.radius_at(t2), self.loose.radius_at(t2))

    def test_fresher_contact_resolves_what_was_straddling(self):
        # a new contact at t_c=990 (same rate bounds, zero measured residual)
        # shrinks the envelope relative to the stale t_c=0 contact
        fresh = self.loose.collapse(990, NOMINAL, u_measured_nm=0)
        for t2, expected_fresh in ((999, "REJECTED"), (1001, "ADMITTED")):
            stale_v = two_floor_verdict(T1, P1, t2, self.loose)["verdict"]
            fresh_v = two_floor_verdict(T1, P1, t2, fresh)["verdict"]
            self.assertEqual(stale_v, "APPARATUS_LIMITED", f"t2={t2}")
            self.assertEqual(fresh_v, expected_fresh, f"t2={t2}")
            self.assertLess(fresh.radius_at(t2), self.loose.radius_at(t2))


if __name__ == "__main__":
    unittest.main()
