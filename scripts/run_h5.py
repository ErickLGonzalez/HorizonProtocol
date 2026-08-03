#!/usr/bin/env python3
"""Run all H5 gates, emit certificates/h5_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.fixtures import (FRAME_ORIGIN_LLH, NODE_U_NS, NODES_NM,  # noqa: E402
                              SEED_H5, build_registry, trusted_node_params)
from horizon.measure import (C_EFF_DEN, C_EFF_NUM,  # noqa: E402
                             verify_measured_certificate)

GATES = [
    ("H5-A", "tests/test_h5a_budget_gate.py", "SOUND", "uncertainty-budgeted gate math boundary correctness"),
    ("H5-B", "tests/test_h5b_replay_pass.py", "SOUND", "replay PASS over the committed fixture; standalone verifier"),
    ("H5-C", "tests/test_h5c_apparatus_limited.py", "SOUND", "apparatus-limited control on a marginal fixture"),
    ("H5-D", "tests/test_h5d_negative.py", "SOUND", "negative controls REJECTED / APPARATUS_LIMITED with witnesses"),
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
    registry = build_registry()
    node_params = trusted_node_params()  # TRUSTED - never taken from a certificate
    fixtures = []
    apparatus_limited_events = []
    per_event = {}
    for name, origin in (("h5_fixture_capture.json", "capture"),
                         ("h5_fixture_marginal.json", "marginal")):
        path = os.path.join(ROOT, "data", name)
        with open(path) as f:
            cert = json.load(f)
        res = verify_measured_certificate(cert, registry, node_params)
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
        if name == "h5_fixture_marginal.json" and res["verdict"] != "APPARATUS_LIMITED":
            all_pass = False
        if name == "h5_fixture_capture.json" and res["verdict"] != "PASS":
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
        "benchmark_id": "H5",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("a forger without station keys who submits a "
                            "vacuum-c-violating receipt, declares its own "
                            "uncertainty/speed-bound parameters (rejected: "
                            "node_params is trusted caller input, never read "
                            "from the certificate), tampers with a receipt "
                            "after signing, forges a station's own position "
                            "claim, or presents a LIVE_CAPTURE fixture that "
                            "fails its internal self-check; clock/network "
                            "attacks against a legitimately-keyed station and "
                            "any claim of deployed security are OUT OF SCOPE "
                            "(see docs/h5-spec.md)"),
        "heuristic_warnings": [
            {"location": "horizon/fixtures.py", "warning":
             "node positions derived once via a float-based flat-earth "
             "projection, then frozen as integers; synthetic captures are "
             "deterministic pseudo-measurements, not real ones - every "
             "fixture built here is labelled SYNTHETIC_CONSISTENT"},
            {"location": "horizon/capture.py", "warning":
             "live measurement; not part of the trusted path; excluded from "
             "CI; results non-deterministic and unauthenticated; never "
             "imported by any verifier or test"},
            {"location": "horizon/stations.py", "warning":
             "HMAC with demo-derived symmetric keys stands in for signatures; "
             "key distribution trusted"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "seeds": [SEED_H5],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        # H5-specific fields
        "frame_origin_llh": FRAME_ORIGIN_LLH,
        "nodes": [{"id": nid, "pos_nm": list(pos), "u_ns": NODE_U_NS[nid]}
                 for nid, pos in sorted(NODES_NM.items())],
        "c_eff_rational": [C_EFF_NUM, C_EFF_DEN],
        "path_excess_note": ("real fiber/copper paths are longer than the "
                             "straight-line distance and propagate slower "
                             "than vacuum c; this reference implementation "
                             "does not numerically model path excess beyond "
                             "the frozen c_eff = 3/5 c bound - see "
                             "docs/h5-spec.md"),
        "fixtures": fixtures,
        "per_event": per_event,
        "apparatus_limited_events": apparatus_limited_events,
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h5_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
