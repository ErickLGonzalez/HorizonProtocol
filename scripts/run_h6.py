#!/usr/bin/env python3
"""Run all H6 gates, emit certificates/h6_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.geo_fixtures import SEED_H6  # noqa: E402
from horizon.geo_registry import load_geo_registry, trusted_node_params  # noqa: E402
from horizon.measure import (C_EFF_DEN, C_EFF_NUM,  # noqa: E402
                             verify_measured_certificate)

GATES = [
    ("H6-A", "tests/test_h6a_frame.py", "HEURISTIC", "real geography -> exact nm lattice (quantized)"),
    ("H6-B", "tests/test_h6b_replay.py", "SOUND", "consistent fixture over real geography PASSES; verifier standalone"),
    ("H6-C", "tests/test_h6c_apparatus.py", "SOUND", "marginal fixture -> APPARATUS_LIMITED, never silent PASS"),
    ("H6-D", "tests/test_h6d_negative.py", "SOUND", "negative controls REJECTED / APPARATUS_LIMITED with witnesses"),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def main():
    results = []
    all_pass = True
    for gate_id, path, tag, desc in GATES:
        proc = subprocess.run([sys.executable, "-m", "unittest", "-v",
                               path.replace("/", ".").removesuffix(".py")],
                              cwd=ROOT, capture_output=True, text=True)
        ok = proc.returncode == 0
        all_pass &= ok
        results.append({"gate": gate_id, "description": desc,
                        "soundness_tag": tag,
                        "result": "PASS" if ok else "FAIL",
                        "unittest_tail": proc.stderr.strip().splitlines()[-1] if proc.stderr else ""})
        print(f"{gate_id}: {'PASS' if ok else 'FAIL'} - {desc}")

    # sprint extras (deterministic recomputation over the committed fixtures)
    frame, registry, node_llh, node_u_ns, spec = load_geo_registry()
    node_params = trusted_node_params(node_u_ns)  # TRUSTED - never from a certificate
    fixtures = []
    apparatus_limited_events = []
    per_event = {}
    for name, origin in (("h6_fixture_capture.json", "capture"),
                         ("h6_fixture_marginal.json", "marginal")):
        path = os.path.join(ROOT, "data", name)
        with open(path) as f:
            cert = json.load(f)
        res = verify_measured_certificate(cert, registry, node_params,
                                          required_station_ids=set(registry))
        event_hash = cert["event"]["payload_hash"]
        per_event[f"{origin}:{event_hash}"] = {
            "fixture": name, "verdict": res["verdict"],
            "per_node_verdicts": {nid: w["verdict"] for nid, w in res["per_node"].items()},
            "budget_witnesses": res["per_node"],
        }
        if res["verdict"] == "APPARATUS_LIMITED":
            apparatus_limited_events.append(f"{origin}:{event_hash}")
        fixtures.append({"name": name, "origin": cert["fixture_origin"],
                         "sha256": sha256_file(path)})
        if name == "h6_fixture_marginal.json" and res["verdict"] != "APPARATUS_LIMITED":
            all_pass = False
        if name == "h6_fixture_capture.json" and res["verdict"] != "PASS":
            all_pass = False

    src_hashes = {}
    for dirpath, _, files in os.walk(os.path.join(ROOT, "horizon")):
        if "__pycache__" in dirpath:
            continue
        for fn in sorted(files):
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                src_hashes[os.path.relpath(p, ROOT)] = sha256_file(p)

    cert = {
        "certificate_version": "1",
        "benchmark_id": "H6",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("a forger without station keys who submits a "
                            "vacuum-c-violating receipt, declares its own "
                            "uncertainty/speed-bound parameters (rejected: "
                            "node_params is trusted caller input, never read "
                            "from the certificate - identical to H5), tampers "
                            "with a receipt after signing, forges a node's own "
                            "position claim, or submits an unknown node; "
                            "colluding multi-node adversaries are OUT OF SCOPE "
                            "(classical PV limit, demonstrated in H3-C); node "
                            "key compromise and curvature/relativistic frame "
                            "effects beyond local-ENU Minkowski are OUT OF "
                            "SCOPE (see docs/h6-spec.md)"),
        "heuristic_warnings": [
            {"location": "horizon/geo_frame.py", "warning":
             "WGS84 ellipsoid -> ECEF -> ENU geodesy is floating point; "
             "quantized to the nm lattice once, then every gate is exact"},
            {"location": "horizon/geo_fixtures.py", "warning":
             "synthetic captures are deterministic pseudo-measurements, not "
             "real ones - every fixture built here is labelled "
             "SYNTHETIC_CONSISTENT"},
            {"location": "horizon/h6_capture.py", "warning":
             "live measurement against public NTP stand-ins; not part of the "
             "trusted path; excluded from CI; results non-deterministic and "
             "unauthenticated; never imported by any verifier or test"},
            {"location": "horizon/stations.py", "warning":
             "HMAC with demo-derived symmetric keys stands in for signatures; "
             "key distribution trusted"},
        ],
        "unit_convention": {"position": "nanometers (int, local ENU lattice)",
                            "time": "nanoseconds (int)", "c": 299792458,
                            "c_units": "nm/ns (exact integer)"},
        "seeds": [SEED_H6],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        # H6-specific fields
        "geo_frame": frame.metadata(),
        "nodes": {nid: {"pos_nm": list(registry[nid].pos_nm),
                        "u_ns": node_u_ns[nid], "llh": node_llh[nid]}
                 for nid in sorted(registry)},
        "c_eff_rational": [C_EFF_NUM, C_EFF_DEN],
        "fixtures": fixtures,
        "per_event": per_event,
        "apparatus_limited_events": apparatus_limited_events,
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h6_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
