"""Deterministic synthetic-consistent fixtures over the real-geography node
registry (`data/h6_nodes.json`). [HEURISTIC - located warning]

Structurally identical to `horizon.fixtures` (H5), generalized to an
arbitrary real-geography registry (H6) instead of H5's frozen 3-node
abstract set: every node's receipt lands at or above the conservative
`c_eff` transit-time floor from `horizon.measure`, so every node is
comfortably ADMITTED under the SAME dual-floor gate H5 already uses and
Codex-reviewed - no new gate math, no new bound-inversion risk.

Located warning: `build_synthetic_consistent_capture` and
`build_marginal_capture` synthesize deterministic pseudo-measurements,
NOT real captured data; every fixture they produce is labelled
`"fixture_origin": "SYNTHETIC_CONSISTENT"` and must never be presented as
evidence of an actual measurement (see docs/h6-spec.md).

This module is the world model only. The trusted verifier
(`horizon.measure.verify_measured_certificate`) never imports it.
"""
import hashlib

from .events import make_event
from .geo_registry import load_geo_registry
from .measure import min_transit_time_ns_eff

SEED_H6 = "H6-FROZEN-SEED-v1"
T0_H6_NS = 1_000_000_000          # 1 s, arbitrary frozen epoch
EMIT_NODE = "us-east-1"           # claimed emission originates at the frame origin


def _seeded_offset_ns(seed: str, node_id: str, modulus: int) -> int:
    """Small deterministic non-negative offset in [0, modulus)."""
    if modulus <= 0:
        return 0
    h = hashlib.sha256(f"{seed}||offset||{node_id}".encode()).digest()
    return int.from_bytes(h, "big") % modulus


def _event(emit_pos_nm):
    return make_event({"kind": "h6_measurement_event"}, T0_H6_NS, emit_pos_nm)


def build_synthetic_consistent_capture(seed: str = SEED_H6):
    """Honest measured cone certificate over real geography: every node's
    receipt lands at the exact c_eff minimal transit time plus a small
    seeded offset - comfortably ADMITTED at every node.

    Returns (cert, registry, node_u_ns). `registry`/`node_u_ns` are TRUSTED
    caller state, never embedded in `cert` - see
    `horizon.measure`'s module docstring, section 6b.
    """
    frame, registry, node_llh, node_u_ns, spec = load_geo_registry()
    emit_pos_nm = registry[EMIT_NODE].pos_nm
    event = _event(emit_pos_nm)
    receipts = []
    for nid in sorted(registry):
        st = registry[nid]
        u_ns = node_u_ns[nid]
        typical_floor = min_transit_time_ns_eff(emit_pos_nm, st.pos_nm)
        offset = _seeded_offset_ns(seed, nid, max(u_ns // 4, 1))
        recv_time_ns = T0_H6_NS + typical_floor + offset
        receipts.append(st.sign_receipt(event["payload_hash"], recv_time_ns))
    cert = {
        "type": "measured_cone_certificate", "version": "1",
        "event": event, "receipts": receipts,
        "fixture_origin": "SYNTHETIC_CONSISTENT", "seed": seed,
        "geo_frame": frame.metadata(),
    }
    return cert, registry, node_u_ns


def build_marginal_capture(seed: str = SEED_H6, marginal_node: str = "us-west-2"):
    """Like `build_synthetic_consistent_capture`, but `marginal_node`'s
    receipt is placed at the midpoint between the vacuum-c floor and the
    conservative in-medium (`c_eff`) floor - physically possible, but
    faster than typical real-medium performance would explain - engineered
    so the verifier must report APPARATUS_LIMITED rather than PASS.
    """
    from .geometry import min_light_time_ns

    cert, registry, node_u_ns = build_synthetic_consistent_capture(seed)
    emit_pos_nm = registry[EMIT_NODE].pos_nm
    st = registry[marginal_node]
    u_ns = node_u_ns[marginal_node]
    vacuum_floor = min_light_time_ns(emit_pos_nm, st.pos_nm)
    typical_floor = min_transit_time_ns_eff(emit_pos_nm, st.pos_nm)
    dt_adjusted_target = (vacuum_floor + typical_floor) // 2
    recv_time_ns = T0_H6_NS + dt_adjusted_target - u_ns
    for i, r in enumerate(cert["receipts"]):
        if r["body"]["station_id"] == marginal_node:
            cert["receipts"][i] = st.sign_receipt(cert["event"]["payload_hash"],
                                                  recv_time_ns)
            break
    return cert, registry, node_u_ns
