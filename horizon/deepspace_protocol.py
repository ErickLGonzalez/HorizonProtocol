"""End-to-end deep-space authenticated-telemetry + attestation protocol. [SOUND core]

Composes: (0) receipt authentication (station identity, MAC, event binding,
surveyed position - reusing H1's exact `horizon.stations` machinery, not a
new authentication mechanism), (1) the unified latency-budget gate (timing
security, exact integers), (2) the BE(Q) tracker (collusion-resistance
parameter, exact fractions), and (3) a quantum channel meeting
quantum_interface (stand-in for plumbing tests).

The verifier's security decision is the CONJUNCTION:
  receipt authenticated  AND  timing gate ADMITTED  AND  BE(Q) meets target
  AND  quantum score passes
-> verdict CONDITIONAL(BE(Q)); any failure -> REJECTED / APPARATUS_LIMITED.
The verifier does NOT import qubit_sim or the simulator; it receives a channel
object and a score, keeping the trusted path clean.

(Erratum: an earlier version of this module accepted a bare
`{t0, p_src, t_recv, p_dst}` packet with NO authentication at all - `t_recv`
and `p_dst` were whatever the caller asserted, not a value attested by a
registered station. An attacker could pick `t0 = t_recv - required_ns` for
any claimed `p_src`, wait out the claimed light-travel time, and be
CONDITIONAL_BE_Q'd - authentication in name only. Fixed: `t_recv`/`p_dst`
now come from a receipt SIGNED by a `horizon.stations.Station` in a TRUSTED
`registry` (exactly H1's cone-certificate model - registry is caller-supplied
trusted state, never read from the packet), verified through the same
known_station -> receipt_mac -> payload_binding -> surveyed_position gate
sequence `horizon.certificate.verify_certificate` uses, before any timing
decision runs.)
"""
from .beq import beq_verdict
from .latency_gate import telemetry_consistent


def _reject(gate, **extra):
    return {"aggregate_verdict": "REJECTED",
           "timing": {"verdict": "REJECTED", "witness": {"gate": gate, **extra}},
           "beq": None, "quantum_score": None,
           "meaning": "not certified"}


def verify_telemetry_packet(packet, registry, link, beq_params, quantum_score):
    """packet: {event: {payload_hash, claimed_emit_time_ns,
    claimed_emit_pos_nm}, receipt: {body: {station_id, station_pos_nm,
    payload_hash, recv_time_ns}, mac}} - an H1-style event + signed receipt,
    NOT a bare timing claim (see module erratum). `registry` is TRUSTED
    caller input (station positions/keys), never read from `packet`.
    link: {u_ns, resolve_ns}; beq_params: {k, gap_num, gap_den, target_num,
    target_den}; quantum_score: (correct, total) from a channel run (opaque
    to security).
    """
    event = packet["event"]
    receipt = packet["receipt"]
    body = receipt["body"]
    sid = body["station_id"]

    station = registry.get(sid)
    if station is None:
        return _reject("known_station", station_id=sid)
    if not station.verify_receipt(receipt):
        return _reject("receipt_mac", station_id=sid,
                       detail="HMAC verification failed")
    if body["payload_hash"] != event["payload_hash"]:
        return _reject("payload_binding", station_id=sid)
    if tuple(body["station_pos_nm"]) != station.pos_nm:
        return _reject("surveyed_position", station_id=sid)

    timing = telemetry_consistent(
        event["claimed_emit_time_ns"], tuple(event["claimed_emit_pos_nm"]),
        body["recv_time_ns"], station.pos_nm,
        link["u_ns"], link.get("resolve_ns", 0))

    beq = beq_verdict(beq_params["k"], beq_params["gap_num"],
                      beq_params["gap_den"],
                      beq_params.get("target_num", 1),
                      beq_params.get("target_den", 10**9))

    correct, total = quantum_score
    # honest threshold: require > 0.9 correct (idealized; real value set by A4)
    quantum_ok = total > 0 and (correct * 10 > total * 9)

    if timing["verdict"] == "REJECTED":
        agg = "REJECTED"
    elif not quantum_ok:
        agg = "REJECTED"
    elif not beq["meets_target"]:
        agg = "INSUFFICIENT_ROUNDS"
    elif timing["verdict"] == "APPARATUS_LIMITED":
        agg = "APPARATUS_LIMITED"
    else:
        agg = "CONDITIONAL_BE_Q"

    return {
        "aggregate_verdict": agg,
        "timing": timing,
        "beq": beq,
        "quantum_score": {"correct": correct, "total": total, "ok": quantum_ok},
        "meaning": ("authenticated + attested under bounded entanglement"
                    if agg == "CONDITIONAL_BE_Q" else "not certified"),
    }
