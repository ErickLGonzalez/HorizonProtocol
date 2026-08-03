"""Uncertainty-budgeted cone gate over MEASURED timestamps. [SOUND]

H1-H4 certify claims against COMPUTED arrival times (a world-model
simulator). H5 certifies claims against MEASURED arrival times: real
clocks carry a declared uncertainty `U_ns` and real signal paths are not
vacuum straight lines, so a single tight admissibility gate is the wrong
instrument here - it would spuriously reject honest measurements as often
as it would catch forgeries. Instead this module classifies a measured
receipt against TWO exact-integer floors:

  - `min_light_time_ns` (from `horizon.geometry`, unmodified, reused
    exactly): the absolute vacuum-c floor. NOTHING travels faster than
    this, in any medium, ever. A receipt earlier than this floor - even
    after adding the full declared clock uncertainty `U_ns` in the
    prover's favor - is REJECTED: physically impossible, full stop.
  - `min_transit_time_ns_eff` (this module): the floor implied by a
    conservative, declared in-medium speed bound `c_eff = C_NM_PER_NS *
    c_eff_num / c_eff_den` (frozen at 3/5 of c - real fiber typically
    performs at least this well). A receipt at or above this floor is
    ADMITTED: consistent with ordinary, unremarkable real-medium
    performance.

Between the two floors - physically possible (not FTL), but faster than
the conservative real-medium bound accounts for - is exactly the region
this module cannot resolve: APPARATUS_LIMITED, never silently PASS. This
is the honest three-way split; there is no separate arbitrary "margin"
constant, because the gap between a vacuum floor and a slower-medium
floor already IS the unresolvable band, by construction.

(Erratum: an earlier version of this module used `c_eff` - a declared
LOWER bound on real-medium speed - as if it were the fastest anything
could travel, and REJECTED receipts below the `c_eff` floor. Since real
signals can legitimately travel faster than the conservative `c_eff`
bound (up to vacuum c), that inverted the roles of the two speed bounds
and could reject honest measurements. Fixed: vacuum c is the only floor
that can ever justify REJECTED; `c_eff` only ever raises the bar for a
clean ADMITTED.)

No floats anywhere in a classification decision: `min_transit_time_ns_eff`
uses the same exact-integer ceiling search as `geometry.min_light_time_ns`.

Trust boundary: `verify_measured_certificate` takes per-station clock
uncertainty (`node_params`) as a TRUSTED argument from the caller, exactly
as it takes `registry` - never from the certificate itself. A certificate
is untrusted input; if its own claimed uncertainty or speed bound were
used to classify its own receipts, a forger could simply declare an
enormous `U_ns` (or a superluminal `c_eff`) and turn an otherwise
impossibly-early receipt into ADMITTED. `node_params` must come from the
same pre-declared, trusted source as the station registry (see
`horizon.fixtures.NODE_U_NS`).

This module is on the trusted path: it never imports `horizon.capture`,
`horizon.fixtures`, or any world-model module; test H5-B asserts this by
source inspection. What it certifies is (a) receipt authenticity and
event/position binding (reusing H1's station/receipt machinery exactly),
and (b) that the measured arrival is consistent with a real, non-vacuum
signal path under a declared, TRUSTED uncertainty budget. It does NOT
certify that any capture was actually performed live, or that a
"SYNTHETIC_CONSISTENT" fixture is a real measurement (see docs/h5-spec.md,
"Claim-scope firewall").
"""
import math

from .geometry import C_NM_PER_NS, dist2, min_light_time_ns

# ---- frozen parameters (H5) -------------------------------------------------
C_EFF_NUM = 3                       # c_eff = c * C_EFF_NUM / C_EFF_DEN
C_EFF_DEN = 5                       # 3/5 of vacuum c: conservative fiber lower bound


