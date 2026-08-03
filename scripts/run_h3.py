#!/usr/bin/env python3
"""Run all H3 gates, emit certificates/h3_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.distance import (P_CLAIM, PROC_NS, SEED_H3, VERIFIERS,  # noqa: E402
                              multilateration, rtt_bound_witness)
from horizon.db_sim import (COLLUDER_PAIR, HONEST, run_session)  # noqa: E402

GATES = [
    ("H3-A", "tests/test_h3a_rtt.py", "SOUND", "single-verifier RTT bounding"),
    ("H3-B", "tests/test_h3b_multilateration.py", "SOUND", "4-verifier multilateration"),
    ("H3-C", "tests/test_h3c_collusion.py", "SOUND",
     "classical collusion break demonstrated (EXPECTED_ATTACK_SUCCESS)"),
    ("H3-D", "tests/test_h3d_floor.py", "SOUND", "FTL floor control"),
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
        result = "PASS" if ok else "FAIL"
        if gate_id == "H3-C" and ok:
            result = "EXPECTED_ATTACK_SUCCESS"  # the expected verdict; counts as PASS
        results.append({"gate": gate_id, "description": desc,
                        "soundness_tag": tag, "result": result,
                        "counts_as_pass": ok,
                        "unittest_tail": proc.stderr.strip().splitlines()[-1] if proc.stderr else ""})
        print(f"{gate_id}: {result if gate_id == 'H3-C' else ('PASS' if ok else 'FAIL')} - {desc}")

    # sprint extras (deterministic recomputation)
    honest = run_session(HONEST)
    per_verifier_bounds = {
        vid: rtt_bound_witness(honest["measurements"][vid], PROC_NS,
                               VERIFIERS[vid], P_CLAIM)
        for vid in sorted(VERIFIERS)}

    collusion = run_session(COLLUDER_PAIR)
    collusion_res = multilateration(collusion["measurements"], PROC_NS, P_CLAIM)
    collusion_demo = {
        "attacker_positions_nm": collusion["agent_positions"],
        "per_verifier_satisfaction": {
            vid: collusion_res["per_verifier"][vid]["verdict"]
            for vid in sorted(VERIFIERS)},
        "no_prover_at_claimed_position": True,
        "verdict": ("EXPECTED_ATTACK_SUCCESS"
                    if collusion_res["verdict"] == "ADMITTED" else "FAIL"),
        "citation": "Chandran-Goyal-Moriarty-Ostrovsky 2009",
    }

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
        "benchmark_id": "H3",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("distant/decoy provers without the ability to send "
                            "signals faster than light; PLUS the colluding pair "
                            "deliberately IN SCOPE for H3-C to demonstrate that "
                            "classical position verification fails against "
                            "collusion (see docs/h3-spec.md)"),
        "heuristic_warnings": [
            {"location": "horizon/db_sim.py", "warning":
             "RTTs computed, not measured; simulator excluded from trusted path"},
            {"location": "horizon/stations.py", "warning":
             "HMAC with demo-derived symmetric keys stands in for signatures; "
             "key distribution trusted"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "seeds": [SEED_H3],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        # H3-specific fields
        "verifiers_nm": {vid: list(v) for vid, v in sorted(VERIFIERS.items())},
        "p_claim_nm": list(P_CLAIM),
        "proc_ns": PROC_NS,
        "per_verifier_bounds": per_verifier_bounds,
        "collusion_demo": collusion_demo,
        "classical_pv_break_demonstrated":
            collusion_demo["verdict"] == "EXPECTED_ATTACK_SUCCESS",
        "claim_scope": ("classical position verification is assurance-grade "
                        "only; collusion defeats it (demonstrated in H3-C); "
                        "mitigation belongs to a quantum layer out of scope "
                        "for this repository"),
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h3_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"classical_pv_break_demonstrated: {cert['classical_pv_break_demonstrated']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
