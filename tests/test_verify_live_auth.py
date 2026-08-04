"""H8-LIVE verify wrapper: MAC-bound measured_u_ns, no nominal fallback."""
import importlib.util
import json
import os
import tempfile
import unittest

from horizon.signed_capture import sign_receipt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFY_LIVE_PATH = os.path.join(ROOT, "scripts", "verify_live.py")


def _load_verify_live():
    spec = importlib.util.spec_from_file_location("verify_live", VERIFY_LIVE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVerifyLiveAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vl = _load_verify_live()

    def _minimal_capture(self, with_body_u=True, inflate_top=False, bad_mac=False):
        u = 50_000
        r = sign_receipt("us-east-1", [0, 0, 0], "eh", 1_000_000, "PTP",
                         measured_u_ns=u if with_body_u else None)
        if not with_body_u and "measured_u_ns" in r["body"]:
            del r["body"]["measured_u_ns"]
            # re-sign without u
            r = sign_receipt("us-east-1", [0, 0, 0], "eh", 1_000_000, "PTP")
        if bad_mac:
            r["body"]["measured_u_ns"] = 10**12  # break MAC
        top_u = 10**12 if inflate_top else u
        return {
            "origin": "LIVE_CAPTURE",
            "tier_nominal": "PTP",
            "measured_u_ns": {"us-east-1": top_u},
            "receipts": [r],
        }

    def test_authenticated_measured_u_from_body(self):
        cap = self._minimal_capture(with_body_u=True)
        measured, meta = self.vl.authenticated_measured_u(cap, {"us-east-1"})
        self.assertEqual(measured["us-east-1"], 50_000)
        self.assertEqual(meta["used_authenticated"]["us-east-1"], 50_000)
        self.assertFalse(meta["missing"])
        self.assertFalse(meta["bad_mac"])

    def test_missing_body_u_is_reported(self):
        cap = self._minimal_capture(with_body_u=False)
        measured, meta = self.vl.authenticated_measured_u(cap, {"us-east-1"})
        self.assertNotIn("us-east-1", measured)
        self.assertIn("us-east-1", meta["missing"])

    def test_top_level_mismatch_detected(self):
        cap = self._minimal_capture(with_body_u=True, inflate_top=True)
        measured, meta = self.vl.authenticated_measured_u(cap, {"us-east-1"})
        self.assertIn("us-east-1", measured)
        self.assertIn("us-east-1", meta["top_level_mismatch"])

    def test_tampered_body_u_breaks_mac(self):
        cap = self._minimal_capture(with_body_u=True, bad_mac=True)
        measured, meta = self.vl.authenticated_measured_u(cap, {"us-east-1"})
        self.assertNotIn("us-east-1", measured)
        self.assertIn("us-east-1", meta["bad_mac"])

    def test_main_refuses_missing_measured_u(self):
        cap = self._minimal_capture(with_body_u=False)
        # Need a plausible LIVE_CAPTURE shape for load_registry path; write
        # a temp file and invoke main — it must exit non-zero before cert.
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cap.json")
            # Use a real multi-node capture stripped of body u to exercise
            # the refusal path end-to-end.
            real = os.path.join(ROOT, "data", "h8_live_capture_PTP_1.json")
            with open(real) as f:
                live = json.load(f)
            for r in live["receipts"]:
                r["body"].pop("measured_u_ns", None)
                # Re-sign without u so MAC is valid but u absent.
                b = r["body"]
                from horizon.signed_capture import sign_receipt as sr
                new_r = sr(b["node_id"], b["node_pos_nm"], b["event_hash"],
                           b["recv_time_ns"], b["tier"])
                r.clear()
                r.update(new_r)
            with open(path, "w") as f:
                json.dump(live, f)
            rc = self.vl.main([path, "--out", os.path.join(td, "out.json")])
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(os.path.join(td, "out.json")))


if __name__ == "__main__":
    unittest.main()
