#!/usr/bin/env python3
"""Run all H1 gates, emit the aggregate JSON certificate, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

GATES = [
    ("H1-A", "tests/test_h1a_geometry.py", "SOUND", "exact light-cone geometry kernel"),
    ("H1-B", "tests/test_h1b_receipts.py", "SOUND", "receipt authenticity round-trip"),
    ("H1-C", "tests/test_h1c_cone_certificate.py", "SOUND", "cone certificate + standalone verifier"),
    ("H1-D", "tests/test_h1d_ledger.py", "SOUND", "causal ledger admissibility / concurrency"),
    ("H1-E", "tests/test_h1e_negative_controls.py", "SOUND", "negative controls REJECTED with witnesses"),
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

    src_hashes = {}
    for dirpath, _, files in os.walk(os.path.join(ROOT, "horizon")):
        for fn in sorted(files):
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                src_hashes[os.path.relpath(p, ROOT)] = sha256_file(p)

    cert = {
        "certificate_version": "1",
        "benchmark_id": "H1",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("single forger without station keys; colluding "
                            "multi-site adversaries and key compromise are OUT OF SCOPE "
                            "at H1 (see docs/h1-spec.md)"),
        "heuristic_warnings": [
            {"location": "horizon/stations.py", "warning":
             "HMAC with demo-derived symmetric keys stands in for signatures; "
             "key distribution trusted"},
            {"location": "horizon/simulate.py", "warning":
             "arrival times computed, not measured; simulator excluded from trusted path"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h1_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
