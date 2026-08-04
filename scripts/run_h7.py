#!/usr/bin/env python3
"""Run all H7 gates, emit certificates/h7_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.beq import beq_verdict  # noqa: E402
from horizon.deepspace import light_time_table  # noqa: E402
from horizon.quantum_interface import REGISTERED_ASSUMPTIONS  # noqa: E402

GATES = [
    ("H7-A", "tests/test_h7a_deepspace.py", "SOUND", "real Earth-Mars light-time geometry (exact)"),
    ("H7-B", "tests/test_h7b_latency_gate.py", "SOUND", "unified latency-budget gate (telemetry + attestation)"),
    ("H7-C", "tests/test_h7c_beq.py", "SOUND", "bounded-entanglement security tracker (exact fractions)"),
    ("H7-D", "tests/test_h7d_protocol.py", "SOUND", "end-to-end protocol; verifier excludes simulator"),
    ("H7-E", "tests/test_h7e_negative.py", "SOUND", "negative controls; qubit sim quarantined"),
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
        results.append({"gate": gate_id, "description": desc, "soundness_tag": tag,
                        "result": "PASS" if ok else "FAIL",
                        "unittest_tail": proc.stderr.strip().splitlines()[-1] if proc.stderr else ""})
        print(f"{gate_id}: {'PASS' if ok else 'FAIL'} - {desc}")

    demo_beq = beq_verdict(73, 3, 4)

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
        "benchmark_id": "H7",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "security_verdict_class": "CONDITIONAL_BE_Q",
        "application": ("groundwork for deep-space authenticated telemetry and "
                        "trajectory attestation (Earth-Mars and beyond); latency "
                        "is the security budget, not a defect"),
        "adversary_model": ("colluding adversaries with pre-shared entanglement "
                            "bounded by Q; classical collusion defeats classical "
                            "PV (CGMO 2009), QPV restores soundness for "
                            "Q < Q_secure; UNCONDITIONAL security is impossible"),
        "heuristic_warnings": [
            {"location": "horizon/qubit_sim.py", "warning":
             "DETERMINISTIC idealized BB84/SWAP outcomes; NOT a quantum "
             "device, NOT a security proof; quarantined from verifier path"},
            {"location": "horizon/quantum_interface.py", "warning":
             "quantum optical channel is a DOCUMENTED INTERFACE with "
             "registered assumptions A1-A4, not an implementation"},
            {"location": "horizon/deepspace.py", "warning":
             "light_time_table()'s seconds/minutes fields are float, for "
             "human-readable certificate display only"},
            {"location": "horizon/beq.py", "warning":
             "adversary_bound_float/target_soundness_float are float "
             "renderings of exact Fraction values, for readability only; "
             "the soundness decision itself is exact rational comparison"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_eff_vacuum": [1, 1]},
        "registered_assumptions": REGISTERED_ASSUMPTIONS,
        "earth_mars_light_times": light_time_table(),
        "demo_beq_verdict": demo_beq,
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h7_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"security verdict class: {cert['security_verdict_class']} "
         f"(Q_secure={demo_beq['entanglement_threshold']['Q_secure_linear']})")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