def min_transit_time_ns_eff(p1, p2, c_eff_num: int = C_EFF_NUM,
                            c_eff_den: int = C_EFF_DEN) -> int:
    """Smallest integer dt (ns) with (dt * C_NM_PER_NS * num)^2 >= den^2 * dist2.

    Exact integer analogue of `geometry.min_light_time_ns`, but for the
    slower effective in-medium speed `c_eff = C_NM_PER_NS * num/den`
    instead of vacuum c. Equivalently: ceil(dist(p1,p2) / c_eff). Always
    >= `min_light_time_ns(p1,p2)` since c_eff <= vacuum c.
    """
    d2 = dist2(p1, p2)
    if d2 == 0:
        return 0
    rhs = (c_eff_den * c_eff_den) * d2
    denom = C_NM_PER_NS * c_eff_num
    r = math.isqrt(rhs)
    if r * r < rhs:
        r += 1                      # r = ceil(sqrt(rhs))
    dt = -(-r // denom)             # ceil(r / denom)
    while dt > 0 and (denom * (dt - 1)) ** 2 >= rhs:
        dt -= 1
    while (denom * dt) ** 2 < rhs:
        dt += 1
    return dt


def budget_witness(t0_ns: int, p0, t_recv_ns: int, station_pos_nm, u_ns: int,
                   c_eff_num: int = C_EFF_NUM, c_eff_den: int = C_EFF_DEN) -> dict:
    """Exact integer witness classifying one measured receipt against both
    floors. `dt_adjusted_ns` adds the full declared clock uncertainty
    `u_ns` in the prover's favor before comparing against either floor.
    """
    raw_dt_ns = t_recv_ns - t0_ns
    dt_adjusted_ns = raw_dt_ns + u_ns
    vacuum_floor_ns = min_light_time_ns(p0, station_pos_nm)
    typical_floor_ns = min_transit_time_ns_eff(p0, station_pos_nm,
                                               c_eff_num, c_eff_den)

    if dt_adjusted_ns < vacuum_floor_ns:
        verdict = "REJECTED"
    elif dt_adjusted_ns < typical_floor_ns:
        verdict = "APPARATUS_LIMITED"
    else:
        verdict = "ADMITTED"

    return {
        "t0_ns": int(t0_ns), "t_recv_ns": int(t_recv_ns), "u_ns": int(u_ns),
        "raw_dt_ns": raw_dt_ns, "dt_adjusted_ns": dt_adjusted_ns,
        "c_eff_num": int(c_eff_num), "c_eff_den": int(c_eff_den),
        "vacuum_floor_ns": vacuum_floor_ns, "typical_floor_ns": typical_floor_ns,
        "margin_below_vacuum_floor_ns": vacuum_floor_ns - dt_adjusted_ns,
        "margin_below_typical_floor_ns": typical_floor_ns - dt_adjusted_ns,
        "verdict": verdict,
    }


def classify_measured_receipt(t0_ns: int, p0, t_recv_ns: int, station_pos_nm,
                              u_ns: int, c_eff_num: int = C_EFF_NUM,
                              c_eff_den: int = C_EFF_DEN) -> dict:
    """`{"verdict": ADMITTED|REJECTED|APPARATUS_LIMITED, "witness": {...}}`."""
    w = budget_witness(t0_ns, p0, t_recv_ns, station_pos_nm, u_ns,
                       c_eff_num, c_eff_den)
    return {"verdict": w["verdict"], "witness": w}


# ---- standalone verifier ----------------------------------------------------
def verify_measured_certificate(cert: dict, registry: dict, node_params: dict,
                                required_station_ids=None) -> dict:
    """Independently re-verify a measured cone certificate. Gates, in order:
    nonempty_receipts -> distinct_sources -> station_coverage (only if
    `required_station_ids` is given) -> per receipt (known_station ->
    receipt_mac -> payload_binding -> surveyed_position -> budget). Then,
    only for a certificate declaring `fixture_origin: LIVE_CAPTURE`, a
    self-consistency check that no receipt's raw elapsed time is negative.

    `node_params` (`{station_id: {"u_ns": int, "c_eff_num": int (optional),
    "c_eff_den": int (optional)}}`) is TRUSTED CALLER INPUT, exactly like
    `registry` - it is never read from `cert`. A certificate has no field
    for it: nothing in the untrusted input can override the declared
    per-station uncertainty or speed bound.

    `distinct_sources` rejects a certificate that repeats the same
    station_id across multiple receipts - without it, a single valid
    signed receipt could be duplicated to pad a certificate's apparent
    node count while still returning PASS. `required_station_ids`, when
    given (a caller-supplied set/iterable of station ids that MUST all be
    represented - e.g. every station in a multi-node registry a
    certificate claims to corroborate), rejects a certificate missing any
    of them; when omitted (as for a single-emitter H1/H5-style
    certificate, where nothing requires universal station coverage), no
    coverage check is performed.

    Aggregate verdict: REJECTED if any receipt fails a binding gate or is
    classified REJECTED (propagating the exact witness); else
    APPARATUS_LIMITED if any receipt is APPARATUS_LIMITED or the
    live-capture self-check fails (refuse to certify PASS on a marginal
    or unresolved measurement); else PASS.
    """
    event = cert["event"]
    t0 = event["claimed_emit_time_ns"]
    p0 = tuple(event["claimed_emit_pos_nm"])
    receipts = cert.get("receipts", [])
    if not receipts:
        return {"verdict": "REJECTED",
                "witness": {"gate": "nonempty_receipts"}, "per_node": {}}

    station_ids = [r["body"]["station_id"] for r in receipts]
    if len(set(station_ids)) != len(station_ids):
        return {"verdict": "REJECTED",
                "witness": {"gate": "distinct_sources",
                            "station_ids": station_ids},
                "per_node": {}}

    if required_station_ids is not None:
        required = set(required_station_ids)
        got = set(station_ids)
        if got != required:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "station_coverage",
                                "missing": sorted(required - got),
                                "unexpected": sorted(got - required)},
                    "per_node": {}}

    per_node = {}
    apparatus_limited_nodes = []

    for r in receipts:
        body = r["body"]
        sid = body["station_id"]
        st = registry.get(sid)
        if st is None:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "known_station", "station_id": sid},
                    "per_node": per_node}
        if not st.verify_receipt(r):
            return {"verdict": "REJECTED",
                    "witness": {"gate": "receipt_mac", "station_id": sid,
                                "detail": "HMAC verification failed"},
                    "per_node": per_node}
        if body["payload_hash"] != event["payload_hash"]:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "payload_binding", "station_id": sid},
                    "per_node": per_node}
        if tuple(body["station_pos_nm"]) != st.pos_nm:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "surveyed_position", "station_id": sid},
                    "per_node": per_node}

        params = node_params[sid]
        u_ns = params["u_ns"]
        c_num = params.get("c_eff_num", C_EFF_NUM)
        c_den = params.get("c_eff_den", C_EFF_DEN)
        w = budget_witness(t0, p0, body["recv_time_ns"], st.pos_nm, u_ns,
                           c_num, c_den)
        per_node[sid] = w
        if w["verdict"] == "REJECTED":
            return {"verdict": "REJECTED",
                    "witness": {"gate": "budget", "station_id": sid,
                                "exact_witness": w,
                                "detail": "receipt earlier than the absolute "
                                          "vacuum-c floor, even with the full "
                                          "clock-uncertainty benefit of the "
                                          "doubt: physically impossible"},
                    "per_node": per_node}
        if w["verdict"] == "APPARATUS_LIMITED":
            apparatus_limited_nodes.append(sid)

    if cert.get("fixture_origin") == "LIVE_CAPTURE":
        for r in receipts:
            body = r["body"]
            if body["recv_time_ns"] - t0 < 0:
                return {"verdict": "APPARATUS_LIMITED",
                        "witness": {"gate": "live_capture_self_check",
                                    "station_id": body["station_id"],
                                    "detail": "negative raw elapsed time in a "
                                              "live capture indicates "
                                              "unresolved clock skew, not a "
                                              "consistent slow path"},
                        "per_node": per_node}

    if apparatus_limited_nodes:
        return {"verdict": "APPARATUS_LIMITED",
                "witness": {"gate": "budget",
                            "apparatus_limited_nodes": apparatus_limited_nodes,
                            "detail": "measurement is physically possible but "
                                      "faster than the conservative real-medium "
                                      "bound accounts for; cannot certify as "
                                      "ordinary real-world performance"},
                "per_node": per_node}

    return {"verdict": "PASS", "per_node": per_node}
