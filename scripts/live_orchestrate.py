#!/usr/bin/env python3
"""Multi-node LIVE capture orchestrator.  [HEURISTIC - QUARANTINED, manual only]

Coordinates an emitter + responders over a stdlib TCP channel so each node
stamps a signed receipt with real `time.time_ns()`. Aggregating >=3 receipts
from geographically separated hosts yields a genuine LIVE_CAPTURE the
unmodified verifier can check.

Never imported by the verifier or by CI. Stdlib only.

Protocol (one TCP connection per responder):
  emitter -> responder: {"cmd":"CAPTURE","event_hash":...,"payload_hash":...,
                         "t0_ns":...,"p0_nm":...,"tier":...,"run":...}
  responder -> emitter: {"cmd":"RECEIPT","receipt":{...},
                         "clock":{...},"rtt_hint_ns":...}

Also supports a local `--role both` loopback mode for plumbing checks; that
mode must never be labeled LIVE_CAPTURE (it is not multi-region).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from horizon.build_frame import load_registry  # noqa: E402
from horizon.capture_verify import bound_event_hash  # noqa: E402
from horizon.events import event_hash  # noqa: E402
from horizon.signed_capture import measure_now  # noqa: E402

DEFAULT_PORT = 9753
RECV_TIMEOUT_S = 30


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def read_chrony_tracking() -> dict:
    """Parse `chronyc tracking` into measured clock fields. Stdlib only."""
    out = {
        "available": False,
        "raw": "",
        "ref_id": None,
        "stratum": None,
        "system_time_offset_s": None,
        "last_offset_s": None,
        "rms_offset_s": None,
        "root_delay_s": None,
        "root_dispersion_s": None,
        "update_interval_s": None,
        "leap_status": None,
        "measured_offset_ns": None,
        "measured_u_ns": None,
        "ptp_device_present": os.path.exists("/dev/ptp_hyperv")
        or os.path.exists("/dev/ptp0"),
    }
    try:
        p = subprocess.run(
            ["chronyc", "tracking"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        raw = (p.stdout or "") + (p.stderr or "")
        out["raw"] = raw.strip()
        if p.returncode != 0 or not p.stdout:
            return out
        out["available"] = True
        fields = {}
        for line in p.stdout.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()

        def _first_float(s):
            # chronyc values look like "0.000000435 seconds slow of NTP time"
            tok = s.split()[0]
            return float(tok)

        if "Reference ID" in fields:
            out["ref_id"] = fields["Reference ID"]
        if "Stratum" in fields:
            out["stratum"] = int(fields["Stratum"].split()[0])
        if "System time" in fields:
            out["system_time_offset_s"] = _first_float(fields["System time"])
        if "Last offset" in fields:
            out["last_offset_s"] = _first_float(fields["Last offset"])
        if "RMS offset" in fields:
            out["rms_offset_s"] = _first_float(fields["RMS offset"])
        if "Root delay" in fields:
            out["root_delay_s"] = _first_float(fields["Root delay"])
        if "Root dispersion" in fields:
            out["root_dispersion_s"] = _first_float(fields["Root dispersion"])
        if "Update interval" in fields:
            out["update_interval_s"] = _first_float(fields["Update interval"])
        if "Leap status" in fields:
            out["leap_status"] = fields["Leap status"]

        # Measured offset: prefer last_offset; fall back to system_time.
        off = out["last_offset_s"]
        if off is None:
            off = out["system_time_offset_s"]
        if off is not None:
            out["measured_offset_ns"] = int(round(off * 1e9))

        # Measured uncertainty budget: root_dispersion + rms_offset
        # (conservative; never smaller than |last_offset|).
        parts = []
        for key in ("root_dispersion_s", "rms_offset_s", "root_delay_s"):
            if out[key] is not None:
                parts.append(abs(out[key]))
        if off is not None:
            parts.append(abs(off))
        if parts:
            u_s = sum(parts)
            # Floor at 1 us so a perfect-looking chrony reading still
            # declares a non-zero budget rather than pretending zero error.
            out["measured_u_ns"] = max(1_000, int(round(u_s * 1e9)))
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError) as e:
        out["error"] = str(e)
    return out


def _recv_json_line(conn: socket.socket) -> dict:
    buf = b""
    while b"\n" not in buf:
        chunk = conn.recv(65536)
        if not chunk:
            raise ConnectionError("peer closed before complete JSON line")
        buf += chunk
        if len(buf) > 8_000_000:
            raise ValueError("oversized message")
    line, _rest = buf.split(b"\n", 1)
    return json.loads(line.decode("utf-8"))


def _send_json_line(conn: socket.socket, obj: dict) -> None:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    conn.sendall(data)


def run_responder(node_id: str, port: int, registry_path: str | None) -> int:
    _, reg, _ = load_registry(registry_path) if registry_path else load_registry()
    if node_id not in reg:
        print(f"unknown node {node_id}; known={list(reg)}", file=sys.stderr)
        return 1
    pos = reg[node_id]["pos_nm"]
    clock_before = read_chrony_tracking()
    print(json.dumps({
        "role": "responder", "node_id": node_id,
        "listening_port": port,
        "clock_before": {k: clock_before[k] for k in
                         ("available", "ref_id", "stratum", "measured_offset_ns",
                          "measured_u_ns", "ptp_device_present")},
    }, sort_keys=True))

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(8)
    print(f"responder {node_id} listening on 0.0.0.0:{port}", flush=True)

    while True:
        conn, addr = srv.accept()
        with conn:
            conn.settimeout(RECV_TIMEOUT_S)
            try:
                msg = _recv_json_line(conn)
            except (OSError, ValueError, json.JSONDecodeError) as e:
                print(f"bad request from {addr}: {e}", flush=True)
                continue
            if msg.get("cmd") != "CAPTURE":
                _send_json_line(conn, {"cmd": "ERROR", "error": "expected CAPTURE"})
                continue
            ehash = msg["event_hash"]
            tier = msg.get("tier", "NTP")
            clock_pre = read_chrony_tracking()
            t_net_in = time.time_ns()
            receipt = measure_now(node_id, pos, ehash, tier)
            clock_post = read_chrony_tracking()
            _send_json_line(conn, {
                "cmd": "RECEIPT",
                "receipt": receipt,
                "clock_before": clock_pre,
                "clock_after": clock_post,
                "net_in_ns": t_net_in,
                "peer": list(addr),
            })
            print(json.dumps({
                "served": True, "peer": list(addr),
                "recv_time_ns": receipt["body"]["recv_time_ns"],
                "measured_u_ns": clock_post.get("measured_u_ns"),
            }, sort_keys=True), flush=True)


def _query_responder(host: str, port: int, msg: dict, timeout_s: float) -> dict:
    t0 = time.time_ns()
    with socket.create_connection((host, port), timeout=timeout_s) as conn:
        conn.settimeout(timeout_s)
        _send_json_line(conn, msg)
        resp = _recv_json_line(conn)
    t1 = time.time_ns()
    resp["rtt_ns"] = t1 - t0
    return resp


def run_emitter(args) -> int:
    path = args.registry if args.registry else None
    frame, reg, spec = load_registry(path) if path else load_registry()
    emit_id = args.emitter_id
    if emit_id not in reg:
        print(f"unknown emitter {emit_id}", file=sys.stderr)
        return 1

    responders = []
    for item in args.responders:
        # node_id:host[:port]
        if ":" not in item:
            print(f"bad --responders entry {item!r}; want node_id:host[:port]",
                  file=sys.stderr)
            return 1
        parts = item.split(":")
        nid, host = parts[0], parts[1]
        port = int(parts[2]) if len(parts) > 2 else args.port
        if nid not in reg:
            print(f"unknown responder node {nid}", file=sys.stderr)
            return 1
        responders.append((nid, host, port))

    # Include emitter as its own local responder (same process stamp).
    include_self = not args.no_self_receipt

    payload = {
        "experiment": "H8-LIVE",
        "run": int(args.run),
        "nonce": secrets.token_hex(16),
        "emitter": emit_id,
        "tier_nominal": args.tier,
    }
    payload_hash = event_hash(payload)
    p0_nm = list(reg[emit_id]["pos_nm"])

    clock_pre = {emit_id: read_chrony_tracking()}
    # Emission instant: bind t0 into the claim hash BEFORE broadcast so
    # every receipt signs the same (payload_hash, t0_ns, p0_nm) claim.
    t0_ns = time.time_ns()
    claim_hash = bound_event_hash(payload_hash, t0_ns, p0_nm)

    capture_msg = {
        "cmd": "CAPTURE",
        "event_hash": claim_hash,
        "payload_hash": payload_hash,
        "t0_ns": t0_ns,
        "p0_nm": p0_nm,
        "tier": args.tier,
        "run": int(args.run),
    }

    receipts = []
    clock_offsets_ns = {}
    measured_u_ns = {}
    rtts_ns = {}
    clock_logs = {}
    errors = []

    if include_self:
        self_clock_pre = read_chrony_tracking()
        self_receipt = measure_now(emit_id, p0_nm, claim_hash, args.tier)
        self_clock_post = read_chrony_tracking()
        receipts.append(self_receipt)
        clock_logs[emit_id] = {"before": self_clock_pre, "after": self_clock_post}
        if self_clock_post.get("measured_offset_ns") is not None:
            clock_offsets_ns[emit_id] = self_clock_post["measured_offset_ns"]
        if self_clock_post.get("measured_u_ns") is not None:
            measured_u_ns[emit_id] = self_clock_post["measured_u_ns"]
        rtts_ns[emit_id] = 0

    lock = threading.Lock()

    def _one(nid, host, port):
        try:
            resp = _query_responder(host, port, capture_msg, float(args.timeout))
            if resp.get("cmd") != "RECEIPT":
                with lock:
                    errors.append({"node_id": nid, "error": resp})
                return
            with lock:
                receipts.append(resp["receipt"])
                rtts_ns[nid] = resp.get("rtt_ns")
                clock_logs[nid] = {
                    "before": resp.get("clock_before"),
                    "after": resp.get("clock_after"),
                }
                after = resp.get("clock_after") or {}
                if after.get("measured_offset_ns") is not None:
                    clock_offsets_ns[nid] = after["measured_offset_ns"]
                if after.get("measured_u_ns") is not None:
                    measured_u_ns[nid] = after["measured_u_ns"]
        except (OSError, ValueError, json.JSONDecodeError) as e:
            with lock:
                errors.append({"node_id": nid, "error": str(e)})

    threads = [threading.Thread(target=_one, args=r) for r in responders]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    clock_post = {emit_id: read_chrony_tracking()}

    # Position source metadata from registry spec if present.
    pos_sources = {}
    for n in spec.get("nodes", []):
        if "position_source" in n:
            pos_sources[n["id"]] = n["position_source"]

    captured_at = _utc_now_iso()
    capture = {
        "origin": "LIVE_CAPTURE",
        "captured_at": captured_at,
        "experiment": "H8-LIVE",
        "run": int(args.run),
        "payload": payload,
        "payload_hash": payload_hash,
        "event_hash": claim_hash,
        "t0_ns": t0_ns,
        "p0_nm": p0_nm,
        "emitter_id": emit_id,
        "c_eff": [3, 5],
        "route_excess_note": (
            "measured RTTs recorded separately; c_eff accounts for medium"
        ),
        "tier_nominal": args.tier,
        "clock_offsets_ns": clock_offsets_ns,
        "measured_u_ns": measured_u_ns,
        "rtts_ns": rtts_ns,
        "position_sources": pos_sources,
        "clock_logs": clock_logs,
        "emitter_clock": {"before": clock_pre[emit_id], "after": clock_post[emit_id]},
        "receipts": receipts,
        "errors": errors,
        "auth_note": (
            "Receipts signed with HMAC-SHA256 demo keys derived from node_id "
            "(horizon.signed_capture). Production target: per-VM Ed25519 keys."
        ),
    }

    out_name = f"h8_live_capture_{args.tier}_{args.run}.json"
    out_path = args.output or os.path.join(ROOT, "data", out_name)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(capture, f, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps({
        "wrote": out_path,
        "origin": "LIVE_CAPTURE",
        "tier_nominal": args.tier,
        "t0_ns": t0_ns,
        "payload_hash": payload_hash,
        "event_hash": claim_hash,
        "n_receipts": len(receipts),
        "nodes": [r["body"]["node_id"] for r in receipts],
        "errors": errors,
        "measured_u_ns": measured_u_ns,
        "clock_offsets_ns": clock_offsets_ns,
    }, indent=2, sort_keys=True))
    return 0 if receipts and not errors else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role", choices=("emitter", "responder"), required=True)
    ap.add_argument("--node-id", help="responder node id (registry key)")
    ap.add_argument("--emitter-id", default="us-east-1")
    ap.add_argument("--responders", nargs="*", default=[],
                    help="node_id:host[:port] entries")
    ap.add_argument("--tier", default="NTP", choices=("NTP", "PTP", "GNSS"))
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--registry", default=None,
                    help="override path to nodes registry JSON")
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-self-receipt", action="store_true",
                    help="do not stamp a local emitter receipt")
    args = ap.parse_args(argv)

    if args.role == "responder":
        if not args.node_id:
            ap.error("--node-id required for responder")
        return run_responder(args.node_id, args.port, args.registry)
    return run_emitter(args)


if __name__ == "__main__":
    sys.exit(main())
