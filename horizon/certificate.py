"""Cone certificates: construction and independent re-verification.

A cone certificate for an event E = (payload_hash, claimed emission
time/position) is a set of signed station receipts plus exact integer
witnesses that every receipt is consistent with the light cone of the
claimed emission event.

Verdicts follow data:
  PASS      - all receipts authentic, all cone gates hold
  REJECTED  - with an explicit witness naming the violated gate
The verifier `verify_certificate` uses ONLY the certificate contents plus
the public station registry (positions + verification keys): a third party
can re-check every gate without re-running the emitter. (A7 discipline.)
"""
from .geometry import causally_admissible, admissibility_witness
from .stations import Station


def build_cone_certificate(event: dict, receipts: list) -> dict:
    return {
        "type": "cone_certificate",
        "version": "1",
        "event": event,
        "receipts": receipts,
    }


def verify_certificate(cert: dict, registry: dict) -> dict:
    """Independently verify a cone certificate. Returns a verdict dict."""
    event = cert["event"]
    t0 = event["claimed_emit_time_ns"]
    p0 = tuple(event["claimed_emit_pos_nm"])
    checks = []
    verdict = "PASS"
    witness = None

    if not cert.get("receipts"):
        return {"verdict": "REJECTED", "witness": {"gate": "nonempty_receipts",
                "detail": "certificate contains no receipts"}, "checks": []}

    for r in cert["receipts"]:
        body = r["body"]
        sid = body["station_id"]
        st = registry.get(sid)
        # Gate 1: known station
        if st is None:
            verdict, witness = "REJECTED", {"gate": "known_station", "station_id": sid}
            checks.append({"station_id": sid, "gate": "known_station", "ok": False})
            break
        # Gate 2: authentic signature
        if not st.verify_receipt(r):
            verdict, witness = "REJECTED", {"gate": "receipt_mac", "station_id": sid,
                                            "detail": "HMAC verification failed"}
            checks.append({"station_id": sid, "gate": "receipt_mac", "ok": False})
            break
        # Gate 3: receipt binds this event
        if body["payload_hash"] != event["payload_hash"]:
            verdict, witness = "REJECTED", {"gate": "payload_binding", "station_id": sid}
            checks.append({"station_id": sid, "gate": "payload_binding", "ok": False})
            break
        # Gate 4: surveyed position matches registry
        if tuple(body["station_pos_nm"]) != st.pos_nm:
            verdict, witness = "REJECTED", {"gate": "surveyed_position", "station_id": sid}
            checks.append({"station_id": sid, "gate": "surveyed_position", "ok": False})
            break
        # Gate 5: light-cone gate (exact integers)
        w = admissibility_witness(t0, p0, body["recv_time_ns"], st.pos_nm)
        checks.append({"station_id": sid, "gate": "light_cone", "ok": w["admissible"],
                       "witness": w})
        if not w["admissible"]:
            verdict, witness = "REJECTED", {"gate": "light_cone", "station_id": sid,
                                            "exact_witness": w,
                "detail": "receipt arrives earlier than light permits from claimed emission"}
            break

    result = {"verdict": verdict, "checks": checks}
    if witness is not None:
        result["witness"] = witness
    if verdict == "PASS":
        # Emission-time upper bound implied by the receipts.
        result["emit_time_upper_bound_ns"] = min(
            r["body"]["recv_time_ns"] for r in cert["receipts"])
    return result
