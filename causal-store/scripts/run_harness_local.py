#!/usr/bin/env python3
"""Run the benchmark harness's deterministic LOCAL gates, then a
LOCAL/LOOPBACK end-to-end sweep of causal-store vs. the total-order
baseline; emit certificates/harness_certificate.json.

benchmark_id is deliberately "D1-HARNESS", never "D1": D1 (design doc
section 8) is the LIVE cross-region measurement itself, which this
script cannot perform - it runs entirely in one process with 0ns
loopback "network" cost (topology_probe.local_topology()). This
certifies the harness's own correctness (ground-truth order-checking,
percentile math, adapter contract, dependency-respecting scheduling),
NOT the design doc's actual comparison claim. See
docs/benchmark-harness-spec.md for what a genuine D1 live run requires
and the runbook for the live agent.

CockroachDB/YugabyteDB/Tiga adapters are exercised for availability only
(expected: AdapterUnavailable in this environment) and recorded honestly
- never silently skipped, never faked. Exit 0 iff every LOCAL gate is
green; missing competitors do not fail this local gate.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benchmark_harness import driver, report, verify_order  # noqa: E402
from benchmark_harness.adapters.base import AdapterUnavailable  # noqa: E402
from benchmark_harness.adapters.baseline_adapter import TotalOrderBaselineAdapter  # noqa: E402
from benchmark_harness.adapters.causalstore_adapter import CausalStoreAdapter  # noqa: E402
from benchmark_harness.adapters.cockroach_adapter import CockroachAdapter  # noqa: E402
from benchmark_harness.adapters.tiga_adapter import TigaAdapter  # noqa: E402
from benchmark_harness.adapters.yugabyte_adapter import YugabyteAdapter  # noqa: E402
from benchmark_harness.topology_probe import local_topology  # noqa: E402
from benchmark_harness.workload_gen import DEFAULT_CONTENTION_SWEEP, generate_trace  # noqa: E402
from causalstore.geometry import C_NM_PER_NS  # noqa: E402

GATES = [
    ("H-A", "tests.test_h0a_workload_gen", "SOUND",
     "workload generator: deterministic, physically-grounded dependency graph"),
    ("H-B", "tests.test_h0b_verify_order", "SOUND",
     "correctness gate catches an injected causality violation"),
    ("H-C", "tests.test_h0c_driver", "SOUND",
     "driver respects depends_on ordering under concurrency, closed and open loop"),
    ("H-D", "tests.test_h0d_collect_report", "SOUND",
     "percentile/throughput math; report assembly flags VOID points"),
    ("H-E", "tests.test_h0e_adapters", "SOUND",
     "adapter contract: causalstore/baseline conform; unavailable competitors report loudly"),
    ("H-F", "tests.test_h0f_topology_probe_quarantine", "SOUND",
     "LIVE network probe functions never referenced outside topology_probe.py"),
]

# Regions reused from H8-LIVE's Azure mapping (design doc section 2: "reuse
# the H8-LIVE Azure region mapping where possible"); positions are relative
# nm along one axis, matching bench/geo_workload.py's convention - light-ms
# scale separations, not the real WGS84 geometry (that lives in
# data/h8_nodes.json for the live run; see docs/benchmark-harness-spec.md).
REGIONS_NM = {
    "us-east-1": 0,
    "us-east-2": C_NM_PER_NS * 5_000_000,
    "us-west-2": C_NM_PER_NS * 12_000_000,
    "eu-west-1": C_NM_PER_NS * 28_000_000,
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _local_sweep():
    regions = list(REGIONS_NM)
    positions = {r: (nm, 0, 0) for r, nm in REGIONS_NM.items()}
    region_clocks = {r: {"pos_nm": positions[r], "u_ns": 1000} for r in regions}

    points = []
    for contention_ratio in DEFAULT_CONTENTION_SWEEP:
        gen = generate_trace(regions, positions, n_keys=80, n_ops=300,
                             contention_ratio=contention_ratio,
                             seed=f"D1-HARNESS-local-{contention_ratio}")
        trace = gen["trace"]
        for name, adapter in (("causal-store", CausalStoreAdapter(region_clocks)),
                              ("total-order-baseline", TotalOrderBaselineAdapter())):
            adapter.setup(regions)
            t0 = time.perf_counter()
            results = driver.run(adapter, trace, mode="closed", concurrency=8)
            elapsed_s = time.perf_counter() - t0
            adapter.teardown()
            by_id = {r.op_id: r for r in results}
            verdict = verify_order.verify(trace, by_id)
            points.append(report.build_point(name, contention_ratio, results,
                                             elapsed_s, verdict, adapter.diagnostics()))

    competitor_availability = {}
    for cls in (CockroachAdapter, YugabyteAdapter, TigaAdapter):
        a = cls() if cls is not TigaAdapter else cls()
        try:
            a.setup(regions)
            competitor_availability[a.name] = "AVAILABLE"
            a.teardown()
        except AdapterUnavailable as exc:
            competitor_availability[a.name] = f"UNAVAILABLE: {exc}"

    rep = report.build_report(
        points,
        topology=local_topology(regions),
        honest_scope={
            "mode": "LOCAL_LOOPBACK",
            "note": ("single in-process run; 0ns loopback network cost. "
                     "This is NOT the design doc's cross-region measurement "
                     "(see docs/benchmark-harness-spec.md section 8/D1)."),
            "competitor_availability": competitor_availability,
        },
    )
    return rep


def main():
    results, all_pass = [], True
    for gid, mod, tag, desc in GATES:
        p = subprocess.run([sys.executable, "-m", "unittest", "-v", mod],
                           cwd=ROOT, capture_output=True, text=True)
        ok = p.returncode == 0
        all_pass &= ok
        results.append({"gate": gid, "description": desc, "soundness_tag": tag,
                        "result": "PASS" if ok else "FAIL"})
        print(f"{gid}: {'PASS' if ok else 'FAIL'} - {desc}")

    rep = _local_sweep()
    all_pass &= not rep["any_void_points"]
    if rep["any_void_points"]:
        print("LOCAL SWEEP: a run point was VOID (correctness violation) - see report")

    src = {}
    for pkg in ("benchmark_harness",):
        for dp, _, files in os.walk(os.path.join(ROOT, pkg)):
            if "__pycache__" in dp:
                continue
            for fn in sorted(files):
                if fn.endswith(".py"):
                    fp = os.path.join(dp, fn)
                    src[os.path.relpath(fp, ROOT)] = sha(fp)

    cert = {
        "certificate_version": "1", "benchmark_id": "D1-HARNESS",
        "program": "causal-store", "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK", "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("not applicable - this is a correctness/performance "
                            "engineering harness, not an adversarial security gate"),
        "thesis": ("harness self-check: the benchmark harness (workload generation, "
                  "dependency-respecting driver, ground-truth correctness gate, "
                  "percentile/report assembly, adapter contract) is correct, run "
                  "here against a LOCAL LOOPBACK topology with causal-store and "
                  "the total-order baseline - NOT the design doc's live "
                  "cross-region comparison (see docs/benchmark-harness-spec.md)"),
        "heuristic_warnings": [
            {"location": "benchmark_harness/topology_probe.py",
             "warning": "this run used local_topology() (0ns loopback); no real "
                        "inter-region network was measured"},
            {"location": "benchmark_harness/adapters/baseline_adapter.py",
             "warning": "coordination_rtt_ns=0 in this run; the baseline's "
                        "latency numbers here are correctness-only, not a "
                        "performance claim (see module docstring)"},
            {"location": "benchmark_harness/adapters/{cockroach,yugabyte}_adapter.py",
             "warning": "written per each system's documented client API but not "
                        "exercised against a live cluster in this build; reported "
                        "as UNAVAILABLE here, never faked (see honest_scope in the "
                        "report and module docstrings)"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "gates": results, "aggregate": "PASS" if all_pass else "FAIL",
        "local_sweep_report": rep,
        "source_hashes": src, "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "harness_certificate.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(cert, open(out, "w"), indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"competitor availability: {rep['honest_scope']['competitor_availability']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
