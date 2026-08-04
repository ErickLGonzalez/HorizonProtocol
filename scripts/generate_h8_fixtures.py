#!/usr/bin/env python3
"""Generate committed replay captures modeling REAL measured behavior.

Marked origin=MEASURED_MODEL: arrival = emission + in-medium light time at
c_eff (fiber ~0.6c, matching `horizon.measure`'s frozen conservative bound)
+ a route-excess factor + a deterministic per-node clock error within the
tier's U_ns. This models what a genuine NTP-tier capture looks like
(arrivals LATER than vacuum, clock error comparable to continental light
time). A true live capture (scripts/live_capture.py) replaces this with real
system-time measurements; this committed model keeps CI deterministic.

Also emits a TIGHTER-TIER variant (PTP U_ns) to demonstrate the
APPARATUS_LIMITED -> ADMITTED transition (gate H8-D), and a SPOOF variant
(H8-C): a process claiming to emit from a distant node while co-located with
the verifier, signed with a ROGUE key it does not legitimately hold.

Run manually whenever `data/h8_nodes.json` changes; the output is committed
to `data/` and thereafter only ever REPLAYED, never regenerated at test or
CI time - see docs/h8-spec.md.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.build_frame import TIERS, load_registry  # noqa: E402
from horizon.geometry import C_NM_PER_NS, dist2  # noqa: E402
from horizon.measure import C_EFF_DEN, C_EFF_NUM  # noqa: E402
from horizon.signed_capture import sign_receipt  # noqa: E402

C_EFF = (C_EFF_NUM, C_EFF_DEN)   # fiber ~0.6c - matches horizon.measure's frozen bound
ROUTE_EXCESS = (13, 10)          # routes ~1.3x straight-line (num/den)
SEED = "H8-CAPTURE-MODEL-v1"


def min_medium_time_ns(p0, p1, num, den):
    import math
    d2 = dist2(p0, p1)
    if d2 == 0:
        return 0
    r = math.isqrt(den * den * d2)
    if r * r < den * den * d2:
        r += 1
    dt = -(-r // (C_NM_PER_NS * num))
    while (C_NM_PER_NS * num * dt) ** 2 < den * den * d2:
        dt += 1
    return dt


def det_error(node_id, u_ns):
    # deterministic clock error in [-u_ns/2, +u_ns/2]
    h = int(hashlib.sha256((SEED + node_id).encode()).hexdigest(), 16)
    return (h % (u_ns + 1)) - u_ns // 2


def build_capture(reg, tier_override=None, origin="MEASURED_MODEL"):
    emit = "us-east-1"
    p0 = tuple(reg[emit]["pos_nm"])
    t0 = 1_000_000_000
    payload = {"doc": "h8-real-capture", "n": 1}
    ehash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    ren, red = ROUTE_EXCESS
    receipts = []
    for nid, node in reg.items():
        u = TIERS[tier_override] if tier_override else node["u_ns"]
        # route-excess path length -> effective distance longer
        base = min_medium_time_ns(p0, tuple(node["pos_nm"]), *C_EFF)
        routed = base * ren // red
        # clock error perturbs the MEASURED arrival; floor total propagation at 0
        prop = max(0, routed + det_error(nid, u))
        recv = t0 + prop
        tier = tier_override or node["tier"]
        receipts.append(sign_receipt(nid, node["pos_nm"], ehash, recv, tier))
    return {"origin": origin, "seed": SEED, "event_hash": ehash,
            "t0_ns": t0, "p0_nm": list(p0), "c_eff": list(C_EFF),
            "route_excess": list(ROUTE_EXCESS), "receipts": receipts}


def main():
    _, reg, _ = load_registry()
    outdir = os.path.join(ROOT, "data")

    # NTP-tier capture (clock error dominates at continental scale)
    cap = build_capture(reg)
    with open(os.path.join(outdir, "h8_capture_ntp.json"), "w") as f:
        json.dump(cap, f, indent=2, sort_keys=True)
    print("wrote data/h8_capture_ntp.json")

    # PTP-tier capture (same geometry, tighter clock -> should resolve)
    cap_ptp = build_capture(reg, tier_override="PTP")
    with open(os.path.join(outdir, "h8_capture_ptp.json"), "w") as f:
        json.dump(cap_ptp, f, indent=2, sort_keys=True)
    print("wrote data/h8_capture_ptp.json")

    # SPOOF: co-located adversary claims a distant node's identity+position
    # but signs with a rogue key (not the real node key).
    spoof = build_capture(reg)
    spoof["origin"] = "SPOOF"
    import hashlib as _h
    import hmac
    from horizon.events import canonical
    rogue_key = _h.sha256(b"ROGUE").digest()
    body = {"node_id": "us-west-2", "node_pos_nm": reg["us-west-2"]["pos_nm"],
            "event_hash": spoof["event_hash"],
            "recv_time_ns": spoof["t0_ns"] + 500_000,  # arrives ~instantly
            "tier": "NTP"}
    spoof_receipt = {"body": body,
                     "mac": hmac.new(rogue_key, canonical(body), _h.sha256).hexdigest()}
    spoof["receipts"] = [r for r in spoof["receipts"]
                         if r["body"]["node_id"] != "us-west-2"] + [spoof_receipt]
    with open(os.path.join(outdir, "h8_capture_spoof.json"), "w") as f:
        json.dump(spoof, f, indent=2, sort_keys=True)
    print("wrote data/h8_capture_spoof.json")


if __name__ == "__main__":
    main()
