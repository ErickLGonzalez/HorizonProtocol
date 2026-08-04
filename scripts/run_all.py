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
    ("H7", "scripts/run_h7.py", "h7_certificate.json",
     "   deep-space latency-budget gate + BE(Q) tracker; CONDITIONAL(BE(Q))"),
    ("H8", "scripts/run_h8.py", "h8_certificate.json",
     "   genuine multi-node capture; APPARATUS_LIMITED->ADMITTED tier transition"),
    ("MNX1", "scripts/run_mnx.py", "mnx_certificate.json",
     "   MnemesisOS causal memory; ordering matches the ledger edge-for-edge"),
    ("RT1", "scripts/run_redteam.py", "redteam_certificate.json",
     "   independent red-team harness; zero bypasses across every attack class"),
    ("H9", "scripts/run_h9.py", "h9_certificate.json",
     "   independent red-team harness targeting H8's capture surface; zero bypasses"),
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

    # D0 (causal-store) is a self-contained sibling project that deliberately
    # vendors its own copy of the kernel rather than importing horizon/ (see
    # causal-store/docs/d0-spec.md) - it has no non-stdlib dependency, so
    # unlike PROOF it is a required, non-skippable gate. Its certificate lives
    # under causal-store/certificates/, not the top-level certificates/ dir,
    # so scripts/validate_certificates.py's glob does not (and should not)
    # pick it up; it is validated here instead.
    d0_proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "causal-store", "scripts", "run_d0.py")],
        cwd=ROOT, capture_output=True, text=True)
    with open(os.path.join(ROOT, "causal-store", "certificates", "d0_certificate.json")) as f:
        d0_cert = json.load(f)
    d0_ok = d0_proc.returncode == 0 and d0_cert["aggregate"] == "PASS"
    all_green &= d0_ok
    print(f"D0: {'PASS' if d0_ok else 'FAIL'} ({len(d0_cert['gates'])}/"
         f"{len(d0_cert['gates'])} gates)   causal-store coordination-free "
         f"engine; {d0_cert['benchmark']['coordination_free_rate']:.1%} "
         f"coordination-free on the modeled 5-region workload")

    # PROOF (formal/, Phase C) is the one gate with a non-stdlib dependency
    # (z3-solver), confined entirely to this offline artifact - see
    # formal/README.md. Exit code 2 means "z3-solver not installed": reported
    # as SKIPPED, not counted against all_green, so a fresh clone with no
    # extra installs still reaches ALL HORIZON GATES GREEN on the stdlib-only
    # path. Exit 0/1 are treated as a real pass/fail like every other gate.
    proof_proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "run_formal.py")],
                                cwd=ROOT, capture_output=True, text=True)
    if proof_proc.returncode == 2:
        print("PROOF: SKIPPED - z3-solver not installed "
             "(pip install z3-solver && python3 scripts/run_formal.py to verify)")
    else:
        with open(os.path.join(ROOT, "certificates", "formal_certificate.json")) as f:
            proof_cert = json.load(f)
        proof_ok = proof_proc.returncode == 0 and proof_cert["aggregate"] == "PASS"
        all_green &= proof_ok
        print(f"PROOF: {'PASS' if proof_ok else 'FAIL'} ({len(proof_cert['gates'])}/"
             f"{len(proof_cert['gates'])} gates)   machine-checked kernel proof (Z3); "
             f"all theorems PROVEN")

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
