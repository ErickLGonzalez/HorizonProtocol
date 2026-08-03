"""Optional LIVE measurement capture. [HEURISTIC - located warning]

Located warning: this is best-effort LIVE measurement over the public
internet - NOT part of the trusted path, EXCLUDED from CI, and its
results are non-deterministic and unauthenticated (a public NTP/HTTP
server is trusted for a timestamp; nothing here is signed by the node
whose clock is queried). It is meant to be run manually, once, to produce
a candidate fixture file for a human to inspect and, if judged reasonable,
commit as a new `data/h5_fixture_*.json` (re-labelled `LIVE_CAPTURE`).

Quarantine, enforced structurally:
  - never imported by `horizon/measure.py`, `horizon/fixtures.py`, any
    `scripts/run_h*.py`, or any file under `tests/` - test H5-B asserts
    this by source inspection across the package;
  - performs no side-effectful network writes: it only reads public NTP
    time and HTTP `Date` response headers, and only ever WRITES a local
    candidate fixture file when explicitly invoked with an output path;
  - never runs as part of `scripts/run_all.py` or any CI workflow.

Stdlib only: `socket` for a minimal SNTP client-mode query (RFC 5905),
`http.client` for `Date` headers, both read-only network operations.
"""
import calendar
import http.client
import socket
import struct
import time

_NTP_EPOCH_OFFSET = 2_208_988_800  # seconds between 1900-01-01 and 1970-01-01
_NTP_PORT = 123
_NTP_PACKET_FORMAT = "!12I"


def query_ntp_offset_ns(host: str, timeout_s: float = 2.0) -> dict:
    """Best-effort SNTP client-mode query. Returns local-vs-server clock
    offset in nanoseconds, or an error detail - never raises to the caller.
    """
    try:
        packet = bytearray(48)
        packet[0] = 0x1B  # LI=0, VN=3, Mode=3 (client)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout_s)
            t_send = time.time()
            sock.sendto(bytes(packet), (host, _NTP_PORT))
            data, _ = sock.recvfrom(48)
            t_recv = time.time()
        unpacked = struct.unpack(_NTP_PACKET_FORMAT, data)
        server_secs = unpacked[10] - _NTP_EPOCH_OFFSET
        server_frac = unpacked[11] / (2 ** 32)
        server_time = server_secs + server_frac
        local_mid = (t_send + t_recv) / 2.0
        offset_ns = int(round((server_time - local_mid) * 1e9))
        rtt_ns = int(round((t_recv - t_send) * 1e9))
        return {"host": host, "offset_ns": offset_ns, "rtt_ns": rtt_ns,
                "verdict": "OK"}
    except OSError as exc:
        return {"host": host, "verdict": "UNREACHABLE", "detail": str(exc)}


def query_http_date_ns(host: str, path: str = "/", timeout_s: float = 3.0) -> dict:
    """Best-effort read of an HTTPS `Date` response header (second
    resolution only - a coarse cross-check, not a primary source).
    """
    try:
        t_send_ns = time.time_ns()
        conn = http.client.HTTPSConnection(host, timeout=timeout_s)
        conn.request("HEAD", path)
        resp = conn.getresponse()
        t_recv_ns = time.time_ns()
        date_hdr = resp.getheader("Date")
        conn.close()
        if date_hdr is None:
            return {"host": host, "verdict": "NO_DATE_HEADER"}
        # HTTP Date headers are always GMT; calendar.timegm (unlike
        # time.mktime) interprets the parsed tuple as UTC, so this is not
        # shifted by the local machine's timezone offset.
        server_epoch_s = calendar.timegm(time.strptime(date_hdr,
                                                       "%a, %d %b %Y %H:%M:%S %Z"))
        return {"host": host, "date_header": date_hdr,
                "server_time_ns": int(server_epoch_s * 1e9),
                "request_sent_ns": t_send_ns, "response_recv_ns": t_recv_ns,
                "verdict": "OK"}
    except (OSError, ValueError) as exc:
        return {"host": host, "verdict": "UNREACHABLE", "detail": str(exc)}


def capture_candidate_fixture(ntp_hosts: list, http_hosts: list) -> dict:
    """Best-effort candidate fixture: NOT a measured_cone_certificate, and
    NOT wired into any verifier - a human must review and hand-adapt this
    into a fixture before it is ever committed, and must label it
    `LIVE_CAPTURE` with the capture's ISO timestamp when they do.
    """
    return {
        "type": "h5_live_capture_candidate",
        "warning": ("live measurement; not part of the trusted path; "
                   "excluded from CI; results non-deterministic and "
                   "unauthenticated"),
        "captured_at_unix_ns": time.time_ns(),
        "ntp": [query_ntp_offset_ns(h) for h in ntp_hosts],
        "http_date": [query_http_date_ns(h) for h in http_hosts],
    }


if __name__ == "__main__":
    import json
    import sys
    result = capture_candidate_fixture(
        ntp_hosts=["time.cloudflare.com", "time.google.com"],
        http_hosts=["www.cloudflare.com"])
    json.dump(result, sys.stdout, indent=2)
    print()
