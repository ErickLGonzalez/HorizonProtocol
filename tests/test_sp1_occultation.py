"""SP1-A..E: occultation (partition/reconnect in space). [SOUND]

See docs/sp1-spec.md for the occultation-as-partition framing, the exact
geometry, the emergent-reorder rule, and the registered falsifiers. Builds
on SP-0 (Worldline, causally_admissible_wl, merged #11); the frozen kernel
and the SP-0 wrapper are never modified here, only imported.

"The causal substrate" in this repo is `mnemesis.memory.CausalMemory` with
`GeometricOrdering` (MNX1, merged) - its `put(..., supersedes=[...])`
validates each claimed supersession via `ordering.before`, which is this
repo's concrete form of the handoff's `may_supersede` gate; a rejected
claim (`reason == "supersedes_non_ancestor"`) is this repo's form of a
stale write refused, never force-applied; `get()` returning `CONFLICT`
with multiple candidates is concurrent writes retained, never
force-picked. See docs/mnemesis-convergence.md for the underlying mapping.
"""
import ast
import math
import os
import unittest

from horizon.geometry import C_NM_PER_NS, causally_admissible, min_light_time_ns
from horizon.worldline import FixedWorldline, LinearWorldline, causally_admissible_wl
from horizon.occultation import is_link_down, occultation_interval
from horizon.light_delay import delivery_time_ns
from mnemesis.memory import CausalMemory, GeometricOrdering

from benchmark.int_vs_float.boundary_gen import boundary_pairs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M_TO_NM = 1_000_000_000
KM_TO_NM = 1_000 * M_TO_NM
INTERPLANETARY = "interplanetary (~78,000,000 km, Earth-Mars opposition)"


def _closed_form_ymax(dx, r):
    """Independent reference for the occultation half-width: the largest
    integer Y with Y^2*(dx^2-r^2) <= r^2*dx^2 (see docs/sp1-spec.md for the
    derivation of this closed form for the "ship crosses in front of a
    body at fixed x-offset Dx" geometry used below). Uses `math.isqrt`
    plus an exact correction loop, the same style as
    `horizon.geometry.min_light_time_ns` - not the code under test."""
    def down(y):
        return y * y * (dx * dx - r * r) <= r * r * dx * dx
    q = (r * r * dx * dx) // (dx * dx - r * r)
    y = math.isqrt(q)
    while down(y + 1):
        y += 1
    while not down(y):
        y -= 1
    return y


