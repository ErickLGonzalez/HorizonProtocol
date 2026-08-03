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
        # round trip to Mars-distance claimed position
        min_rtt = min_round_trip_ns(self.p_earth, self.p_mars)
        rtt = min_rtt + 2000
        r = trajectory_attested(0, self.p_earth, rtt, self.p_mars,
                                proc_ns=0, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "ADMITTED")

    def test_attestation_rejects_too_fast_response(self):
        min_rtt = min_round_trip_ns(self.p_earth, self.p_mars)
        rtt = min_rtt - 1_000_000_000  # impossibly quick for the distance
        r = trajectory_attested(0, self.p_earth, rtt, self.p_mars,
                                proc_ns=0, u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "REJECTED")

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
