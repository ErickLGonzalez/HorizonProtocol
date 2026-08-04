"""H7-B: unified latency-budget gate (telemetry + attestation). [SOUND]"""
import unittest
from horizon.latency_gate import telemetry_consistent, trajectory_attested
from horizon.deepspace import one_way_light_time_ns, EARTH_MARS_TYP_M, M_TO_NM
from horizon.distance import min_round_trip_ns


class TestLatencyGate(unittest.TestCase):
    def setUp(self):
        self.d_nm = EARTH_MARS_TYP_M * M_TO_NM
        self.p_mars = (self.d_nm, 0, 0)
        self.p_earth = (0, 0, 0)
        self.owlt = one_way_light_time_ns(EARTH_MARS_TYP_M)

    def test_honest_telemetry_admitted(self):
        # packet emitted at Mars t0=0, received at Earth at owlt (+ margin)
        r = telemetry_consistent(0, self.p_mars, self.owlt + 1000, self.p_earth,
                                 u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "ADMITTED")

    def test_impossibly_fast_telemetry_rejected(self):
        # arrives 1 second before light could bring it -> forged
        r = telemetry_consistent(0, self.p_mars, self.owlt - 1_000_000_000,
                                 self.p_earth, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "REJECTED")
        self.assertLess(r["witness"]["margin_ns"], 0)

    def test_attestation_admits_correct_distance(self):
        # round trip to Mars-distance claimed position, landing exactly at
        # the requirement (zero slack needed for the exact honest case)
        min_rtt = min_round_trip_ns(self.p_earth, self.p_mars)
        r = trajectory_attested(0, self.p_earth, min_rtt, self.p_mars,
                                proc_ns=0, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "ADMITTED")

    def test_attestation_within_resolve_band_is_apparatus_limited_not_rejected(self):
        # a small amount of jitter beyond the exact requirement is neither
        # a clean ADMITTED (it overshoots the exact round-trip requirement)
        # nor a REJECTED (it's within the declared resolve_ns slack) -
        # never a silent PASS on an unresolvable margin
        min_rtt = min_round_trip_ns(self.p_earth, self.p_mars)
        r = trajectory_attested(0, self.p_earth, min_rtt + 2000, self.p_mars,
                                proc_ns=0, u_ns=0, resolve_ns=5000)
        self.assertEqual(r["verdict"], "APPARATUS_LIMITED")

    def test_attestation_admits_within_resolve_band_given_matching_u_ns(self):
        # declared clock uncertainty pulls the high side back down to the
        # exact requirement, yielding a clean ADMITTED
        min_rtt = min_round_trip_ns(self.p_earth, self.p_mars)
        r = trajectory_attested(0, self.p_earth, min_rtt + 2000, self.p_mars,
                                proc_ns=0, u_ns=2000, resolve_ns=0)
        self.assertEqual(r["verdict"], "ADMITTED")

    def test_attestation_rejects_too_fast_response(self):
        min_rtt = min_round_trip_ns(self.p_earth, self.p_mars)
        rtt = min_rtt - 1_000_000_000  # impossibly quick for the distance
        r = trajectory_attested(0, self.p_earth, rtt, self.p_mars,
                                proc_ns=0, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "REJECTED")
        self.assertEqual(r["witness"]["reason"], "too_fast_for_claimed_distance")

    def test_attestation_rejects_too_slow_response(self):
        min_rtt = min_round_trip_ns(self.p_earth, self.p_mars)
        rtt = min_rtt + 1_000_000_000  # implausibly slow for the distance
        r = trajectory_attested(0, self.p_earth, rtt, self.p_mars,
                                proc_ns=0, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "REJECTED")
        self.assertEqual(r["witness"]["reason"], "too_slow_for_claimed_distance")

    def test_two_sided_bound_catches_a_farther_prover_claiming_closer(self):
        # the direction the two-sided bound SOUNDLY closes (matching H3's
        # original deadline semantics): a prover truly at Mars cannot
        # physically respond fast enough to satisfy a nearer claim (e.g.
        # claiming to be co-located with the verifier) - its forced minimum
        # RTT for its TRUE (farther) distance already exceeds what the
        # nearer claim allows, so it is caught regardless of promptness.
        min_rtt_true_mars = min_round_trip_ns(self.p_earth, self.p_mars)
        p_claimed_near = self.p_earth  # false claim: "I am co-located with you"
        # even responding as promptly as physically possible (its own true
        # minimum), the response is far too slow for the false nearby claim
        r = trajectory_attested(0, self.p_earth, min_rtt_true_mars,
                                p_claimed_near, proc_ns=0, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "REJECTED")
        self.assertEqual(r["witness"]["reason"], "too_slow_for_claimed_distance")

    def test_registered_limitation_claiming_farther_than_true_is_not_caught(self):
        # HONEST LIMITATION (see horizon/latency_gate.py's module docstring
        # and docs/h7-spec.md section 3b): the opposite direction - a
        # prover truly CLOSE to the verifier deliberately delaying its
        # response to mimic the round-trip time of a FARTHER claimed
        # position (e.g. co-located with Earth, claiming to be on Mars) -
        # is NOT caught by any combination of timing bounds. Delaying a
        # response is always physically possible; no purely aggregate-RTT
        # check can distinguish "genuinely at the claimed distance" from
        # "closer, and waited." This is registered here as a known,
        # structural limitation of round-trip-timing distance bounding
        # (not specific to this implementation) rather than silently
        # assumed solved - matching H3-C's discipline of demonstrating a
        # known impossibility as a passing test instead of hiding it.
        min_rtt_mars = min_round_trip_ns(self.p_earth, self.p_mars)
        r = trajectory_attested(0, self.p_earth, min_rtt_mars, self.p_mars,
                                proc_ns=0, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "ADMITTED")  # EXPECTED_ATTACK_SUCCESS in effect

    def test_clock_uncertainty_apparatus_limited(self):
        # a receipt landing exactly on the boundary, with a realistic
        # microsecond-scale resolve band, must be APPARATUS_LIMITED - not
        # silently ADMITTED, and not requiring an astronomically large
        # resolve value to ever trigger (see the erratum in
        # horizon/latency_gate.py: the old squared-margin design needed a
        # resolve_ns2 comparable to the FULL margin magnitude to have any
        # effect at all, which a realistic clock-uncertainty figure never is)
        resolve_ns = 50_000  # 50 us, comparable to H5/H6's declared U_ns
        r = telemetry_consistent(0, self.p_mars, self.owlt - resolve_ns // 2,
                                 self.p_earth, u_ns=0, resolve_ns=resolve_ns)
        self.assertEqual(r["verdict"], "APPARATUS_LIMITED")

    def test_realistic_resolve_ns_does_not_mask_a_real_forgery(self):
        # the same small, realistic resolve band must NOT rescue a receipt
        # that is genuinely, grossly too early
        resolve_ns = 50_000
        r = telemetry_consistent(0, self.p_mars, self.owlt - 1_000_000_000,
                                 self.p_earth, u_ns=0, resolve_ns=resolve_ns)
        self.assertEqual(r["verdict"], "REJECTED")

    def test_clock_uncertainty_can_rescue_a_near_boundary_arrival(self):
        # u_ns is applied in the claimant's favor, exactly like H5/H6
        r = telemetry_consistent(0, self.p_mars, self.owlt - 1000,
                                 self.p_earth, u_ns=1000, resolve_ns=0)
        self.assertEqual(r["verdict"], "ADMITTED")

    def test_gate_module_imports_only_the_kernel(self):
        import ast
        import inspect
        import horizon.latency_gate as lg
        tree = ast.parse(inspect.getsource(lg))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any("sim" in n for n in imported), imported)
        self.assertFalse(any("capture" in n for n in imported), imported)
        self.assertFalse(any("quantum" in n for n in imported), imported)


if __name__ == "__main__":
    unittest.main()