def _ceil_div(a, b):
    return -(-a // b)


def _build_flyby(dx, r, v):
    """A ship on a LinearWorldline moving along +y at fixed x-offset `dx`
    from a ground station at the origin, occulted by a body of radius `r`
    centered at (dx, 0, 0). Returns (ship, ground, body, t_hi, y_max,
    (t_enter_ref, t_exit_ref)) where the reference interval is computed by
    the closed form above, independent of `occultation_interval`'s exact
    bisection search - see module docstring on `_closed_form_ymax`.

    Colinear with ground/body on the x-axis is deliberately avoided (the
    ship travels in y, offset in x): the ground-ship segment's closest
    point to the body then always lands in the segment's INTERIOR (the
    projection branch of `is_link_down`), which is what makes a clean
    closed-form Y-threshold available for cross-checking - see
    docs/sp1-spec.md section 2.
    """
    y_max = _closed_form_ymax(dx, r)
    y0 = -3 * y_max
    t_hi = (6 * y_max) // v
    ship = LinearWorldline((dx, y0, 0), 0, (0, v, 0))
    ground = FixedWorldline((0, 0, 0))
    body = FixedWorldline((dx, 0, 0))
    t_enter_ref = _ceil_div(-y_max - y0, v)
    t_exit_ref = (y_max - y0) // v
    return ship, ground, body, t_hi, y_max, (t_enter_ref, t_exit_ref)


# Toy-scale fixture shared by SP1-A..D: chosen so the numbers are small
# enough to sanity-check by hand, not because the geometry needs it (SP1-E
# proves the same code at interplanetary scale).
TOY_DX = C_NM_PER_NS * 500
TOY_R = TOY_DX * 3 // 10
TOY_V = C_NM_PER_NS // 10  # 0.1c - sub-luminal, so the ship's own worldline
                           # is self-consistent under the kernel (F1/F4 tie-in)


class TestSP1AOccultationGeometry(unittest.TestCase):
    def setUp(self):
        (self.ship, self.ground, self.body, self.t_hi, self.y_max,
         self.ref_interval) = _build_flyby(TOY_DX, TOY_R, TOY_V)

    def test_occultation_interval_matches_closed_form_reference(self):
        got = occultation_interval(0, self.t_hi, self.ship, self.ground,
                                    self.body, TOY_R)
        self.assertEqual(got, self.ref_interval)

    def test_boundary_of_interval_is_exact(self):
        t_enter, t_exit = self.ref_interval
        self.assertFalse(is_link_down(t_enter - 1, self.ship, self.ground,
                                       self.body, TOY_R))
        self.assertTrue(is_link_down(t_enter, self.ship, self.ground,
                                      self.body, TOY_R))
        self.assertTrue(is_link_down(t_exit, self.ship, self.ground,
                                      self.body, TOY_R))
        self.assertFalse(is_link_down(t_exit + 1, self.ship, self.ground,
                                       self.body, TOY_R))

    def test_ship_worldline_is_self_consistent_sub_luminal(self):
        # v < c, so the ship's own successive positions stay inside its own
        # light cone - a superluminal fixture would silently make the
        # geometric ordering's self-chain checks in SP1-D meaningless.
        p1 = self.ship.position_at(1_000)
        p2 = self.ship.position_at(50_000)
        self.assertTrue(causally_admissible(1_000, p1, 50_000, p2))

    def test_is_link_down_pointwise_branches_hand_verified(self):
        # interior projection: line x=0..10 (y=z=0); point (5,3,0) is
        # exactly 3 nm off the line, projecting at x=5 (inside [0,10])
        a = FixedWorldline((0, 0, 0))
        b = FixedWorldline((10, 0, 0))
        on_boundary = FixedWorldline((5, 3, 0))
        self.assertTrue(is_link_down(0, a, b, on_boundary, 3))
        just_outside = FixedWorldline((5, 4, 0))
        self.assertFalse(is_link_down(0, a, b, just_outside, 3))

        # clamped to A: body sits behind A, off the segment entirely
        behind_a = FixedWorldline((-2, 1, 0))  # distance sqrt(5) =~2.236 from A
        self.assertTrue(is_link_down(0, a, b, behind_a, 3))
        self.assertFalse(is_link_down(0, a, b, behind_a, 2))

        # clamped to B: body sits beyond B
        beyond_b = FixedWorldline((13, 1, 0))  # distance sqrt(10) =~3.162 from B
        self.assertTrue(is_link_down(0, a, b, beyond_b, 4))
        self.assertFalse(is_link_down(0, a, b, beyond_b, 2))

        # degenerate: A and B coincide, segment collapses to a point
        same = FixedWorldline((0, 0, 0))
        far = FixedWorldline((1, 1, 1))  # distance sqrt(3) =~1.732
        self.assertTrue(is_link_down(0, same, same, far, 2))
        self.assertFalse(is_link_down(0, same, same, far, 1))

    def test_no_float_in_occultation_and_light_delay_modules(self):
        for rel in ("horizon/occultation.py", "horizon/light_delay.py"):
            path = os.path.join(ROOT, rel)
            with open(path) as f:
                tree = ast.parse(f.read(), filename=path)
            violations = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    violations.append((rel, "float literal", node.lineno))
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                    violations.append((rel, "true division", node.lineno))
                if isinstance(node, ast.Call):
                    name = (node.func.id if isinstance(node.func, ast.Name) else
                            node.func.attr if isinstance(node.func, ast.Attribute) else None)
                    if name in ("sqrt", "float"):
                        violations.append((rel, f"{name}() call", node.lineno))
            self.assertEqual(violations, [])


class TestSP1BBlackoutBlocksDelivery(unittest.TestCase):
    def setUp(self):
        (self.ship, self.ground, self.body, self.t_hi, self.y_max,
         self.interval) = _build_flyby(TOY_DX, TOY_R, TOY_V)
        self.t_enter, self.t_exit = self.interval

    def test_write_before_blackout_delivered_at_naive_light_time(self):
        t_emit = 1_200
        self.assertLess(t_emit, self.t_enter)
        p_emit = self.ship.position_at(t_emit)
        p_recv = self.ground.position_at(t_emit)
        expected = t_emit + min_light_time_ns(p_emit, p_recv)
        got = delivery_time_ns(t_emit, self.ship, self.ground, self.interval)
        self.assertEqual(got, expected)

    def test_write_during_blackout_delayed_until_after_exit(self):
        for t_emit in (self.t_enter + 5, (self.t_enter + self.t_exit) // 2,
                       self.t_exit - 5):
            naive = t_emit + min_light_time_ns(self.ship.position_at(t_emit),
                                                self.ground.position_at(t_emit))
            from_exit = self.t_exit + min_light_time_ns(
                self.ship.position_at(self.t_exit),
                self.ground.position_at(self.t_exit))
            expected = max(naive, from_exit)
            got = delivery_time_ns(t_emit, self.ship, self.ground, self.interval)
            self.assertEqual(got, expected, f"t_emit={t_emit}")
            # the whole point of the blackout: delivery is pushed past the
            # naive same-instant light-time estimate
            self.assertGreaterEqual(got, self.t_exit)

    def test_no_occultation_argument_is_plain_light_time(self):
        t_emit = 4_700
        expected = t_emit + min_light_time_ns(self.ship.position_at(t_emit),
                                               self.ground.position_at(t_emit))
        got = delivery_time_ns(t_emit, self.ship, self.ground, occultation=None)
        self.assertEqual(got, expected)


# The SP1-C/D event schedule: both ship and ground keep writing across the
# blackout (per docs/sp1-spec.md section 0's #548 framing). Times chosen so
# some fall before, during, and after the toy fixture's occultation
# interval (3145, 6289); verified against the fixture's actual interval in
# setUp rather than assumed.
_SCHEDULE = [
    ("ground", 200), ("ship", 1_200),
    ("ship", 3_400), ("ground", 4_000), ("ship", 4_700), ("ground", 4_750),
    ("ship", 6_000), ("ground", 7_000), ("ship", 8_500),
]


def _process_schedule(ship, ground, interval):
    processed = []
    for who, t in _SCHEDULE:
        if who == "ship":
            pos = ship.position_at(t)
            arrival = delivery_time_ns(t, ship, ground, interval)
        else:
            pos = ground.position_at(t)
            arrival = t  # ground writes to its own store: no transit delay
        processed.append({"who": who, "t": t, "pos": pos, "arrival": arrival})
    return processed


class TestSP1CReconnectBurstReordersEmergent(unittest.TestCase):
    def setUp(self):
        (self.ship, self.ground, self.body, self.t_hi, self.y_max,
         self.interval) = _build_flyby(TOY_DX, TOY_R, TOY_V)
        self.t_enter, self.t_exit = self.interval
        # sanity: schedule actually straddles the blackout as intended
        during = [t for who, t in _SCHEDULE if self.t_enter <= t <= self.t_exit]
        before = [t for who, t in _SCHEDULE if t < self.t_enter]
        after = [t for who, t in _SCHEDULE if t > self.t_exit]
        self.assertTrue(during and before and after)
        self.processed = _process_schedule(self.ship, self.ground, self.interval)

    def test_reorder_is_nonzero_and_emergent(self):
        by_emit = sorted(self.processed, key=lambda e: e["t"])
        inversions = 0
        total = 0
        for i in range(len(by_emit)):
            for j in range(i + 1, len(by_emit)):
                total += 1
                if by_emit[i]["arrival"] > by_emit[j]["arrival"]:
                    inversions += 1
        self.assertGreater(total, 0)
        # emergent, not injected: this ratio falls straight out of feeding
        # the SAME occultation interval + delivery_time_ns computed in
        # SP1-A/B through the schedule above - nothing here hand-picks an
        # arrival order. (Smaller than #548's 84.5-98.9% Earth measurement
        # because this toy fixture has far fewer concurrent writers and a
        # much shorter relative blackout - the qualitative effect, not the
        # magnitude, is what SP-1 claims; see docs/sp1-spec.md.)
        self.assertGreater(inversions, 0)
        self.assertGreaterEqual(inversions * 100, total * 5)  # >= 5%, as measured

    def test_a_specific_causally_earlier_write_arrives_later(self):
        # concrete, falsifiable instance of the emergent reorder: ship@3400
        # is emitted (t=3400) strictly before ground@4000 (t=4000), but
        # ship@3400 is inside the blackout so its delivery is deferred past
        # t_exit - it arrives AFTER ground@4000, which needed no light
        # delay at all (ground writing to its own store).
        by_key = {(e["who"], e["t"]): e for e in self.processed}
        ship_3400 = by_key[("ship", 3_400)]
        ground_4000 = by_key[("ground", 4_000)]
        self.assertLess(ship_3400["t"], ground_4000["t"])
        self.assertGreater(ship_3400["arrival"], ground_4000["arrival"])


class TestSP1DSubstrateHoldsAcrossOccultation(unittest.TestCase):
    """Feeds the SP1-C schedule's events into the causal substrate
    (mnemesis.memory.CausalMemory + GeometricOrdering, unmodified) and
    shows: a valid cross-node supersession across the gap is ADMITTED; a
    genuinely concurrent blackout pair is REJECTED in both directions and
    retained as CONFLICT (never force-picked); and a valid but ASYMMETRIC
    post-reconnect supersession is recognized in the correct direction
    only. This is the #548 guarantee (false-supersession = 0), in space."""

    def setUp(self):
        (self.ship, self.ground, self.body, self.t_hi, self.y_max,
         self.interval) = _build_flyby(TOY_DX, TOY_R, TOY_V)
        self.processed = _process_schedule(self.ship, self.ground, self.interval)
        self.by_key = {(e["who"], e["t"]): e for e in self.processed}
        self.mem = CausalMemory(GeometricOrdering())

    def _clock(self, who, t):
        e = self.by_key[(who, t)]
        return {"time_ns": e["t"], "pos_nm": list(e["pos"])}

    def test_valid_cross_node_supersession_across_the_gap_is_admitted(self):
        # ground@200 really is in ship@3400's causal past (confirmed
        # directly against the kernel, not assumed)
        self.assertTrue(causally_admissible(
            *self._clock("ground", 200).values(), *self._clock("ship", 3_400).values()))
        r1 = self.mem.put("k_valid", "ground_v", "ground", self._clock("ground", 200))
        r2 = self.mem.put("k_valid", "ship_v", "ship", self._clock("ship", 3_400),
                          supersedes=[r1["wid"]])
        self.assertEqual(r2["verdict"], "ADMITTED")
        g = self.mem.get("k_valid")
        self.assertEqual(g["status"], "RESOLVED")
        self.assertEqual(g["value"], "ship_v")

    def test_concurrent_blackout_pair_rejected_both_directions_and_retained(self):
        # ship@4700 and ground@4750 are both inside the blackout and
        # genuinely spacelike-separated - neither could have influenced
        # the other, confirmed directly against the kernel both ways
        c_ship = self._clock("ship", 4_700)
        c_ground = self._clock("ground", 4_750)
        self.assertFalse(causally_admissible(
            c_ship["time_ns"], c_ship["pos_nm"], c_ground["time_ns"], c_ground["pos_nm"]))
        self.assertFalse(causally_admissible(
            c_ground["time_ns"], c_ground["pos_nm"], c_ship["time_ns"], c_ship["pos_nm"]))

        r1 = self.mem.put("k_concurrent", "ship_v", "ship", c_ship)
        self.assertEqual(r1["verdict"], "ADMITTED")
        # a naive "just-arrived, so I win" claim must be REJECTED - never a
        # false supersession, no matter that ground@4750 arrives with no
        # transit delay at all (it's a local write) while ship@4700's
        # write is still in flight
        bad_claim = self.mem.put("k_concurrent", "ground_v", "ground", c_ground,
                                 supersedes=[r1["wid"]])
        self.assertEqual(bad_claim["verdict"], "REJECTED")
        self.assertEqual(bad_claim["reason"], "supersedes_non_ancestor")
        # retry without the bogus claim: both then coexist as candidates
        r2 = self.mem.put("k_concurrent", "ground_v", "ground", c_ground)
        self.assertEqual(r2["verdict"], "ADMITTED")
        g = self.mem.get("k_concurrent")
        self.assertEqual(g["status"], "CONFLICT")
        self.assertEqual({c["value"] for c in g["candidates"]}, {"ship_v", "ground_v"})

        # and the reverse supersession claim is rejected too - concurrency
        # is symmetric; neither side may clobber the other
        reverse_bad = self.mem.put("k_concurrent_rev", "ship_v", "ship", c_ship)
        reverse_claim = self.mem.put("k_concurrent_rev", "ground_v", "ground", c_ground,
                                     supersedes=[reverse_bad["wid"]])
        self.assertEqual(reverse_claim["verdict"], "REJECTED")

    def test_asymmetric_post_reconnect_supersession_respects_direction(self):
        # ground@4750 (during blackout, local write) genuinely IS in
        # ship@6000's causal past (physically possible given the elapsed
        # time and distance - this is the kernel's flat-spacetime NECESSARY
        # condition, independent of whether the occulted comms channel
        # itself was up; see docs/sp1-spec.md's honest nuance note) - but
        # NOT the other way around.
        c_ground = self._clock("ground", 4_750)
        c_ship = self._clock("ship", 6_000)
        self.assertTrue(causally_admissible(
            c_ground["time_ns"], c_ground["pos_nm"], c_ship["time_ns"], c_ship["pos_nm"]))
        self.assertFalse(causally_admissible(
            c_ship["time_ns"], c_ship["pos_nm"], c_ground["time_ns"], c_ground["pos_nm"]))

        r1 = self.mem.put("k_asym", "ground_v", "ground", c_ground)
        r2 = self.mem.put("k_asym", "ship_v", "ship", c_ship, supersedes=[r1["wid"]])
        self.assertEqual(r2["verdict"], "ADMITTED")

        r3 = self.mem.put("k_asym_rev", "ship_v", "ship", c_ship)
        r4 = self.mem.put("k_asym_rev", "ground_v", "ground", c_ground,
                          supersedes=[r3["wid"]])
        self.assertEqual(r4["verdict"], "REJECTED")
        self.assertEqual(r4["reason"], "supersedes_non_ancestor")


class TestSP1EAdmissibilityAcrossGapUsesWorldlinePositions(unittest.TestCase):
    """Interplanetary tie-in (ties to SP0-D / #10): the occultation geometry
    itself is exact at interplanetary scale (no float can resolve this
    lattice), and a post-occultation reconnect signal is checked against
    the ship's WORLDLINE-EVALUATED position, not a frozen snapshot."""

    def test_occultation_geometry_is_exact_at_interplanetary_scale(self):
        dx = 78_000_000 * KM_TO_NM   # Earth-Mars opposition distance
        r = 3_390 * KM_TO_NM         # ~Mars radius
        v = C_NM_PER_NS // 10
        ship, ground, body, t_hi, y_max, ref_interval = _build_flyby(dx, r, v)
        got = occultation_interval(0, t_hi, ship, ground, body, r)
        self.assertEqual(got, ref_interval)
        t_enter, t_exit = ref_interval
        self.assertFalse(is_link_down(t_enter - 1, ship, ground, body, r))
        self.assertTrue(is_link_down(t_enter, ship, ground, body, r))
        self.assertTrue(is_link_down(t_exit, ship, ground, body, r))
        self.assertFalse(is_link_down(t_exit + 1, ship, ground, body, r))

    def test_first_post_occultation_signal_checked_against_evaluated_position(self):
        # the exact interplanetary on-cone boundary vector from the merged
        # #10 benchmark, reused here as "the first signal after the ship
        # re-emerges from behind the body": a LinearWorldline built so it
        # evaluates EXACTLY to the boundary point at t2 (same construction
        # as SP0-D/test_sp0_worldline.py, extended to the occultation
        # reconnect framing).
        bv_on = next(b for b in boundary_pairs(INTERPLANETARY) if b["offset_nm"] == 0)
        bv_past = next(b for b in boundary_pairs(INTERPLANETARY) if b["offset_nm"] == 1)
        ground = FixedWorldline(bv_on["p1"])
        for bv in (bv_on, bv_past):
            dx, dy, dz = bv["p2"]
            ship = LinearWorldline(
                (0, 0, 0), bv["t1"],
                ((dx, bv["t2"]), (dy, bv["t2"]), (dz, bv["t2"])))
            self.assertEqual(ship.position_at(bv["t2"]), bv["p2"])
            got = causally_admissible_wl(ground, bv["t1"], ship, bv["t2"])
            self.assertEqual(got, bv["exact_admissible"], f"offset={bv['offset_nm']}")


if __name__ == "__main__":
    unittest.main()
