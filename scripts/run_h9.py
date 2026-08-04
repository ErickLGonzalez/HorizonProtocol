#!/usr/bin/env python3
"""Run H9 gates (the shared red-team harness's H8-surface attacks), emit
certificates/h9_certificate.json, exit 0 iff green.

H9 reuses `redteam.attacks` - the same module RT1 runs - rather than a
second attacker package; see docs/h9-spec.md, section 2.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from redteam import SEED  # noqa: E402
from redteam.attacks import (attack_h8_boundary_skew_fuzz,  # noqa: E402
                             attack_h8_replay_fuzz,
                             attack_ledger_cycle_fuzz,
                             attack_ledger_named_scenarios,
                             attack_timing_fuzz)

GATE_TESTS = [
    ("H9-A", "tests.test_h9a_fuzz", "timing fuzz (reuses RT-A): zero misclassifications"),
    ("H9-B", "tests.test_h9b_replay", "H8 replay forgeries rejected"),
    ("H9-C", "tests.test_h9c_boundary_skew", "no impossible arrival admitted (H8 trust boundary)"),
    ("H9-D", "tests.test_h9d_ledger", "ledger refuses cycles/backward/spacelike edges"),
    ("H9-E", "tests.test_h9e_hygiene", "attacks use public gates only; independent oracle"),
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

    rng = __import__("random").Random(SEED)
    reports = {
        "timing_fuzz": attack_timing_fuzz(rng, trials=5000),
        "h8_replay": attack_h8_replay_fuzz(rng, trials=1000),
        "h8_boundary_skew": attack_h8_boundary_skew_fuzz(rng, trials=1000),
        "ledger_cycle": attack_ledger_cycle_fuzz(rng, trials=2000),
        "ledger_named": attack_ledger_named_scenarios(),
    }
    total_trials = sum(r["trials"] for r in reports.values())
    total_bypasses = sum(len(r["bypasses"]) for r in reports.values())
    any_bypass = total_bypasses > 0

    src = {}
    for d in ("horizon", "redteam"):
        for dp, _, files in os.walk(os.path.join(ROOT, d)):
            for fn in sorted(files):
                if fn.endswith(".py"):
                    fp = os.path.join(dp, fn)
                    src[os.path.relpath(fp, ROOT)] = sha(fp)

    cert = {
        "certificate_version": "1", "benchmark_id": "H9", "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE", "execution_tier": "BENCHMARK",
        "promotion_allowed": False, "empirical_claim": "NONE",
        "purpose": ("independent red-team, reusing RT1's shared attacker module, "
                   "extended to attack H8's signed-capture and capture-verify surface; "
                   "see docs/h9-spec.md section 2 for why this is one harness, not two"),
        "adversary_model": ("an independent attacker with no privileged access to "
                           "verifier internals, node keys, or trusted caller state - "
                           "attacks constructed and submitted through each gate's "
                           "PUBLIC API only (horizon.signed_capture, "
                           "horizon.capture_verify, horizon.geometry, horizon.ledger); "
                           "zero bypasses is the pass condition for every attack class"),
        "heuristic_warnings": [
            {"location": "redteam/attacks.py",
             "warning": "RT-A/H9-A's independent reference implementation uses "
                       "Decimal-based real-number arithmetic (a deliberately "
                       "different algorithm from the exact-integer kernel it "
                       "cross-checks); it is the attacker's tool, not a security "
                       "gate itself"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                           "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "attacks_bypassed_security": any_bypass,  # must be False
        "attack_reports": {name: {"trials": r["trials"], "bypass_count": len(r["bypasses"]),
                                  "bypasses": r["bypasses"]}
                          for name, r in reports.items()},
        "gates": results,
        "aggregate": "PASS" if (all_pass and not any_bypass) else "FAIL",
        "total_trials": total_trials, "total_bypasses": total_bypasses,
        "source_hashes": src, "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h9_certificate.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"any attack bypassed security: {any_bypass}  ({total_bypasses}/{total_trials} trials)")
    print(f"certificate written: {out}")
    return 0 if cert["aggregate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
