"""Uncertainty-budgeted cone gate over MEASURED timestamps. [SOUND]

H1-H4 certify claims against COMPUTED arrival times (a world-model
simulator). H5 certifies claims against MEASURED arrival times: real
clocks carry a declared uncertainty `U_ns` and real signal paths are not
vacuum straight lines, so the tight vacuum-c admissibility gate from
`horizon.geometry` is the wrong instrument here - it would spuriously
reject honest measurements as often as it would catch forgeries.

Instead this module widens the gate by an explicitly declared,
certificate-recorded uncertainty budget: a conservative in-medium speed
bound `c_eff = C_NM_PER_NS * c_eff_num / c_eff_den` (frozen at 3/5 of c,
a fiber lower bound) and a per-station clock uncertainty `U_ns`, both
integers, both recorded. A receipt is classified by how its measured
elapsed time compares to the minimal transit time `c_eff` would require:

  - comfortably at or above that requirement (margin > RESOLVE_MARGIN_NS):
    ADMITTED
  - comfortably below it (margin < -RESOLVE_MARGIN_NS): REJECTED - the
    receipt is impossibly early even at the slow in-medium bound and with
    the full clock-uncertainty benefit of the doubt
  - within RESOLVE_MARGIN_NS of the boundary: APPARATUS_LIMITED - the
    measurement cannot resolve admissible from rejected given the
    declared uncertainty. Never silently PASS a marginal measurement.

No floats anywhere in a classification decision: `min_transit_time_ns_eff`
uses the same exact-integer ceiling search as `geometry.min_light_time_ns`.

This module is on the trusted path: it never imports `horizon.capture`,
`horizon.fixtures`, or any world-model module; test H5-B asserts this by
source inspection. What it certifies is (a) receipt authenticity and
event/position binding (reusing H1's station/receipt machinery exactly),
and (b) that the measured arrival is consistent with a real, non-vacuum
signal path under a declared uncertainty budget. It does NOT certify that
any capture was actually performed live, or that a "SYNTHETIC_CONSISTENT"
fixture is a real measurement (see docs/h5-spec.md, "Claim-scope
firewall").
"""
import math

from .geometry import C_NM_PER_NS, dist2

# ---- frozen parameters (H5) -------------------------------------------------
C_EFF_NUM = 3                       # c_eff = c * C_EFF_NUM / C_EFF_DEN
C_EFF_DEN = 5                       # 3/5 of vacuum c: conservative fiber lower bound
RESOLVE_MARGIN_NS = 20_000          # 20 us: band where ADMIT vs REJECT can't be resolved


def min_transit_time_ns_eff(p1, p2, c_eff_num: int = C_EFF_NUM,
                            c_eff_den: int = C_EFF_DEN) -> int:
    """Smallest integer dt (ns) with (dt * C_NM_PER_NS * num)^2 >= den^2 * dist2.

    Exact integer analogue of `geometry.min_light_time_ns`, but for the
    slower effective in-medium speed `c_eff = C_NM_PER_NS * num/den`
    instead of vacuum c. Equivalently: ceil(dist(p1,p2) / c_eff).
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
                   c_eff_num: int = C_EFF_NUM, c_eff_den: int = C_EFF_DEN,
                   resolve_margin_ns: int = RESOLVE_MARGIN_NS) -> dict:
    """Exact integer witness classifying one measured receipt.

    `raw_dt_ns` is the measured elapsed time; `dt_adjusted_ns` adds the
    full declared clock uncertainty `u_ns` in the prover's favor before
    comparing against the in-medium transit-time floor. `margin_ns` is
    signed distance from that floor, in nanoseconds: positive means
    comfortably admissible, negative means comfortably impossible: the
    RESOLVE_MARGIN_NS band around zero is where neither can be concluded.
    """
    raw_dt_ns = t_recv_ns - t0_ns
    dt_adjusted_ns = raw_dt_ns + u_ns
    required_dt_eff_ns = min_transit_time_ns_eff(p0, station_pos_nm,
                                                 c_eff_num, c_eff_den)
    margin_ns = dt_adjusted_ns - required_dt_eff_ns

    lhs = (dt_adjusted_ns * C_NM_PER_NS * c_eff_num) ** 2 if dt_adjusted_ns >= 0 else None
    rhs = (c_eff_den * c_eff_den) * dist2(p0, station_pos_nm)
    consistent = lhs is not None and lhs >= rhs

    if margin_ns > resolve_margin_ns:
        verdict = "ADMITTED"
    elif margin_ns < -resolve_margin_ns:
        verdict = "REJECTED"
    else:
        verdict = "APPARATUS_LIMITED"

    return {
        "t0_ns": int(t0_ns), "t_recv_ns": int(t_recv_ns), "u_ns": int(u_ns),
        "raw_dt_ns": raw_dt_ns, "dt_adjusted_ns": dt_adjusted_ns,
        "c_eff_num": int(c_eff_num), "c_eff_den": int(c_eff_den),
        "lhs_squared_nm2": lhs, "rhs_squared_nm2": rhs, "consistent": consistent,
        "required_dt_eff_ns": required_dt_eff_ns, "margin_ns": margin_ns,
        "resolve_margin_ns": int(resolve_margin_ns),
        "verdict": verdict,
    }


def classify_measured_receipt(t0_ns: int, p0, t_recv_ns: int, station_pos_nm,
                              u_ns: int, c_eff_num: int = C_EFF_NUM,
                              c_eff_den: int = C_EFF_DEN,
                              resolve_margin_ns: int = RESOLVE_MARGIN_NS) -> dict:
    """`{"verdict": ADMITTED|REJECTED|APPARATUS_LIMITED, "witness": {...}}`."""
    w = budget_witness(t0_ns, p0, t_recv_ns, station_pos_nm, u_ns,
                       c_eff_num, c_eff_den, resolve_margin_ns)
    return {"verdict": w["verdict"], "witness": w}


# ---- standalone verifier ----------------------------------------------------
def verify_measured_certificate(cert: dict, registry: dict) -> dict:
    """Independently re-verify a measured cone certificate. Gates, in order
    (per receipt): known_station -> receipt_mac -> payload_binding ->
    surveyed_position -> budget. Then, only for a certificate declaring
    `fixture_origin: LIVE_CAPTURE`, a self-consistency check that no
    receipt's raw elapsed time is negative (a live session cannot rely on
    the uncertainty budget to explain a receipt timestamped before its
    own claimed emission - that signals unresolved clock skew, not a
    consistent-but-slow real path).

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

    node_params = cert.get("node_params", {})
    resolve_margin_ns = cert.get("resolve_margin_ns", RESOLVE_MARGIN_NS)
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

        params = node_params.get(sid, {})
        u_ns = params["u_ns"]
        c_num = params.get("c_eff_num", C_EFF_NUM)
        c_den = params.get("c_eff_den", C_EFF_DEN)
        w = budget_witness(t0, p0, body["recv_time_ns"], st.pos_nm, u_ns,
                           c_num, c_den, resolve_margin_ns)
        per_node[sid] = w
        if w["verdict"] == "REJECTED":
            return {"verdict": "REJECTED",
                    "witness": {"gate": "budget", "station_id": sid,
                                "exact_witness": w,
                                "detail": "receipt impossibly early even at "
                                          "the slow in-medium bound, with the "
                                          "full clock-uncertainty benefit of "
                                          "the doubt"},
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
                            "detail": "measurement cannot resolve admissible "
                                      "from rejected within the declared "
                                      "uncertainty budget"},
                "per_node": per_node}

    return {"verdict": "PASS", "per_node": per_node}
