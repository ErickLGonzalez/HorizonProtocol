#!/usr/bin/env python3
"""Run all H2 gates, emit certificates/h2_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.commitment import (P_FIELD, SITE_1, SITE_2, DT_RESP_NS,  # noqa: E402
                                DT_ROUND_NS, K_SUSTAIN, SEED_H2,
                                isolation_gate, sustained_isolation_gate)
from horizon.geometry import min_light_time_ns  # noqa: E402
from horizon.commit_sim import HONEST, run_session  # noqa: E402

GATES = [
    ("H2-A", "tests/test_h2a_algebra.py", "SOUND", "commit-sustain-reveal chain algebra"),
    ("H2-B", "tests/test_h2b_timing.py", "SOUND", "causal-isolation precondition (two-sided)"),
    ("H2-C", "tests/test_h2c_sustain.py", "SOUND", "full sustained run on schedule"),
    ("H2-D", "tests/test_h2d_negative.py", "SOUND", "negative controls REJECTED / APPARATUS_LIMITED"),
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
    one_way = min_light_time_ns(SITE_1, SITE_2)
    sess = run_session(HONEST, b=1)
    iso = isolation_gate(SITE_1, SITE_2, DT_RESP_NS)
    isolation_witnesses = [{"round": rec["k"], "exact_witness": iso["exact_witness"]}
                           for rec in sess["rounds"]]
    sustained_iso = sustained_isolation_gate(SITE_1, SITE_2, DT_ROUND_NS, DT_RESP_NS)
    if sustained_iso["verdict"] != "PASS":
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
        "benchmark_id": "H2",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("cheating committer attempting post-hoc bit flip or "
                            "transcript tamper, without the power to rewrite "
                            "already-sent round responses; arbitrary adversaries "
                            "and any security PROOF of binding are OUT OF SCOPE "
                            "(see docs/h2-spec.md)"),
        "heuristic_warnings": [
            {"location": "horizon/commit_sim.py", "warning":
             "round timings computed, not measured; secrets/challenges derived "
             "from a frozen seed; simulator excluded from trusted path"},
            {"location": "horizon/stations.py", "warning":
             "HMAC with demo-derived symmetric keys stands in for signatures; "
             "key distribution trusted"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "seeds": [SEED_H2],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        # H2-specific fields
        "field_prime": P_FIELD,
        "sites_nm": {"site_1": list(SITE_1), "site_2": list(SITE_2)},
        "dt_resp_ns": DT_RESP_NS,
        "dt_round_ns": DT_ROUND_NS,
        "k_sustain": K_SUSTAIN,
        "one_way_light_time_ns": one_way,
        "binding_duration_ns": sess["binding_duration_ns"],
        "per_round_transcript_hashes": sess["transcript_hashes"],
        "isolation_witnesses": isolation_witnesses,
        "sustained_isolation": sustained_iso,
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h2_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
