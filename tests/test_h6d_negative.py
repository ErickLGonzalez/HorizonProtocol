"""H6-D: negative controls - vacuum-c violation, tamper, bad position,
forged gate parameters, unknown node. [SOUND]"""
import copy
import hashlib
import hmac
import json
import os
import unittest

from horizon.events import canonical
from horizon.geo_registry import load_geo_registry, trusted_node_params
from horizon.measure import verify_measured_certificate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(ROOT, "data", "h6_fixture_capture.json")


class TestNegativeControls(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH) as f:
            self.cert = json.load(f)
        _, self.registry, _, node_u_ns, _ = load_geo_registry()
        self.node_params = trusted_node_params(node_u_ns)

    def _resign(self, cert, station_id, recv_time_ns):
        st = self.registry[station_id]
        payload_hash = cert["event"]["payload_hash"]
        return st.sign_receipt(payload_hash, recv_time_ns)

    def test_impossibly_early_from_farthest_node_rejected(self):
        # Singapore is ~12,000 km from the Virginia origin (~40 ms vacuum
        # floor); an arrival 1 us after emission is impossible in any medium
        cert = copy.deepcopy(self.cert)
        sid = "ap-southeast-1"
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                cert["receipts"][i] = self._resign(cert, sid, cert["event"]["claimed_emit_time_ns"] + 1000)
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "budget")
        self.assertEqual(res["witness"]["station_id"], sid)
        w = res["witness"]["exact_witness"]
        self.assertLess(w["dt_adjusted_ns"], w["vacuum_floor_ns"])

    def test_tampered_recv_time_rejected_at_mac(self):
        cert = copy.deepcopy(self.cert)
        cert["receipts"][0]["body"]["recv_time_ns"] += 1
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "receipt_mac")

    def test_position_lie_rejected_surveyed_position(self):
        # a node lying about its own position: still validly MAC'd, since
        # the false claim originates from the node itself
        cert = copy.deepcopy(self.cert)
        sid = "us-west-2"
        st = self.registry[sid]
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                body = dict(r["body"])
                body["station_pos_nm"] = [0, 0, 0]
                mac = hmac.new(st._key, canonical(body), hashlib.sha256).hexdigest()
                cert["receipts"][i] = {"body": body, "mac": mac}
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "surveyed_position")

    def test_forged_cert_embedded_parameters_are_ignored(self):
        cert = copy.deepcopy(self.cert)
        sid = "ap-southeast-1"
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                cert["receipts"][i] = self._resign(cert, sid, cert["event"]["claimed_emit_time_ns"] + 1000)
        cert["node_params"] = {sid: {"u_ns": 10 ** 15, "c_eff_num": 1, "c_eff_den": 1}}
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "budget")
        self.assertEqual(res["witness"]["exact_witness"]["u_ns"],
                         self.node_params[sid]["u_ns"])

    def test_unknown_node_rejected(self):
        cert = copy.deepcopy(self.cert)
        cert["receipts"][0]["body"]["station_id"] = "mars-1"
        node_params = dict(self.node_params)
        node_params["mars-1"] = {"u_ns": 50_000}
        res = verify_measured_certificate(cert, self.registry, node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "known_station")


if __name__ == "__main__":
    unittest.main()
