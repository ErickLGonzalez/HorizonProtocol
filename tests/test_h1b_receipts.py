"""H1-B: station receipts round-trip; forged MAC rejected. [SOUND, E0]"""
import unittest
from horizon.stations import demo_registry
from horizon.events import make_event

SPECS = [("STN-A", (0, 0, 0), 5), ("STN-B", (10_000_000_000, 0, 0), 5)]


class TestReceipts(unittest.TestCase):
    def setUp(self):
        self.reg = demo_registry(SPECS)
        self.event = make_event({"msg": "hello"}, 1_000, (0, 0, 0))

    def test_roundtrip(self):
        st = self.reg["STN-A"]
        r = st.sign_receipt(self.event["payload_hash"], 1_100)
        self.assertTrue(st.verify_receipt(r))

    def test_tampered_time_rejected(self):
        st = self.reg["STN-A"]
        r = st.sign_receipt(self.event["payload_hash"], 1_100)
        r["body"]["recv_time_ns"] = 900  # forge an earlier arrival
        self.assertFalse(st.verify_receipt(r))

    def test_wrong_station_key_rejected(self):
        a, b = self.reg["STN-A"], self.reg["STN-B"]
        r = a.sign_receipt(self.event["payload_hash"], 1_100)
        self.assertFalse(b.verify_receipt(r))


if __name__ == "__main__":
    unittest.main()
