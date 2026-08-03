"""H1-E: negative controls - forgeries deterministically REJECTED with
exact witnesses. [SOUND, E0]"""
import unittest
from horizon.stations import demo_registry
from horizon.events import make_event
from horizon.simulate import broadcast
from horizon.certificate import build_cone_certificate, verify_certificate
from horizon.geometry import min_light_time_ns

SPECS = [
    ("STN-A", (0, 0, 0), 3),
    ("STN-B", (10_000_000_000, 0, 0), 4),
    ("STN-C", (0, 10_000_000_000, 0), 5),
]


class TestNegativeControls(unittest.TestCase):
    def setUp(self):
        self.reg = demo_registry(SPECS)
        self.event = make_event({"doc": "x"}, 1_000_000, (0, 0, 0))
        self.receipts = broadcast(self.event, self.reg)

    def test_ftl_receipt_rejected_with_light_cone_witness(self):
        # Adversary controls STN-B's key but claims an arrival 1 ns before
        # light from the claimed emission could reach STN-B.
        st = self.reg["STN-B"]
        d_min = min_light_time_ns((0, 0, 0), st.pos_nm)
        forged = st.sign_receipt(self.event["payload_hash"],
                                 self.event["claimed_emit_time_ns"] + d_min - 1)
        cert = build_cone_certificate(self.event, [self.receipts[0], forged])
        res = verify_certificate(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "light_cone")
        w = res["witness"]["exact_witness"]
        self.assertLess(w["lhs_c_dt_squared"], w["rhs_dist_squared_nm2"])

    def test_forged_mac_rejected(self):
        bad = dict(self.receipts[0])
        bad = {"body": dict(bad["body"]), "mac": bad["mac"]}
        bad["body"]["recv_time_ns"] -= 50  # tamper after signing
        cert = build_cone_certificate(self.event, [bad])
        res = verify_certificate(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "receipt_mac")

    def test_unknown_station_rejected(self):
        from horizon.stations import demo_registry as dr
        rogue = dr([("STN-Z", (5, 5, 5), 1)])["STN-Z"]
        r = rogue.sign_receipt(self.event["payload_hash"], 2_000_000)
        cert = build_cone_certificate(self.event, [r])
        res = verify_certificate(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "known_station")

    def test_wrong_event_binding_rejected(self):
        other = make_event({"doc": "y"}, 1_000_000, (0, 0, 0))
        r = self.reg["STN-A"].sign_receipt(other["payload_hash"], 2_000_000)
        cert = build_cone_certificate(self.event, [r])
        res = verify_certificate(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "payload_binding")

    def test_lying_about_station_position_rejected(self):
        st = self.reg["STN-B"]
        body = st.receipt_body(self.event["payload_hash"], 2_000_000)
        body["station_pos_nm"] = [0, 0, 0]  # claim to be at the origin
        import hmac, hashlib
        from horizon.events import canonical
        mac = hmac.new(st._key, canonical(body), hashlib.sha256).hexdigest()
        cert = build_cone_certificate(self.event, [{"body": body, "mac": mac}])
        res = verify_certificate(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "surveyed_position")


if __name__ == "__main__":
    unittest.main()
