"""H7-D: end-to-end protocol + trusted-path hygiene. [SOUND core]"""
import unittest
from horizon.deepspace_protocol import verify_telemetry_packet
from horizon.deepspace import one_way_light_time_ns, EARTH_MARS_TYP_M, M_TO_NM
from horizon.events import make_event
from horizon.quantum_interface import SimulatedChannel, REGISTERED_ASSUMPTIONS
from horizon.qubit_sim import score, honest_response, mismatched_response
from horizon.stations import demo_registry


class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.d_nm = EARTH_MARS_TYP_M * M_TO_NM
        self.owlt = one_way_light_time_ns(EARTH_MARS_TYP_M)
        self.p_mars = (self.d_nm, 0, 0)
        self.p_earth = (0, 0, 0)
        self.registry = demo_registry([("EARTH-DSN-1", self.p_earth, 0)])
        self.event = make_event({"telemetry": "h7-demo"}, 0, self.p_mars)
        self.link = {"u_ns": 0, "resolve_ns": 0}
        self.beq = {"k": 73, "gap_num": 3, "gap_den": 4}

    def _packet(self, recv_time_ns, station_id="EARTH-DSN-1"):
        st = self.registry[station_id]
        receipt = st.sign_receipt(self.event["payload_hash"], recv_time_ns)
        return {"event": self.event, "receipt": receipt}

    def test_full_pass_conditional_beq(self):
        pkt = self._packet(self.owlt + 1000)
        r = verify_telemetry_packet(pkt, self.registry, self.link, self.beq,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "CONDITIONAL_BE_Q")

    def test_forged_timing_rejected_even_with_good_qubits(self):
        pkt = self._packet(self.owlt - 10**9)  # impossibly early
        r = verify_telemetry_packet(pkt, self.registry, self.link, self.beq,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "REJECTED")

    def test_bad_qubits_rejected_even_with_good_timing(self):
        pkt = self._packet(self.owlt + 1000)
        r = verify_telemetry_packet(pkt, self.registry, self.link, self.beq,
                                    score(200, mismatched_response))
        self.assertEqual(r["aggregate_verdict"], "REJECTED")

    def test_insufficient_rounds_flagged(self):
        weak = {"k": 10, "gap_num": 3, "gap_den": 4}
        pkt = self._packet(self.owlt + 1000)
        r = verify_telemetry_packet(pkt, self.registry, self.link, weak,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "INSUFFICIENT_ROUNDS")

    def test_unauthenticated_receipt_rejected(self):
        # a receipt not signed by a registered station's key must not pass,
        # even if the claimed timing would otherwise be consistent (the
        # erratum this test guards against: authentication in name only)
        pkt = self._packet(self.owlt + 1000)
        pkt["receipt"]["mac"] = "0" * 64
        r = verify_telemetry_packet(pkt, self.registry, self.link, self.beq,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "REJECTED")
        self.assertEqual(r["timing"]["witness"]["gate"], "receipt_mac")

    def test_unknown_station_rejected(self):
        pkt = self._packet(self.owlt + 1000)
        pkt["receipt"]["body"]["station_id"] = "GHOST-STATION"
        r = verify_telemetry_packet(pkt, self.registry, self.link, self.beq,
                                    score(200, honest_response))
        self.assertEqual(r["aggregate_verdict"], "REJECTED")
        self.assertEqual(r["timing"]["witness"]["gate"], "known_station")

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
