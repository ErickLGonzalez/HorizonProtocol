"""Frozen real-world-plausible node geometry and captured measurement
fixtures. [HEURISTIC - located warning]

Located warnings:
  (1) node positions are derived once from public approximate lat/long/
      altitude values via a flat-earth (equirectangular) projection - a
      float computation - then FROZEN as the integer nm constants below;
      no float ever reaches a gate decision (`horizon.measure` operates
      only on the frozen integers);
  (2) `build_synthetic_consistent_capture` and `build_marginal_capture`
      synthesize deterministic pseudo-measurements (arrival = exact
      min-transit-time at `c_eff` plus a small seeded offset), NOT real
      captured data; every fixture they produce is labelled
      `"origin": "SYNTHETIC_CONSISTENT"` and must never be presented as
      evidence of an actual measurement (see docs/h5-spec.md).

This module is the world model only. The trusted verifier
(`horizon.measure.verify_measured_certificate`) never imports it; test
H5-B asserts this by source inspection.
"""
import hashlib

from .events import make_event
from .measure import RESOLVE_MARGIN_NS, min_transit_time_ns_eff
from .stations import demo_registry

# ---- frozen node geometry (H5) ----------------------------------------------
# Derived once via a flat-earth equirectangular projection from approximate
# public lat/long/altitude values, origin at NODE-USE1:
#   NODE-USE1  lat=38.9072  lon=-77.0369  alt_m=30   (approx. N. Virginia)
#   NODE-USW2  lat=45.5946  lon=-121.1787 alt_m=50   (approx. Oregon)
#   NODE-EUW1  lat=53.3498  lon=-6.2603   alt_m=20   (approx. Ireland)
# Frozen thereafter; the conversion is never repeated at gate-evaluation time.
FRAME_ORIGIN_LLH = {"node_id": "NODE-USE1", "lat_deg": 38.9072,
                    "lon_deg": -77.0369, "alt_m": 30.0}
NODES_NM = {
    "NODE-USE1": (0, 0, 0),
    "NODE-USW2": (-3_819_497_896_113_808, 743_604_952_442_822, 20_000_000_000),
    "NODE-EUW1": (6_124_151_593_140_482, 1_605_943_847_556_704, -10_000_000_000),
}
# Declared per-node clock uncertainty: NODE-USE1 is PTP-grade, the rest NTP-grade.
NODE_U_NS = {
    "NODE-USE1": 50_000,          # 50 us (PTP)
    "NODE-USW2": 5_000_000,       # 5 ms (NTP)
    "NODE-EUW1": 5_000_000,       # 5 ms (NTP)
}
T0_H5_NS = 0                      # frozen claimed emission time
EVENT_POS_NM = NODES_NM["NODE-USE1"]  # claimed emission originates at NODE-USE1
SEED_H5 = "H5-FROZEN-SEED-v1"


def llh_to_enu_nm(lat_deg: float, lon_deg: float, alt_m: float,
                  origin_lat_deg: float, origin_lon_deg: float,
                  origin_alt_m: float) -> tuple:
    """Flat-earth equirectangular approximation, float-based. Used only to
    derive the FROZEN integer constants in `NODES_NM` above; never called
    at gate-evaluation time. Returns (east_nm, north_nm, up_nm)."""
    import math
    earth_radius_m = 6_371_000.0
    m_to_nm = 1_000_000_000
    lat0_rad = math.radians(origin_lat_deg)
    east_m = (math.radians(lon_deg - origin_lon_deg) * earth_radius_m
              * math.cos(lat0_rad))
    north_m = math.radians(lat_deg - origin_lat_deg) * earth_radius_m
    up_m = alt_m - origin_alt_m
    return (round(east_m * m_to_nm), round(north_m * m_to_nm),
            round(up_m * m_to_nm))


def build_registry():
    specs = [(nid, pos, 0) for nid, pos in sorted(NODES_NM.items())]
    return demo_registry(specs)


def _seeded_offset_ns(seed: str, node_id: str, modulus: int) -> int:
    """Small deterministic non-negative offset in [0, modulus)."""
    if modulus <= 0:
        return 0
    h = hashlib.sha256(f"{seed}||offset||{node_id}".encode()).digest()
    return int.from_bytes(h, "big") % modulus


def _event():
    return make_event({"kind": "h5_measurement_event"}, T0_H5_NS, EVENT_POS_NM)


def build_synthetic_consistent_capture(seed: str = SEED_H5) -> dict:
    """Honest measured cone certificate: every node's receipt lands at the
    exact c_eff minimal transit time plus a small seeded offset well
    within its declared uncertainty - comfortably ADMITTED at every node.
    """
    registry = build_registry()
    event = _event()
    receipts = []
    node_params = {}
    for nid in sorted(NODES_NM):
        st = registry[nid]
        u_ns = NODE_U_NS[nid]
        required = min_transit_time_ns_eff(EVENT_POS_NM, st.pos_nm)
        offset = _seeded_offset_ns(seed, nid, max(u_ns // 4, 1))
        recv_time_ns = T0_H5_NS + required + offset
        receipts.append(st.sign_receipt(event["payload_hash"], recv_time_ns))
        node_params[nid] = {"u_ns": u_ns}
    cert = {
        "type": "measured_cone_certificate", "version": "1",
        "event": event, "receipts": receipts, "node_params": node_params,
        "resolve_margin_ns": RESOLVE_MARGIN_NS,
        "fixture_origin": "SYNTHETIC_CONSISTENT", "seed": seed,
    }
    return cert, registry


def build_marginal_capture(seed: str = SEED_H5,
                           marginal_node: str = "NODE-USW2") -> dict:
    """Like `build_synthetic_consistent_capture`, but `marginal_node`'s
    receipt is placed exactly at the boundary (margin_ns == 0) between the
    ADMITTED and REJECTED regions, landing inside RESOLVE_MARGIN_NS -
    engineered so the verifier must report APPARATUS_LIMITED for this
    event rather than silently certifying PASS.
    """
    cert, registry = build_synthetic_consistent_capture(seed)
    st = registry[marginal_node]
    u_ns = NODE_U_NS[marginal_node]
    required = min_transit_time_ns_eff(EVENT_POS_NM, st.pos_nm)
    # raw_dt + u_ns - required == 0  =>  raw_dt == required - u_ns
    recv_time_ns = T0_H5_NS + required - u_ns
    for i, r in enumerate(cert["receipts"]):
        if r["body"]["station_id"] == marginal_node:
            cert["receipts"][i] = st.sign_receipt(cert["event"]["payload_hash"],
                                                  recv_time_ns)
            break
    return cert, registry
