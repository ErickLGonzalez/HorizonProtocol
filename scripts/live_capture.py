#!/usr/bin/env python3
"""LIVE capture over real nodes.  [HEURISTIC - QUARANTINED, manual only]

Runs on each real node to measure and sign the arrival time of a broadcast
event hash, writing a signed receipt. Aggregating receipts from >=3 real nodes
yields a genuine (non-synthetic) capture the verifier can check. Non-
deterministic; excluded from CI; never imported by the verifier.

This is the on-ramp to a true H8 result: provision 3+ real hosts, run this on
each against a common event hash and a shared clock reference, collect the
signed receipts into a capture JSON, and verify with capture_verify.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from horizon.build_frame import load_registry  # noqa: E402
from horizon.signed_capture import measure_now  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("node_id")
    ap.add_argument("event_hash")
    ap.add_argument("--tier", default="NTP")
    args = ap.parse_args()
    _, reg, _ = load_registry()
    if args.node_id not in reg:
        print(f"unknown node {args.node_id}; known: {list(reg)}")
        return 1
    pos = reg[args.node_id]["pos_nm"]
    receipt = measure_now(args.node_id, pos, args.event_hash, args.tier)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
