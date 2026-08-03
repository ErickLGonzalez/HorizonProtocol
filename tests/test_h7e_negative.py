"""H7-E: negative controls and quarantine. [SOUND]"""
import unittest
from horizon.latency_gate import telemetry_consistent
from horizon.deepspace import one_way_light_time_ns, EARTH_MARS_MIN_M, M_TO_NM


class TestNegative(unittest.TestCase):
    def test_earth_spoofing_mars_packet_rejected(self):
        # adversary on Earth forges a "from Mars" packet; claims Mars emission
        # but the packet reaches the Earth verifier far too soon.
        d_nm = EARTH_MARS_MIN_M * M_TO_NM
        owlt = one_way_light_time_ns(EARTH_MARS_MIN_M)
        r = telemetry_consistent(0, (d_nm, 0, 0), owlt // 2, (0, 0, 0),
                                 u_ns=0, resolve_ns=0)
        self.assertEqual(r["verdict"], "REJECTED")
        self.assertLess(r["witness"]["margin_ns"], 0)

    def test_arrival_before_emission_rejected(self):
        r = telemetry_consistent(1000, (0, 0, 0), 500, (0, 0, 0), 0, 0)
        self.assertEqual(r["verdict"], "REJECTED")
        self.assertEqual(r["witness"]["reason"], "arrival_before_emission")

    def test_qubit_sim_is_quarantined_from_interface_security(self):
        # SimulatedChannel is explicitly labeled a stand-in, not a device
        import horizon.quantum_interface as qi, inspect
        src = inspect.getsource(qi.SimulatedChannel)
        self.assertIn("stand-in", src.lower())


if __name__ == "__main__":
    unittest.main()
