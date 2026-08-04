#!/usr/bin/env python3
"""Performance benchmark: gate cost and ledger scaling. [D2, no security gate]

Answers "demonstrator or deployable infrastructure?" - not a PASS/FAIL
security certificate (nothing here is a gate), so this writes a perf
REPORT (bench_report.json) rather than a certificate, and always exits 0.

Measures, with stdlib `time.perf_counter_ns` only:
  1. `causally_admissible` / `min_light_time_ns` at terrestrial and
     interplanetary magnitudes (bignum growth at Earth-Mars distance).
  2. `verify_certificate` latency vs. station count.
  3. `CausalLedger.add_edge` and `.precedes` (reachability) latency vs.
     edge count, with a fitted scaling exponent (log-log slope) to
     characterize whether reachability is roughly linear in the number of
     edges or worse.
"""
import json
import math
import os
import platform
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.certificate import build_cone_certificate, verify_certificate  # noqa: E402
from horizon.events import make_event  # noqa: E402
from horizon.geometry import C_NM_PER_NS, causally_admissible, min_light_time_ns  # noqa: E402
from horizon.ledger import CausalLedger  # noqa: E402
from horizon.simulate import broadcast  # noqa: E402
from horizon.stations import demo_registry  # noqa: E402

M_TO_NM = 1_000_000_000
KM_TO_NM = 1_000 * M_TO_NM

# Distance magnitudes: terrestrial (antipodal-ish), Earth-Moon, Earth-Mars
# (average opposition distance) - chosen to exercise bignum growth in
# (c*dt)**2, which scales with distance squared.
MAGNITUDES_KM = {
    "terrestrial (~12,000 km, antipodal)": 12_000,
    "earth_moon (~384,000 km)": 384_000,
    "earth_mars_opposition (~78,000,000 km)": 78_000_000,
    "earth_mars_max (~401,000,000 km)": 401_000_000,
}


def timeit_ns(fn, iterations):
    start = time.perf_counter_ns()
    for _ in range(iterations):
        fn()
    end = time.perf_counter_ns()
    return (end - start) / iterations


def bench_gate_at_magnitudes():
    results = {}
    for label, dist_km in MAGNITUDES_KM.items():
        dist_nm = dist_km * KM_TO_NM
        p0, p1 = (0, 0, 0), (dist_nm, 0, 0)
        dt = min_light_time_ns(p0, p1)

        def call_admissible():
            causally_admissible(0, p0, dt + 1, p1)

        def call_min_light_time():
            min_light_time_ns(p0, p1)

        results[label] = {
            "distance_km": dist_km,
            "min_light_time_ns": dt,
            "causally_admissible_ns_per_call": timeit_ns(call_admissible, 20_000),
            "min_light_time_ns_ns_per_call": timeit_ns(call_min_light_time, 20_000),
        }
    return results


