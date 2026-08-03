#!/usr/bin/env python3
"""Run all H4 gates, emit certificates/h4_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.beacon import (EMITTERS, SEED_H4, T_EMIT_NS,  # noqa: E402
                            pairwise_spacelike_witnesses, verify_beacon)
from horizon.beacon_sim import build_full_beacon, statistical_sanity  # noqa: E402

GATES = [
    ("H4-A", "tests/test_h4a_spacelike.py", "SOUND", "pairwise spacelike separation"),
    ("H4-B", "tests/test_h4b_binding.py", "SOUND", "block binding + cone certificates + standalone verify"),
    ("H4-C", "tests/test_h4c_sanity.py", "HEURISTIC", "byte-balance smoke test (NOT a randomness certification)"),
    ("H4-D", "tests/test_h4d_negative.py", "SOUND", "negative controls REJECTED with witnesses"),
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

    # sprint extras (deterministic recomputation)
    beacon_cert, registry = build_full_beacon()
    verify_res = verify_beacon(beacon_cert, registry)
    emissions = {eid: {"time_ns": T_EMIT_NS, "pos_nm": pos}
                 for eid, pos in EMITTERS.items()}
    pairwise = pairwise_spacelike_witnesses(emissions)
    sanity = statistical_sanity(bytes.fromhex(beacon_cert["beacon_value_hex"]))

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
        "benchmark_id": "H4",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("a forger without station keys who may inject "
                            "timelike-correlated emitters, tamper with blocks "
                            "post-binding, duplicate sources, or embed forged "
                            "cone certificates; statistical adversaries and "
                            "randomness quality are OUT OF SCOPE "
                            "(see docs/h4-spec.md)"),
        "heuristic_warnings": [
            {"location": "horizon/beacon_sim.py", "warning":
             "blocks are deterministic pseudo-entropy (SHA-256 of frozen "
             "seed), not physical randomness; arrival times computed, not "
             "measured; simulator excluded from trusted path"},
            {"location": "horizon/beacon_sim.py", "warning":
             "statistical_sanity is a smoke test, not a randomness "
             "certification; causal independence != statistical quality"},
            {"location": "horizon/stations.py", "warning":
             "HMAC with demo-derived symmetric keys stands in for signatures; "
             "key distribution trusted"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "seeds": [SEED_H4],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        # H4-specific fields
        "emitters_nm": {eid: list(p) for eid, p in sorted(EMITTERS.items())},
        "t_emit_ns": T_EMIT_NS,
        "pairwise_spacelike_witnesses": pairwise,
        "per_block": [{"emitter_id": b["emitter_id"],
                       "block_sha256": b["block_sha256"],
                       "cone_certificate_verdict":
                           verify_res["cone_certificate_verdicts"][b["emitter_id"]]}
                      for b in beacon_cert["per_block"]],
        "beacon_value_hex": beacon_cert["beacon_value_hex"],
        "beacon_verify_verdict": verify_res["verdict"],
        "statistical_sanity": sanity,
        "claim_scope": ("beacon certifies independence by causal structure "
                        "only; it never certifies statistical randomness "
                        "quality"),
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h4_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
