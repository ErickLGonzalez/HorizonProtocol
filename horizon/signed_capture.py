"""Signed capture: authenticated measured receipts.  [SOUND verifier / HEURISTIC clock]

A node measures the arrival time of an event hash and signs
(event_hash, node_id, node_pos_nm, recv_time_ns, tier[, measured_u_ns]) with
its per-node key (HMAC-SHA256 stdlib stand-in; Ed25519 is the deployment
target). When `measured_u_ns` is present it is covered by the MAC, so a
forger cannot inflate the clock budget without the node key. Without the
node key a co-located adversary cannot forge a receipt - this is what makes
the spoof control (H8-C) meaningful. The key is derived deterministically
from `node_id` (DEMO ONLY, exactly `horizon.stations.demo_registry`'s
pattern) - a real deployment issues independent, unpredictable per-node keys.

The LIVE measurement path (measure_now) reads real system time and is
non-deterministic; it is never imported by the verifier. Committed captures
are replayed deterministically by the gates.
"""
import hashlib
import hmac
import time

from .events import canonical


def _key(node_id: str) -> bytes:
    # DEMO key derivation. Deployment: per-node Ed25519 private keys.
    return hashlib.sha256(b"HORIZON-H8-NODE-KEY::" + node_id.encode()).digest()


def sign_receipt(node_id, node_pos_nm, event_hash, recv_time_ns, tier,
                 measured_u_ns=None):
    body = {
        "node_id": node_id,
        "node_pos_nm": [int(x) for x in node_pos_nm],
        "event_hash": event_hash,
        "recv_time_ns": int(recv_time_ns),
        "tier": tier,
    }
    if measured_u_ns is not None:
        body["measured_u_ns"] = int(measured_u_ns)
    mac = hmac.new(_key(node_id), canonical(body), hashlib.sha256).hexdigest()
    return {"body": body, "mac": mac}


def verify_receipt(receipt) -> bool:
    body = receipt["body"]
    mac = hmac.new(_key(body["node_id"]), canonical(body),
                   hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, receipt["mac"])


def measure_now(node_id, node_pos_nm, event_hash, tier, measured_u_ns=None):
    """LIVE, non-deterministic: stamp the current system time. [HEURISTIC]
    Not imported by the verifier; used only by the live capture script.
    When `measured_u_ns` is supplied it is MAC-bound into the receipt body."""
    return sign_receipt(node_id, node_pos_nm, event_hash,
                        time.time_ns(), tier, measured_u_ns=measured_u_ns)
