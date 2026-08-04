"""Assembles per-run results into the latency-vs-contention /
throughput-vs-load curves the design doc calls for.  [reporting only -
not a gate; the correctness gate is verify_order.py, run per point
BEFORE a point's timing is included here]

(Erratum: an earlier version computed `latency_ns` percentiles from EVERY
op_result's `latency_ns`, including rejected ops - every adapter populates
`latency_ns` on a rejection too (it's still a real measured duration, just
not a commit). A system that fails fast on a subset of the trace would
report an artificially LOW commit-latency curve, even though
`throughput_ops_per_s` correctly counts only accepted ops - a fast reject
is not a fast commit, and design doc section 4 defines this metric at
"the client-observed commit acknowledgment," which a rejection never
reaches. Fixed: `latency_ns` percentiles are now computed from accepted
ops only.)
"""
from .collect import acceptance_rate, latency_percentiles, throughput_per_sec


def build_point(system, contention_ratio, op_results, elapsed_s, order_verdict,
                diagnostics=None):
    """One (system, contention_ratio) result point. `order_verdict` must
    be the output of verify_order.verify() for this run - a point whose
    order_verdict is not ok is still recorded, but flagged VOID per H4,
    so a fast-but-wrong result can never silently read as a win."""
    committed_latencies = [r.latency_ns for r in op_results if r.accepted]
    return {
        "system": system,
        "contention_ratio": contention_ratio,
        "n_ops": len(op_results),
        "acceptance_rate": round(acceptance_rate(op_results), 4),
        "throughput_ops_per_s": round(throughput_per_sec(op_results, elapsed_s), 2),
        "latency_ns": latency_percentiles(committed_latencies),
        "correctness": {
            "ok": order_verdict["ok"],
            "checked_edges": order_verdict["checked_edges"],
            "violation_count": len(order_verdict["violations"]),
        },
        "status": "OK" if order_verdict["ok"] else "VOID_CORRECTNESS_VIOLATION",
        "diagnostics": diagnostics or {},
    }


def build_report(points, topology=None, honest_scope=None):
    """`points`: list of build_point() dicts. Groups into curves by
    system, sorted by contention_ratio, for direct plotting."""
    by_system = {}
    for p in points:
        by_system.setdefault(p["system"], []).append(p)
    for pts in by_system.values():
        pts.sort(key=lambda p: p["contention_ratio"])

    any_void = any(p["status"] != "OK" for p in points)
    return {
        "report_version": "1",
        "curves": by_system,
        "any_void_points": any_void,
        "topology": topology or {},
        "honest_scope": honest_scope or {},
    }
