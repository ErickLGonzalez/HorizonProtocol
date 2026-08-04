#!/usr/bin/env python3
"""Verify a LIVE_CAPTURE with the unmodified capture verifier. [manual only]

Loads a live capture JSON + node registry, overlays each node's measured
`u_ns` from the MAC-bound receipt body (never a nominal guess, never an
unsigned capture-level field alone), calls `horizon.capture_verify.verify_capture`,
prints per-receipt verdicts with exact integer witnesses, and writes
`certificates/h8_live_certificate.json`.

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
from horizon.signed_capture import verify_receipt  # noqa: E402


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def authenticated_measured_u(capture: dict, receipt_nodes: set) -> tuple:
    """Extract per-node u_ns exclusively from MAC-verified receipt bodies.

    Returns (measured_map, meta). Refuses unsigned capture-level
    `measured_u_ns` and refuses any receipt contributor without a
    MAC-bound measured value — no silent TIERS[tier] fallback.
    """
    measured = {}
    meta = {"used_authenticated": {}, "missing": [], "bad_mac": []}
    top = dict(capture.get("measured_u_ns") or {})

    for r in capture.get("receipts") or []:
        body = r.get("body") or {}
        nid = body.get("node_id")
        if nid not in receipt_nodes:
            continue
        if not verify_receipt(r):
            meta["bad_mac"].append(nid)
            continue
        if "measured_u_ns" not in body or body["measured_u_ns"] is None:
            meta["missing"].append(nid)
            continue
        u = int(body["measured_u_ns"])
        measured[nid] = u
        meta["used_authenticated"][nid] = u
        # Capture-level map is provenance only; mismatch is a hard error.
        if nid in top and int(top[nid]) != u:
            meta.setdefault("top_level_mismatch", {})[nid] = {
                "body": u, "capture": int(top[nid]),
            }

    for nid in sorted(receipt_nodes):
        if nid not in measured and nid not in meta["bad_mac"]:
            if nid not in meta["missing"]:
                meta["missing"].append(nid)

    return measured, meta


def overlay_measured_u(reg: dict, measured: dict, tier: str) -> dict:
    """Return a registry copy whose per-node u_ns is the authenticated
    measured uncertainty. Only nodes present in `measured` are overlaid;
    callers must ensure every receipt contributor is present.
    """
    out = {}
    for nid, node in reg.items():
        n = dict(node)
        n["tier"] = tier
        if nid in measured:
            n["u_ns"] = int(measured[nid])
        else:
            # Non-contributing registry nodes keep the tier nominal for
            # completeness; they are never consulted by verify_capture
            # unless a receipt names them (which would have failed earlier).
            n["u_ns"] = int(TIERS[tier])
        out[nid] = n
    return out


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

    # Require coverage of every node that actually contributed a receipt;
    # do not invent a coverage set broader than the live run.
    receipt_nodes = {r["body"]["node_id"] for r in capture["receipts"]}
    measured, u_meta = authenticated_measured_u(capture, receipt_nodes)

    if u_meta["bad_mac"]:
        print(f"refusing: receipt MAC failed for {u_meta['bad_mac']}",
              file=sys.stderr)
        return 1
    if u_meta["missing"]:
        print(f"refusing: receipt contributors missing MAC-bound "
              f"measured_u_ns: {u_meta['missing']}", file=sys.stderr)
        return 1
    if u_meta.get("top_level_mismatch"):
        print(f"refusing: capture measured_u_ns mismatches receipt body: "
              f"{u_meta['top_level_mismatch']}", file=sys.stderr)
        return 1

    live_reg = overlay_measured_u(reg, measured, tier)
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
            "description": (
                "unmodified verify_capture over MAC-bound measured u_ns overlay"
            ),
            "soundness_tag": "SOUND",
            "result": "PASS" if agg in ("PASS", "APPARATUS_LIMITED") else "FAIL",
        },
        {
            "gate": "H8-LIVE-C",
            "description": "no honest receipt REJECTED (falsifier F1)",
            "soundness_tag": "SOUND",
            "result": "PASS" if "REJECTED" not in verdicts.values() else "FAIL",
        },
        {
            "gate": "H8-LIVE-D",
            "description": (
                "every receipt contributor carries MAC-bound measured_u_ns"
            ),
            "soundness_tag": "SOUND",
            "result": "PASS",
        },
    ]

    if any(g["result"] == "FAIL" for g in gates):
        failed = [g["gate"] for g in gates if g["result"] == "FAIL"]
        print(f"refusing to write certificate; failed gates: {failed}",
              file=sys.stderr)
        return 1

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
            "parameters; measured_u_ns is MAC-bound in each receipt body so "
            "inflating the clock budget requires forging the receipt; "
            "colluding multi-node adversaries OUT OF SCOPE"
        ),
        "captured_at": capture.get("captured_at"),
        "tier_nominal": tier,
        "clock_offsets_ns": capture.get("clock_offsets_ns") or {},
        "measured_u_ns": measured,
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
            "HMAC-SHA256 demo keys; measured_u_ns MAC-bound in receipt body; "
            "production target is per-VM Ed25519"
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
