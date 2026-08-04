"""Real inter-region RTT/jitter measurement, plus a deterministic local
stand-in for testing.  [LIVE half is HEURISTIC and QUARANTINED - never
imported by tests/, run_harness_local.py, or any gate]

The design doc (section 2) requires every run to measure and record real
inter-region RTT before comparing systems, so a reader can see the
wide-area cost is real, not simulated - the same "measure, don't assume"
discipline `horizon/capture.py` and `scripts/live_orchestrate.py` already
apply to clock offsets. `probe_rtt`/`probe_topology` are that measurement
for network latency: stdlib TCP connect timing, read-only, never writing
anything but the returned dict.

Quarantine, enforced the same way as `horizon/capture.py`:
  - never imported by anything under `tests/`, `causal-store/tests/`, or
    `causal-store/scripts/run_d0.py` - test_topology_probe_quarantine
    asserts this by source inspection;
  - performs no side-effectful network writes, only TCP connect probes;
  - `local_topology()` below is the ONLY thing the deterministic harness
    tests and `run_harness_local.py` may call.

For an actual cross-region run, the live agent uses `probe_topology()`
directly (see docs/benchmark-harness-spec.md's runbook) with each
region's real reachable host:port.
"""
import socket
import statistics
import time


def probe_rtt(host, port, rounds=5, timeout_s=3.0):
    """Best-effort TCP-connect RTT to (host, port), `rounds` times.
    Never raises to the caller - returns a verdict dict, UNREACHABLE on
    any socket error, matching horizon/capture.py's convention."""
    samples_ns = []
    for _ in range(max(1, rounds)):
        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout_s):
                pass
        except OSError as exc:
            return {"host": host, "port": port, "verdict": "UNREACHABLE",
                    "detail": str(exc)}
        samples_ns.append(int((time.perf_counter() - t0) * 1e9))
    return {
        "host": host, "port": port, "verdict": "OK",
        "rounds": len(samples_ns),
        "rtt_ns_median": int(statistics.median(samples_ns)),
        "rtt_ns_min": min(samples_ns),
        "rtt_ns_max": max(samples_ns),
        "jitter_ns": int(statistics.pstdev(samples_ns)) if len(samples_ns) > 1 else 0,
    }


def probe_topology(region_endpoints, rounds=5, timeout_s=3.0):
    """`region_endpoints`: {region_name: (host, port)}. Probes every
    ordered pair (from the CALLING node's perspective - run once per
    node in the deployment to get the full matrix) and returns
    {(from_region, to_region): probe_rtt(...) result}. LIVE, quarantined -
    see module docstring."""
    matrix = {}
    for region, (host, port) in region_endpoints.items():
        matrix[region] = probe_rtt(host, port, rounds=rounds, timeout_s=timeout_s)
    return {"mode": "LIVE_PROBE", "measured_at_unix_ns": time.time_ns(),
            "results": matrix}


def local_topology(regions):
    """Deterministic stand-in for testing and for run_harness_local.py:
    every region is "reachable" with 0ns measured RTT, because the whole
    run is a single in-process loopback - this is NOT a claim about real
    network cost, and is labeled LOCAL_LOOPBACK so it can never be
    mistaken for probe_topology()'s real measurement. See
    docs/benchmark-harness-spec.md's honest-scoping section."""
    return {"mode": "LOCAL_LOOPBACK", "measured_at_unix_ns": None,
            "results": {r: {"host": None, "port": None, "verdict": "LOOPBACK",
                            "rtt_ns_median": 0, "rtt_ns_min": 0,
                            "rtt_ns_max": 0, "jitter_ns": 0}
                       for r in regions}}


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", action="append", default=[],
                        metavar="REGION=HOST:PORT", required=True,
                        help="repeatable; e.g. --endpoint us-west=20.1.2.3:9800")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()

    endpoints = {}
    for e in args.endpoint:
        region, hostport = e.split("=", 1)
        host, port = hostport.rsplit(":", 1)
        endpoints[region] = (host, int(port))

    result = probe_topology(endpoints, rounds=args.rounds)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print()
