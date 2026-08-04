#!/usr/bin/env python3
"""Run the formal kernel proof (Z3), emit certificates/formal_certificate.json.

This is the ONLY script in the repository with a non-stdlib dependency
(`z3-solver`), confined entirely to this offline proof artifact - see
formal/README.md. If z3-solver is not installed, this exits with code 2
("SKIPPED") rather than 1 ("FAIL"); scripts/run_all.py treats a 2 as
non-fatal so a fresh clone with no extra installs still gets
"ALL HORIZON GATES GREEN" on the stdlib-only path. Exit 0 iff every theorem
is PROVEN and the proof-to-code binding tests pass.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import z3  # noqa: F401
except ImportError:
    print("PROOF: SKIPPED - z3-solver not installed "
         "(pip install z3-solver && python3 scripts/run_formal.py to verify)")
    sys.exit(2)

from formal.kernel_proof import run_all as run_theorems  # noqa: E402

GATE_TESTS = [
    ("C1-A", "formal.tests.test_kernel_proof", "all five theorems PROVEN by Z3"),
    ("C1-B", "formal.tests.test_proof_matches_code",
    "proven predicate matches horizon.geometry.causally_admissible exactly"),
]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    results, all_pass = [], True
    for gid, mod, desc in GATE_TESTS:
        p = subprocess.run([sys.executable, "-m", "unittest", "-v", mod],
                           cwd=ROOT, capture_output=True, text=True)
        ok = p.returncode == 0
        all_pass &= ok
        results.append({"gate": gid, "description": desc, "soundness_tag": "SOUND",
                        "result": "PASS" if ok else "FAIL"})
        print(f"{gid}: {'PASS' if ok else 'FAIL'} - {desc}")

    theorems = run_theorems()
    all_proven = all(t["proven"] for t in theorems)
    all_pass &= all_proven

    src = {}
    for dp, _, files in os.walk(os.path.join(ROOT, "formal")):
        if "__pycache__" in dp:
            continue
        for fn in sorted(files):
            if fn.endswith(".py") or fn.endswith(".dfy"):
                fp = os.path.join(dp, fn)
                src[os.path.relpath(fp, ROOT)] = sha(fp)
    src["horizon/geometry.py"] = sha(os.path.join(ROOT, "horizon", "geometry.py"))

    cert = {
        "certificate_version": "1", "benchmark_id": "C1", "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE", "execution_tier": "BENCHMARK",
        "promotion_allowed": False, "empirical_claim": "NONE",
        "adversary_model": ("not applicable - this is a machine-checked mathematical "
                           "proof of kernel correctness (Z3 SMT solver over the "
                           "integers), not an adversarial security test; see "
                           "docs/formal-kernel-spec.md"),
        "heuristic_warnings": [
            {"location": "formal/kernel.dfy",
             "warning": "human-readable Dafny companion to the enforced Z3 proof; "
                       "the Dafny toolchain is not available in this environment, "
                       "so this file has not been independently machine-verified "
                       "by `dafny verify` - treat as best-effort, not as an "
                       "additionally-enforced artifact"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                           "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "theorems": [{"theorem": t["theorem"], "result": t["result"],
                     "z3_status": t["z3_status"], "note": t["note"]} for t in theorems],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        "source_hashes": src, "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "formal_certificate.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
