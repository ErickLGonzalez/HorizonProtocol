"""H5-D: negative controls - FTL-in-medium, tamper, bad position,
failing live-capture self-check. [SOUND]"""
import copy
import hashlib
import hmac
import json
import os
import unittest

from horizon.events import canonical
from horizon.fixtures import build_registry
from horizon.measure import verify_measured_certificate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(ROOT, "data", "h5_fixture_capture.json")


class TestNegativeControls(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH) as f:
            self.cert = json.load(f)
        self.registry = build_registry()

    def _resign(self, cert, station_id, recv_time_ns):
        """Rebuild a receipt with a VALID signature over a new recv_time -
        used to simulate a legitimately measured but impossibly-early
        receipt, as distinct from a post-hoc tamper (test 2 below)."""
        st = self.registry[station_id]
        payload_hash = cert["event"]["payload_hash"]
        return st.sign_receipt(payload_hash, recv_time_ns)

    def test_impossibly_early_rejected_ftl_in_medium(self):
        cert = copy.deepcopy(self.cert)
        sid = "NODE-USW2"
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                cert["receipts"][i] = self._resign(cert, sid, 0)  # claims instant arrival
        res = verify_measured_certificate(cert, self.registry)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "budget")
        self.assertEqual(res["witness"]["station_id"], sid)
        self.assertFalse(res["witness"]["exact_witness"]["consistent"])
        self.assertLess(res["witness"]["exact_witness"]["margin_ns"], 0)

    def test_tampered_recv_time_rejected_at_mac(self):
        cert = copy.deepcopy(self.cert)
        cert["receipts"][0]["body"]["recv_time_ns"] += 1  # tamper post-signature
        res = verify_measured_certificate(cert, self.registry)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "receipt_mac")

    def test_inconsistent_position_rejected_surveyed_position(self):
        # a station lying about its own position: body forged with a fake
        # position but still validly MAC'd (a mismatch the MAC alone can't
        # catch, since it's the *station itself* asserting the false claim)
        cert = copy.deepcopy(self.cert)
        sid = "NODE-USW2"
        st = self.registry[sid]
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                body = dict(r["body"])
                body["station_pos_nm"] = [0, 0, 0]  # claim to be at the origin
                mac = hmac.new(st._key, canonical(body), hashlib.sha256).hexdigest()
                cert["receipts"][i] = {"body": body, "mac": mac}
        res = verify_measured_certificate(cert, self.registry)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "surveyed_position")

    def test_live_capture_failing_self_check_apparatus_limited(self):
        cert = copy.deepcopy(self.cert)
        cert["fixture_origin"] = "LIVE_CAPTURE"
        # NODE-USE1 is zero-distance with a small declared U_ns, so a
        # receipt timestamped 1 ns before the claimed emission still clears
        # the ordinary budget gate (ADMITTED) - only the live-capture
        # self-check, which runs after all per-node budget gates, catches
        # the negative raw elapsed time
        sid = "NODE-USE1"
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                cert["receipts"][i] = self._resign(cert, sid, -1)
        res = verify_measured_certificate(cert, self.registry)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertEqual(res["witness"]["gate"], "live_capture_self_check")
        self.assertEqual(res["witness"]["station_id"], sid)
        self.assertNotEqual(res["verdict"], "PASS")

    def test_unknown_station_rejected(self):
        cert = copy.deepcopy(self.cert)
        cert["receipts"][0]["body"]["station_id"] = "NODE-GHOST"
        cert["node_params"]["NODE-GHOST"] = {"u_ns": 50_000}
        res = verify_measured_certificate(cert, self.registry)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "known_station")


if __name__ == "__main__":
    unittest.main()
