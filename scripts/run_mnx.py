#!/usr/bin/env python3
"""Run MNX gates, emit certificates/mnx_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

GATES = [
    ("MNX-A", "tests/test_mnx_vclock.py", "SOUND", "vector-clock partial order"),
    ("MNX-B", "tests/test_mnx_geometric.py", "SOUND", "causal memory under light-cone ordering"),
    ("MNX-C", "tests/test_mnx_logical.py", "SOUND", "causal memory under vector-clock ordering"),
    ("MNX-D", "tests/test_mnx_bridge.py", "SOUND", "memory ordering matches HorizonProtocol ledger edge-for-edge"),
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
    for dirpath, _, files in os.walk(os.path.join(ROOT, "mnemesis")):
        if "__pycache__" in dirpath:
            continue
        for fn in sorted(files):
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                src_hashes[os.path.relpath(p, ROOT)] = sha256_file(p)

    cert = {
        "certificate_version": "1",
        "benchmark_id": "MNX1",
        "program": "MnemesisOS x HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "convergence_claim": ("a causal ledger IS a provenance-aware multi-observer "
                              "memory: writes=events, merge gate=light-cone gate, "
                              "concurrent writes retained with provenance (PGSD "
                              "deferred selection)"),
        "adversary_model": ("honest observers with possibly-divergent clocks; "
                            "Byzantine observers and a signature/authentication "
                            "layer are OUT OF SCOPE at MNX1 (see "
                            "docs/mnemesis-convergence.md)"),
        "heuristic_warnings": [],
        "unit_convention": {"position": "nanometers (int, GEOMETRIC ordering only)",
                            "time": "nanoseconds (int, GEOMETRIC ordering) or "
                                    "unitless vector-clock counters (LOGICAL "
                                    "ordering)",
                            "c": 299792458, "c_units": "nm/ns (exact integer, "
                                                       "GEOMETRIC ordering only)"},
        "orderings": ["GEOMETRIC (exact light-cone, reuses horizon.geometry "
                     "unmodified)",
                     "LOGICAL (vector-clock happens-before fallback)"],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "mnx_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
