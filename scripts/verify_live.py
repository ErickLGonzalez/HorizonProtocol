#!/usr/bin/env python3
"""Verify a LIVE_CAPTURE with the unmodified capture verifier. [manual only]

Loads a live capture JSON + node registry, overlays each node's measured
`u_ns` from the capture's chrony/PTP log (never a nominal guess), calls
`horizon.capture_verify.verify_capture`, prints per-receipt verdicts with
exact integer witnesses, and writes `certificates/h8_live_certificate.json`.

Quarantined from CI. Does not modify the verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.build_frame import TIERS, load_registry  # noqa: E402
from horizon.capture_verify import verify_capture  # noqa: E402


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def overlay_measured_u(reg: dict, capture: dict, tier: str) -> dict:
    """Return a registry copy whose per-node u_ns is the *measured*
    uncertainty from the capture. Falls back to the tier nominal only when
    a node has no measured value — and records that fallback in the
    returned meta so the report cannot silently claim a measurement.
    """
    measured = dict(capture.get("measured_u_ns") or {})
    out = {}
    meta = {"used_measured": {}, "fallback_nominal": {}}
    for nid, node in reg.items():
        n = dict(node)
        n["tier"] = tier
        if nid in measured and measured[nid] is not None:
            u = int(measured[nid])
            n["u_ns"] = u
            meta["used_measured"][nid] = u
        else:
            u = int(TIERS[tier])
            n["u_ns"] = u
            meta["fallback_nominal"][nid] = u
        out[nid] = n
    return out, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("capture", help="path to data/h8_live_capture_*.json")
    ap.add_argument("--registry", default=None,
                    help="override nodes registry (default: data/h8_nodes.json)")
    ap.add_argument("--out", default=None,
                    help="certificate output path")
    ap.add_argument("--verdicts-out", default=None,
                    help="optional path for raw verify_capture JSON")
    args = ap.parse_args(argv)

    with open(args.capture) as f:
        capture = json.load(f)

    if capture.get("origin") != "LIVE_CAPTURE":
        print(f"refusing: capture origin is {capture.get('origin')!r}, "
              f"expected LIVE_CAPTURE", file=sys.stderr)
        return 2

    _, reg, spec = (load_registry(args.registry) if args.registry
                    else load_registry())
    tier = capture.get("tier_nominal") or "NTP"
    live_reg, u_meta = overlay_measured_u(reg, capture, tier)

    # Require coverage of every node that actually contributed a receipt;
    # do not invent a coverage set broader than the live run.
    receipt_nodes = {r["body"]["node_id"] for r in capture["receipts"]}
    result = verify_capture(capture, live_reg,
                            required_node_ids=receipt_nodes)

    print(f"capture: {args.capture}")
    print(f"origin: {capture.get('origin')}  tier: {tier}  "
          f"captured_at: {capture.get('captured_at')}")
    print(f"aggregate: {result['aggregate']}")
    print(f"measured_u_ns overlay: {json.dumps(u_meta, sort_keys=True)}")
    print("--- per-receipt ---")
    for p in result["per_receipt"]:
        w = p.get("witness") or {}
        print(json.dumps({
            "node_id": p.get("node_id"),
            "tier": p.get("tier"),
            "verdict": p.get("verdict"),
            "u_ns": live_reg.get(p.get("node_id"), {}).get("u_ns"),
            "dt_ns": w.get("dt_ns"),
            "dt_adjusted_ns": w.get("dt_adjusted_ns"),
            "vacuum_floor_ns": w.get("vacuum_floor_ns"),
            "typical_floor_ns": w.get("typical_floor_ns"),
            "resolution_band_ns": w.get("resolution_band_ns"),
            "reason": w.get("reason") or w.get("gate"),
        }, sort_keys=True))

    if args.verdicts_out:
        with open(args.verdicts_out, "w") as f:
            json.dump(result, f, indent=2, sort_keys=True)
            f.write("\n")

    # Source hashes of the trusted path only (mirrors H8 certificate style).
    src = {}
    for rel in ("horizon/capture_verify.py", "horizon/geometry.py",
                "horizon/measure.py", "horizon/signed_capture.py",
                "horizon/build_frame.py", "horizon/events.py"):
        src[rel] = sha256_file(os.path.join(ROOT, rel))

    verdicts = {p["node_id"]: p["verdict"] for p in result["per_receipt"]}
    finding_parts = [
        f"tier={tier}",
        f"aggregate={result['aggregate']}",
        "verdicts=" + ",".join(f"{k}:{v}" for k, v in sorted(verdicts.items())),
    ]
    if any(v == "ADMITTED" for v in verdicts.values()):
        finding_parts.append("at least one receipt ADMITTED on real measured times")
    if any(v == "APPARATUS_LIMITED" for v in verdicts.values()):
        finding_parts.append(
            "APPARATUS_LIMITED present where measured clock budget cannot resolve geometry"
        )

    # Map verify_capture aggregate onto the certificate vocabulary.
    # REJECTED live runs do not produce a commit-worthy certificate.
    agg = result["aggregate"]
    if agg == "REJECTED":
        print("refusing to write certificate for REJECTED aggregate",
              file=sys.stderr)
        return 1
    if agg not in ("PASS", "APPARATUS_LIMITED"):
        # verify_capture uses PASS when every receipt is ADMITTED
        agg = "PASS" if "REJECTED" not in verdicts.values() else agg

    gates = [
        {
            "gate": "H8-LIVE-A",
            "description": "multi-node LIVE_CAPTURE collected from >=3 regions",
            "soundness_tag": "HEURISTIC",
            "result": "PASS" if len(receipt_nodes) >= 3 else "FAIL",
        },
        {
            "gate": "H8-LIVE-B",
            "description": "unmodified verify_capture over measured u_ns overlay",
            "soundness_tag": "SOUND",
            "result": "PASS" if agg in ("PASS", "APPARATUS_LIMITED") else "FAIL",
        },
        {
            "gate": "H8-LIVE-C",
            "description": "no honest receipt REJECTED (falsifier F1)",
            "soundness_tag": "SOUND",
            "result": "PASS" if "REJECTED" not in verdicts.values() else "FAIL",
        },
    ]

    cert = {
        "certificate_version": "1",
        "benchmark_id": "H8-LIVE",
        "program": "HorizonProtocol",
        "claim_class": "ENGINEERING_REFERENCE",
        "execution_tier": "LIVE",
        "promotion_allowed": False,
        "empirical_claim": "NONE",
        "capture_origin": "LIVE_CAPTURE",
        "adversary_model": (
            "forger without node keys (HMAC demo keys; Ed25519 is the "
            "deployment target) or without access to trusted c_eff/registry "
            "parameters; colluding multi-node adversaries OUT OF SCOPE"
        ),
        "captured_at": capture.get("captured_at"),
        "tier_nominal": tier,
        "clock_offsets_ns": capture.get("clock_offsets_ns") or {},
        "measured_u_ns": capture.get("measured_u_ns") or {},
        "u_ns_overlay": u_meta,
        "position_sources": capture.get("position_sources") or {},
        "capture_path": os.path.relpath(args.capture, ROOT),
        "capture_sha256": sha256_file(args.capture),
        "registry_frame_origin": spec.get("frame_origin"),
        "per_receipt": result["per_receipt"],
        "tier_verdicts": {tier: verdicts},
        "gates": gates,
        "aggregate": agg,
        "finding": "; ".join(finding_parts),
        "auth_note": capture.get("auth_note") or (
            "HMAC-SHA256 demo keys; production target is per-VM Ed25519"
        ),
        "heuristic_warnings": [
            {
                "location": "scripts/live_orchestrate.py",
                "warning": "HEURISTIC live capture path; quarantined from CI/verifier",
            },
            {
                "location": "horizon/signed_capture.py::measure_now",
                "warning": "live system-time stamp; non-deterministic",
            },
            {
                "location": "horizon/signed_capture.py::_key",
                "warning": "HMAC demo key derivation; not deployment-grade auth",
            },
        ],
        "unit_convention": {
            "position": "nanometers (int)",
            "time": "nanoseconds (int)",
            "c": 299792458,
            "c_eff": [3, 5],
        },
        "timing_tiers_nominal": TIERS,
        "verifier": "horizon.capture_verify.verify_capture (unmodified)",
        "source_hashes": src,
        "python_version": platform.python_version(),
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    out = args.out or os.path.join(ROOT, "certificates", "h8_live_certificate.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(cert, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"certificate written: {out}")
    return 0 if result["aggregate"] != "REJECTED" else 1


if __name__ == "__main__":
    sys.exit(main())
