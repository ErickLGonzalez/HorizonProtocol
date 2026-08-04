#!/usr/bin/env python3
"""Run H8 gates, emit certificates/h8_certificate.json, exit 0 iff green."""
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from horizon.build_frame import TIERS, load_registry  # noqa: E402
from horizon.capture_verify import verify_capture  # noqa: E402

GATES = [
    ("H8-A", "tests.test_h8a_capture", "SOUND", "signed capture round-trip + deterministic replay"),
    ("H8-B", "tests.test_h8b_honest", "SOUND", "honest capture: ADMITTED/APPARATUS_LIMITED, no spurious reject"),
    ("H8-C", "tests.test_h8c_spoof", "SOUND", "rogue-key spoof REJECTED at signature gate"),
    ("H8-D", "tests.test_h8d_tier_transition", "SOUND", "APPARATUS_LIMITED->ADMITTED across timing tiers"),
    ("H8-E", "tests.test_h8e_trust_boundary", "SOUND", "trust-boundary + real-fast-signal regression coverage"),
]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    results, all_pass = [], True
    for gid, mod, tag, desc in GATES:
        p = subprocess.run([sys.executable, "-m", "unittest", "-v", mod],
                           cwd=ROOT, capture_output=True, text=True)
        ok = p.returncode == 0
        all_pass &= ok
        results.append({"gate": gid, "description": desc, "soundness_tag": tag,
                        "result": "PASS" if ok else "FAIL"})
        print(f"{gid}: {'PASS' if ok else 'FAIL'} - {desc}")

    _, reg, _ = load_registry()
    tier_results = {}
    for tier in ("NTP", "PTP"):
        r = {k: {**v, "u_ns": TIERS[tier], "tier": tier} for k, v in reg.items()}
        with open(os.path.join(ROOT, "data", f"h8_capture_{tier.lower()}.json")) as f:
            cap = json.load(f)
        res = verify_capture(cap, r, required_node_ids=set(reg.keys()))
        tier_results[tier] = {p["node_id"]: p["verdict"] for p in res["per_receipt"]}

    src = {}
    for dp, _, files in os.walk(os.path.join(ROOT, "horizon")):
        for fn in sorted(files):
            if fn.endswith(".py"):
                fp = os.path.join(dp, fn)
                src[os.path.relpath(fp, ROOT)] = sha(fp)

    cert = {
        "certificate_version": "1", "benchmark_id": "H8", "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE", "execution_tier": "BENCHMARK",
        "promotion_allowed": False, "empirical_claim": "NONE",
        "capture_origin": "MEASURED_MODEL (committed replay; live_capture.py is the real on-ramp)",
        "adversary_model": ("forger without node keys (rogue-key spoof REJECTED at signature "
                           "gate) or without access to trusted c_eff/registry parameters "
                           "(declared c_eff inside a capture is provenance only, never fed "
                           "into classification); colluding multi-node adversaries OUT OF "
                           "SCOPE (H9 red-team quantifies residual surface)"),
        "heuristic_warnings": [
            {"location": "horizon/signed_capture.py::measure_now",
             "warning": "live system-time measurement; non-deterministic; not in verifier path"},
            {"location": "scripts/live_capture.py",
             "warning": "manual live capture; quarantined from CI and verifier"},
            {"location": "data/h8_capture_*.json",
             "warning": "MEASURED_MODEL: physically-consistent capture model (fiber c_eff=3/5, "
                       "route excess 1.3x, tier clock error); a stand-in for genuine live capture"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                           "c": 299792458, "c_eff": [3, 5], "route_excess": [13, 10]},
        "timing_tiers": TIERS,
        "tier_verdicts": tier_results,
        "finding": ("co-located node (zero flight) is APPARATUS_LIMITED at every tier; an "
                   "intermediate node (~475 km) transitions APPARATUS_LIMITED->ADMITTED from "
                   "NTP to PTP; distant nodes ADMITTED at all tiers"),
        "gates": results, "aggregate": "PASS" if all_pass else "FAIL",
        "source_hashes": src, "python_version": platform.python_version(),
    }
    out = os.path.join(ROOT, "certificates", "h8_certificate.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"tier transition (us-east-2): NTP={tier_results['NTP']['us-east-2']} -> PTP={tier_results['PTP']['us-east-2']}")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
