"""H7-D: end-to-end protocol + trusted-path hygiene. [SOUND core]"""
import unittest
from horizon.deepspace_protocol import verify_telemetry_packet
from horizon.deepspace import one_way_light_time_ns, EARTH_MARS_TYP_M, M_TO_NM
from horizon.quantum_interface import SimulatedChannel, REGISTERED_ASSUMPTIONS
from horizon.qubit_sim import score, honest_response, mismatched_response


class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.d_nm = EARTH_MARS_TYP_M * M_TO_NM
        self.owlt = one_way_light_time_ns(EARTH_MARS_TYP_M)
        self.packet_ok = {"t0": 0, "p_src": [self.d_nm, 0, 0],
                          "t_recv": self.owlt + 1000, "p_dst": [0, 0, 0]}
        self.link = {"u_ns": 0, "resolve_ns": 0}
        self.beq = {"k": 73, "gap_num": 3, "gap_den": 4}

    def test_full_pass_conditional_beq(self):
        r = verify_telemetry_packet(self.packet_ok, self.link, self.beq,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "CONDITIONAL_BE_Q")

    def test_forged_timing_rejected_even_with_good_qubits(self):
        forged = dict(self.packet_ok)
        forged["t_recv"] = self.owlt - 10**9  # impossibly early
        r = verify_telemetry_packet(forged, self.link, self.beq,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "REJECTED")

    def test_bad_qubits_rejected_even_with_good_timing(self):
        r = verify_telemetry_packet(self.packet_ok, self.link, self.beq,
                                    score(200, mismatched_response))
        self.assertEqual(r["aggregate_verdict"], "REJECTED")

    def test_insufficient_rounds_flagged(self):
        weak = {"k": 10, "gap_num": 3, "gap_den": 4}
        r = verify_telemetry_packet(self.packet_ok, self.link, weak,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "INSUFFICIENT_ROUNDS")

    def test_verifier_does_not_import_simulator(self):
        import horizon.deepspace_protocol as dp, inspect, re
        src = inspect.getsource(dp)
        imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", src, re.M)
        for imp in imports:
            self.assertNotIn("qubit_sim", imp)
            self.assertNotIn("_sim", imp)

    def test_registered_assumptions_present(self):
        for key in ("A1", "A2", "A3", "A4"):
            self.assertIn(key, REGISTERED_ASSUMPTIONS)


if __name__ == "__main__":
    unittest.main()