def bench_certificate_verification():
    results = {}
    for n_stations in (1, 5, 10, 50, 100):
        specs = [(f"STN-{i}", (i * KM_TO_NM, 0, 0), 0) for i in range(n_stations)]
        registry = demo_registry(specs)
        event = make_event({"bench": True}, 0, (0, 0, 0))
        receipts = broadcast(event, registry)
        cert = build_cone_certificate(event, receipts)

        def call_verify():
            verify_certificate(cert, registry)

        results[str(n_stations)] = timeit_ns(call_verify, max(200, 2000 // n_stations))
    return results


def _fitted_scaling_exponent(timings_ns):
    # precedes_ns ~ edges^k, k from a log-log least-squares fit over the
    # measured points (k~1 -> linear, k~2 -> quadratic)
    xs = [math.log(n) for n, _ in timings_ns]
    ys = [math.log(max(t, 1.0)) for _, t in timings_ns]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    return num / den if den else float("nan")


def bench_ledger_scaling():
    """Chain of N events (A0 -> A1 -> ... -> AN), each strictly inside the
    previous one's future cone, then time `precedes(A0, AN)` (the reference,
    worst case for a DFS that rescans the full edge set per visited node)
    against `precedes_fast(A0, AN)` (the additive adjacency-indexed BFS,
    horizon.reachability_cache) - the D2 finding and its filed fix."""
    results = {}
    edge_counts = (10, 50, 100, 500, 1000)
    slow_timings, fast_timings = [], []
    for n_edges in edge_counts:
        ledger = CausalLedger()
        for i in range(n_edges + 1):
            ledger.add_event(f"E{i}", i * 1_000_000, (0, 0, 0))
        add_edge_start = time.perf_counter_ns()
        for i in range(n_edges):
            ledger.add_edge(f"E{i}", f"E{i + 1}")
        add_edge_ns = (time.perf_counter_ns() - add_edge_start) / n_edges

        def call_precedes():
            ledger.precedes("E0", f"E{n_edges}")

        precedes_ns = timeit_ns(call_precedes, max(5, 2000 // n_edges))

        ledger.precedes_fast("E0", f"E{n_edges}")  # warm the adjacency cache once

        def call_precedes_fast():
            ledger.precedes_fast("E0", f"E{n_edges}")

        precedes_fast_ns = timeit_ns(call_precedes_fast, max(5, 2000 // n_edges))

        results[str(n_edges)] = {"add_edge_ns_per_call": add_edge_ns,
                                 "precedes_ns_per_call": precedes_ns,
                                 "precedes_fast_ns_per_call": precedes_fast_ns}
        slow_timings.append((n_edges, precedes_ns))
        fast_timings.append((n_edges, precedes_fast_ns))

    slope = _fitted_scaling_exponent(slow_timings)
    fast_slope = _fitted_scaling_exponent(fast_timings)
    return results, slope, fast_slope


def main():
    report = {
        "type": "performance_report",
        "note": ("informational only - not a security gate, not a "
                 "certificate; always exits 0"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "gate_at_magnitudes": bench_gate_at_magnitudes(),
        "certificate_verification_ns_per_call_by_station_count": bench_certificate_verification(),
    }
    ledger_results, ledger_slope, ledger_fast_slope = bench_ledger_scaling()
    report["ledger_reachability_by_edge_count"] = ledger_results
    report["ledger_precedes_fitted_scaling_exponent"] = ledger_slope
    report["ledger_precedes_fast_fitted_scaling_exponent"] = ledger_fast_slope
    report["ledger_scaling_finding"] = (
        "CausalLedger.precedes scans the FULL edge set for every visited "
        f"node (not an adjacency-list restricted scan): fitted exponent "
        f"{ledger_slope:.2f} on this run. An exponent near 1.0 would be "
        "linear in edge count (adjacency-list BFS); an exponent near 2.0 "
        "is consistent with the O(edges) full-set scan per visited node "
        "this implementation performs. Filed and fixed additively: "
        "horizon.reachability_cache adds precedes_fast(), an adjacency-"
        "indexed BFS cross-checked for agreement against precedes() in "
        f"tests/test_reachability_cache.py - fitted exponent "
        f"{ledger_fast_slope:.2f} on this run for the same measurements. "
        "precedes() is kept, unchanged, as the reference; add_edge's "
        "causally_admissible check is unaffected either way - this is a "
        "reachability-query optimization, not a change to what counts as "
        "an admitted edge.")

    out = os.path.join(ROOT, "bench_report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    print("=== Gate cost at magnitude ===")
    for label, r in report["gate_at_magnitudes"].items():
        print(f"  {label}: causally_admissible={r['causally_admissible_ns_per_call']:.0f} ns, "
             f"min_light_time_ns={r['min_light_time_ns_ns_per_call']:.0f} ns")
    print("\n=== Certificate verification vs. station count ===")
    for n, ns in report["certificate_verification_ns_per_call_by_station_count"].items():
        print(f"  {n} stations: {ns:.0f} ns")
    print("\n=== Ledger reachability vs. edge count ===")
    for n, r in ledger_results.items():
        print(f"  {n} edges: add_edge={r['add_edge_ns_per_call']:.0f} ns, "
             f"precedes={r['precedes_ns_per_call']:.0f} ns, "
             f"precedes_fast={r['precedes_fast_ns_per_call']:.0f} ns")
    print(f"\nfitted precedes() scaling exponent:      {ledger_slope:.2f} "
         "(1.0=linear, 2.0=quadratic)")
    print(f"fitted precedes_fast() scaling exponent: {ledger_fast_slope:.2f}")
    print(f"\nreport written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
