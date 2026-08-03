"""H5-D: negative controls - vacuum-c violation, tamper, bad position,
forged gate parameters, failing live-capture self-check. [SOUND]"""
import copy
import hashlib
import hmac
import json
import os
import unittest

from horizon.events import canonical
from horizon.fixtures import build_registry, trusted_node_params
from horizon.measure import verify_measured_certificate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(ROOT, "data", "h5_fixture_capture.json")


class TestNegativeControls(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH) as f:
            self.cert = json.load(f)
        self.registry = build_registry()
        self.node_params = trusted_node_params()

    def _resign(self, cert, station_id, recv_time_ns):
        """Rebuild a receipt with a VALID signature over a new recv_time -
        used to simulate a legitimately measured but impossibly-early
        receipt, as distinct from a post-hoc tamper (test 2 below)."""
        st = self.registry[station_id]
        payload_hash = cert["event"]["payload_hash"]
        return st.sign_receipt(payload_hash, recv_time_ns)

    def test_impossibly_early_rejected_below_vacuum_floor(self):
        cert = copy.deepcopy(self.cert)
        sid = "NODE-USW2"
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                cert["receipts"][i] = self._resign(cert, sid, 0)  # claims instant arrival
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "budget")
        self.assertEqual(res["witness"]["station_id"], sid)
        w = res["witness"]["exact_witness"]
        self.assertLess(w["dt_adjusted_ns"], w["vacuum_floor_ns"])

    def test_tampered_recv_time_rejected_at_mac(self):
        cert = copy.deepcopy(self.cert)
        cert["receipts"][0]["body"]["recv_time_ns"] += 1  # tamper post-signature
        res = verify_measured_certificate(cert, self.registry, self.node_params)
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
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "surveyed_position")

    def test_forged_cert_embedded_parameters_are_ignored(self):
        # an attacker cannot smuggle a huge uncertainty or superluminal
        # c_eff through the certificate itself: node_params comes only from
        # the verifier's TRUSTED caller-supplied argument. Build a receipt
        # that is impossibly early under the true declared u_ns, then
        # attach a forged (but irrelevant) node_params block to the cert
        # claiming an enormous uncertainty - the forgery must have no effect.
        cert = copy.deepcopy(self.cert)
        sid = "NODE-USW2"
        for i, r in enumerate(cert["receipts"]):
            if r["body"]["station_id"] == sid:
                cert["receipts"][i] = self._resign(cert, sid, 0)
        cert["node_params"] = {sid: {"u_ns": 10 ** 15, "c_eff_num": 1, "c_eff_den": 1}}
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "budget")
        # the witness reflects the TRUSTED u_ns, not the forged one
        self.assertEqual(res["witness"]["exact_witness"]["u_ns"],
                         self.node_params[sid]["u_ns"])

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
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertEqual(res["witness"]["gate"], "live_capture_self_check")
        self.assertEqual(res["witness"]["station_id"], sid)
        self.assertNotEqual(res["verdict"], "PASS")

    def test_unknown_station_rejected(self):
        cert = copy.deepcopy(self.cert)
        cert["receipts"][0]["body"]["station_id"] = "NODE-GHOST"
        node_params = dict(self.node_params)
        node_params["NODE-GHOST"] = {"u_ns": 50_000}
        res = verify_measured_certificate(cert, self.registry, node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "known_station")

    def test_duplicate_source_rejected(self):
        # a single valid signed receipt repeated must not pad the apparent
        # node count while still returning PASS (mirrors H4's beacon
        # distinct_sources gate)
        cert = copy.deepcopy(self.cert)
        cert["receipts"][1] = copy.deepcopy(cert["receipts"][0])
        res = verify_measured_certificate(cert, self.registry, self.node_params)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "distinct_sources")


if __name__ == "__main__":
    unittest.main()
