"""H1-C: cone certificate build + independent re-verification. [SOUND, E0]"""
import unittest
from horizon.stations import demo_registry
from horizon.events import make_event
from horizon.simulate import broadcast
from horizon.certificate import build_cone_certificate, verify_certificate

# Five stations on a ~10 m rig (positions in nm), deterministic delays (ns).
SPECS = [
    ("STN-A", (0, 0, 0), 3),
    ("STN-B", (10_000_000_000, 0, 0), 4),
    ("STN-C", (0, 10_000_000_000, 0), 5),
    ("STN-D", (0, 0, 10_000_000_000), 6),
    ("STN-E", (7_000_000_000, 7_000_000_000, 0), 7),
]


class TestConeCertificate(unittest.TestCase):
    def setUp(self):
        self.reg = demo_registry(SPECS)
        self.event = make_event({"doc": "B13 signoff", "n": 1},
                                1_000_000, (2_000_000_000, 1_000_000_000, 0))

    def test_honest_certificate_passes(self):
        receipts = broadcast(self.event, self.reg)
        cert = build_cone_certificate(self.event, receipts)
        res = verify_certificate(cert, self.reg)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(len(res["checks"]), 5)
        self.assertTrue(all(c["ok"] for c in res["checks"]))
        # every receipt arrives at/after the claimed emission
        self.assertGreaterEqual(res["emit_time_upper_bound_ns"],
                                self.event["claimed_emit_time_ns"])

    def test_verifier_is_standalone(self):
        # the verifier must not import the simulator (trusted-path hygiene)
        import horizon.certificate as c
        import inspect
        src = inspect.getsource(c)
        self.assertNotIn("simulate", src)

    def test_empty_certificate_rejected(self):
        cert = build_cone_certificate(self.event, [])
        res = verify_certificate(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "nonempty_receipts")


if __name__ == "__main__":
    unittest.main()
