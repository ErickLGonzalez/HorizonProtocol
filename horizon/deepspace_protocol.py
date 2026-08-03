"""End-to-end deep-space authenticated-telemetry + attestation protocol. [SOUND core]

Composes: (1) the unified latency-budget gate (timing security, exact integers),
(2) the BE(Q) tracker (collusion-resistance parameter, exact fractions), and
(3) a quantum channel meeting quantum_interface (stand-in for plumbing tests).

The verifier's security decision is the CONJUNCTION:
  timing gate ADMITTED  AND  BE(Q) meets target  AND  quantum score passes
-> verdict CONDITIONAL(BE(Q)); any failure -> REJECTED / APPARATUS_LIMITED.
The verifier does NOT import qubit_sim or the simulator; it receives a channel
object and a score, keeping the trusted path clean.
"""
from .beq import beq_verdict
from .latency_gate import telemetry_consistent


def verify_telemetry_packet(packet, link, beq_params, quantum_score):
    """packet: {t0, p_src, t_recv, p_dst}; link: {u_ns, resolve_ns};
    beq_params: {k, gap_num, gap_den, target_num, target_den};
    quantum_score: (correct, total) from a channel run (opaque to security)."""
    timing = telemetry_consistent(
        packet["t0"], tuple(packet["p_src"]),
        packet["t_recv"], tuple(packet["p_dst"]),
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
