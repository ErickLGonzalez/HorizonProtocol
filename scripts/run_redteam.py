#!/usr/bin/env python3
"""Run the independent red-team harness, emit certificates/redteam_certificate.json,
exit 0 iff zero bypasses across every attack class."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from redteam import SEED  # noqa: E402
from redteam.attacks import run_all  # noqa: E402

GATES = [
    ("RT-hygiene", "tests/test_redteam.py", "SOUND",
    "attacks hit only the public API; zero bypasses across every attack class"),
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
                        "result": "PASS" if ok else "FAIL"})
        print(f"{gate_id}: {'PASS' if ok else 'FAIL'} - {desc}")

    attack_reports = run_all(SEED)
    total_trials = sum(r["trials"] for r in attack_reports)
    total_bypasses = sum(len(r["bypasses"]) for r in attack_reports)
    if total_bypasses:
        all_pass = False

    for r in attack_reports:
        n = len(r["bypasses"])
        print(f"  {r['attack']}: {n} bypass(es) / {r['trials']} trials")

    src_hashes = {}
    for dirpath, _, files in os.walk(os.path.join(ROOT, "redteam")):
        if "__pycache__" in dirpath:
            continue
        for fn in sorted(files):
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                src_hashes[os.path.relpath(p, ROOT)] = sha256_file(p)

    cert = {
        "certificate_version": "1",
        "benchmark_id": "RT1",
        "program": "HorizonProtocol Red-Team Harness",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "BENCHMARK",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "adversary_model": ("an independent attacker with no privileged "
                            "access to verifier internals, private keys, "
                            "or trusted caller state - attacks constructed "
                            "and submitted through each gate's PUBLIC API "
                            "only; zero bypasses is the pass condition for "
                            "every attack class; any nonzero residual is "
                            "reported as an explicit count, never silently "
                            "treated as zero"),
        "heuristic_warnings": [
            {"location": "redteam/attacks.py", "warning":
             "RT-A's independent reference implementation uses "
             "Decimal-based real-number arithmetic (a deliberately "
             "different algorithm from the exact-integer kernel it "
             "cross-checks); it is the attacker's tool, not a security "
             "gate itself"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "seeds": [SEED],
        "gates": results,
        "aggregate": "PASS" if all_pass else "FAIL",
        "attack_reports": [{"attack": r["attack"], "trials": r["trials"],
                            "bypass_count": len(r["bypasses"]),
                            "bypasses": r["bypasses"]} for r in attack_reports],
        "total_trials": total_trials,
        "total_bypasses": total_bypasses,
        "source_hashes": src_hashes,
        "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "redteam_certificate.json")
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}  ({total_bypasses} bypass(es) / {total_trials} trials)")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
