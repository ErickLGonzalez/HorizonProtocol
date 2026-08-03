#!/usr/bin/env python3
"""Run every H-series benchmark runner in order; exit 0 iff all green.

H3's gate H3-C records EXPECTED_ATTACK_SUCCESS - that is the expected
result of the honest collusion demonstration and counts as PASS.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNERS = [
    ("H1", "scripts/run_h1.py", "h1_certificate.json", ""),
    ("H2", "scripts/run_h2.py", "h2_certificate.json",
     "   binding_duration_ns recorded; isolation witnesses exact"),
    ("H3", "scripts/run_h3.py", "h3_certificate.json",
     "   classical_pv_break_demonstrated: true (EXPECTED_ATTACK_SUCCESS)"),
    ("H4", "scripts/run_h4.py", "h4_certificate.json",
     "   beacon certified: causal independence only"),
    ("H5", "scripts/run_h5.py", "h5_certificate.json",
     "   real-measurement bridge; APPARATUS_LIMITED honored on marginal fixture"),
    ("H6", "scripts/run_h6.py", "h6_certificate.json",
     "   multi-node cone certificates over real geography; same H5 gate reused"),
    ("MNX1", "scripts/run_mnx.py", "mnx_certificate.json",
     "   MnemesisOS causal memory; ordering matches the ledger edge-for-edge"),
]


def main():
    all_green = True
    lines = []
    for bench, runner, cert_name, suffix in RUNNERS:
        proc = subprocess.run([sys.executable, os.path.join(ROOT, runner)],
                              cwd=ROOT, capture_output=True, text=True)
        ok = proc.returncode == 0
        with open(os.path.join(ROOT, "certificates", cert_name)) as f:
            cert = json.load(f)
        n_gates = len(cert["gates"])
        aggregate = cert["aggregate"]
        ok = ok and aggregate == "PASS"
        all_green &= ok
        status = aggregate if aggregate == "PASS" else "FAIL"
        lines.append(f"{bench}: {status} ({n_gates}/{n_gates} gates)"
                     f"{suffix}" if ok else f"{bench}: FAIL")
    for ln in lines:
        print(ln)

    validate_proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "validate_certificates.py")],
        cwd=ROOT, capture_output=True, text=True)
    validate_ok = validate_proc.returncode == 0
    all_green &= validate_ok
    print(f"certificates validated: {'OK' if validate_ok else 'FAIL'}")
    if not validate_ok:
        print(validate_proc.stdout)

    print("ALL HORIZON GATES GREEN" if all_green else "GATES FAILING - see above")
    return 0 if all_green else 1


if __name__ == "__main__":
    sys.exit(main())
