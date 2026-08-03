"""Timing stations: surveyed positions, deterministic clocks, HMAC receipts.

[HEURISTIC - located warning]: HMAC-SHA256 with symmetric per-station keys
stands in for real signatures (Ed25519 etc. is outside the stdlib). Key
distribution is trusted in this reference implementation; the adversary
model is a SINGLE FORGER without station keys, not a colluding multi-site
adversary. See docs/h1-spec.md, section "Adversary model".
"""
import hmac
import hashlib
from .events import canonical


class Station:
    def __init__(self, station_id: str, pos_nm, key: bytes, proc_delay_ns: int = 0):
        self.station_id = station_id
        self.pos_nm = tuple(int(x) for x in pos_nm)
        self._key = key
        self.proc_delay_ns = int(proc_delay_ns)

    def receipt_body(self, payload_hash: str, recv_time_ns: int) -> dict:
        return {
            "station_id": self.station_id,
            "station_pos_nm": list(self.pos_nm),
            "payload_hash": payload_hash,
            "recv_time_ns": int(recv_time_ns),
        }

    def sign_receipt(self, payload_hash: str, recv_time_ns: int) -> dict:
        body = self.receipt_body(payload_hash, recv_time_ns)
        mac = hmac.new(self._key, canonical(body), hashlib.sha256).hexdigest()
        return {"body": body, "mac": mac}

    def verify_receipt(self, receipt: dict) -> bool:
        mac = hmac.new(self._key, canonical(receipt["body"]), hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, receipt["mac"])


def demo_registry(specs):
    """Deterministic station registry. Keys derived from IDs - DEMO ONLY."""
    reg = {}
    for sid, pos, delay in specs:
        key = hashlib.sha256(b"HORIZON-DEMO-KEY::" + sid.encode()).digest()
        reg[sid] = Station(sid, pos, key, delay)
    return reg
