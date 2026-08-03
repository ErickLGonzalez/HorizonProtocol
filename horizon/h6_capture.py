"""Optional LIVE capture helper for the H6 real-geography node set.
[HEURISTIC - QUARANTINED]

LOCATED WARNING: live measurement; NOT part of the trusted path; excluded
from CI; results are non-deterministic and unauthenticated. No verifier
and no test may import this module (test H6-B asserts the verifier does
not). It reads public NTP time only, performs no authenticated or
side-effectful writes, uses no credentials, and posts nothing.

Reuses `horizon.capture.query_ntp_offset_ns` (the H5 SNTP client-mode
query, already reviewed) rather than re-implementing NTP parsing - this
module only adapts the output shape to H6's per-node registry and picks
a public NTP host as a stand-in reference per declared node.

Usage (manual only):
    python3 -m horizon.h6_capture   # writes data/h6_live_candidate.json

The candidate this writes is NOT a `measured_cone_certificate` and is not
wired into any verifier or gate. A human must review it and hand-adapt it
into a new fixture, labelling it `"fixture_origin": "LIVE_CAPTURE"` with
the capture's ISO timestamp, before it is ever committed or used.
"""
import json
import os
import time

from .capture import query_ntp_offset_ns

# One public NTP reference per declared H6 node, as a real-world stand-in
# for that node's clock (this module has no way to query the node itself).
_NODE_NTP_HOSTS = {
    "us-east-1": "time.cloudflare.com",
    "us-west-2": "time.google.com",
    "eu-west-1": "pool.ntp.org",
    "ap-southeast-1": "time.cloudflare.com",
}


def capture(out_path: str = None) -> tuple:
    measurements = [
        {"node_id": nid, **query_ntp_offset_ns(host)}
        for nid, host in sorted(_NODE_NTP_HOSTS.items())
    ]
    candidate = {
        "fixture_origin": "LIVE_CAPTURE",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "warning": ("unauthenticated live measurement against public NTP "
                   "stand-ins, not the nodes themselves; not for trusted "
                   "use without review"),
        "measurements": measurements,
    }
    if out_path is None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_path = os.path.join(root, "data", "h6_live_candidate.json")
    with open(out_path, "w") as f:
        json.dump(candidate, f, indent=2, sort_keys=True)
    return candidate, out_path


if __name__ == "__main__":
    c, p = capture()
    print("wrote", p)
    for m in c["measurements"]:
        print(" ", m["node_id"], m.get("offset_ns"), m.get("rtt_ns"), m["verdict"])
