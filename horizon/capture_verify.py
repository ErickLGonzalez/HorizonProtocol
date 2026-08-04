"""Verify a multi-node capture into a cone certificate.  [SOUND]

Consumes SIGNED, MEASURED receipts and classifies each against the claimed
emission event. Verdicts per receipt:

  ADMITTED           consistent with a real signal path within the clock budget
  REJECTED           impossibly early even accounting for U (carries exact
                     integer witness) OR bad signature / binding
  APPARATUS_LIMITED  this tier's clock cannot confidently resolve the
                     geometry against the declared real-medium model

The verifier imports NO live-capture or simulator code (H8-D asserts it).

Design note - two floors, two different jobs:
  `vacuum_floor_ns` (`horizon.geometry.min_light_time_ns`, reused exactly) is
  the ONLY floor that can ever justify REJECTED: nothing, in any medium,
  travels faster than this, so a receipt earlier than it - even after adding
  the full declared clock uncertainty `u_ns` in the claimant's favor - is
  physically impossible.
  `typical_floor_ns` (`horizon.measure.min_transit_time_ns_eff`, reused
  exactly, at the same frozen conservative c_eff = 3/5 fiber bound H5/H6
  use) is the declared, ordinary real-medium expectation. Unlike
  `horizon.measure`'s certificate gate - which only needs to answer "is this
  consistent with SOME legitimate path" and treats the entire gap between
  the two floors as one undifferentiated APPARATUS_LIMITED band - H8 also
  needs to answer a second, narrower question the tier-transition gate
  (H8-D) depends on: "is this tier's clock precise enough to confidently
  place the arrival at-or-after the conservative bound, or could ordinary
  jitter of size `u_ns` explain the whole discrepancy?" That second question
  is answered by a band of width `2*u_ns` centered on the (adjusted) arrival,
  derived from the SAME nanosecond quantities - never a squared one (see
  erratum below) - which is what lets a co-located node (zero flight
  distance, floors both zero) correctly read APPARATUS_LIMITED at every
  tier rather than trivially ADMITTED, and what lets a real intermediate
  node move from APPARATUS_LIMITED to ADMITTED as the tier tightens.
  Whichever question is being asked, REJECTED is decided ONLY by the
  absolute vacuum floor - never by the conservative bound or its band.

(Erratum: an earlier version of this module conflated the two questions
above: it REJECTED any receipt landing outside the resolution band around
the conservative c_eff floor, with no reference to the absolute vacuum
floor at all. Two consequences followed:

  1. A genuine, honest signal that happened to travel faster than the
     CONSERVATIVE c_eff bound (anywhere up to vacuum c - c_eff is a
     declared lower bound on real-medium speed, not a ceiling) could be
     REJECTED as if it were physically impossible whenever the discrepancy
     exceeded the tier's jitter band. Concretely: a 475 km signal genuinely
     travelling at 0.8c (well below vacuum c, comfortably real) was
     REJECTED outright at PTP/GNSS-tier clock precision by the old
     classify() - a real, honest, in-budget signal, REJECTED (exactly the
     failure mode `horizon.measure`'s own docstring already documents
     fixing once for H5, and this module's registered falsifier F1 exists
     to catch: "a real in-budget signal REJECTED -> gate/budget defect").
     Fixed: REJECTED is now decided ONLY against `vacuum_floor_ns`, which no
     real signal can ever beat, honest or not.

  2. `verify_capture` read `c_eff` directly from the untrusted `capture`
     object being classified (`capture["c_eff"]`), rather than from a
     TRUSTED caller-supplied parameter - exactly the trust-boundary
     violation `horizon.measure`'s own docstring warns against ("if its own
     claimed ... speed bound were used to classify its own receipts, a
     forger could simply declare ... a superluminal c_eff"). Fixed:
     `verify_capture` takes `c_eff_num`/`c_eff_den` as trusted caller input
     (default: `horizon.measure`'s frozen 3/5 bound, matching H8's own
     declared model), exactly like `verify_measured_certificate`'s
     `node_params`. A `c_eff` recorded inside a `capture` blob is
     provenance only, describing what model generated the data - never fed
     into the classification decision.

`tests/test_h8e_trust_boundary.py` regression-tests both.)
"""
from .geometry import min_light_time_ns
from .measure import C_EFF_DEN, C_EFF_NUM, min_transit_time_ns_eff
from .signed_capture import verify_receipt


def classify(t0_ns, p0_nm, recv_time_ns, p_node_nm, u_ns,
            c_eff_num=C_EFF_NUM, c_eff_den=C_EFF_DEN):
    """Budgeted causal-consistency for one measured receipt, exact integers.
    See module docstring for the two-floor / one-band design and why
    REJECTED is decided only by the absolute vacuum floor."""
    dt = recv_time_ns - t0_ns
    if dt < 0:
        return {"verdict": "REJECTED",
                "witness": {"reason": "arrival_before_emission", "dt_ns": dt}}
    eff = dt + u_ns  # clock error helps the (honest or dishonest) claimant
    vacuum_floor_ns = min_light_time_ns(p0_nm, p_node_nm)
    typical_floor_ns = min_transit_time_ns_eff(p0_nm, p_node_nm,
                                               c_eff_num, c_eff_den)
    band_ns = 2 * u_ns
    w = {"dt_ns": dt, "u_ns": u_ns, "dt_adjusted_ns": eff,
         "vacuum_floor_ns": vacuum_floor_ns, "typical_floor_ns": typical_floor_ns,
         "resolution_band_ns": band_ns,
         "margin_below_vacuum_floor_ns": vacuum_floor_ns - eff,
         "margin_from_typical_floor_ns": eff - typical_floor_ns}
    if eff < vacuum_floor_ns:
        return {"verdict": "REJECTED",
                "witness": {**w, "reason": "below_vacuum_floor"}}
    if abs(eff - typical_floor_ns) <= band_ns:
        return {"verdict": "APPARATUS_LIMITED", "witness": w}
    return {"verdict": "ADMITTED", "witness": w}


def verify_capture(capture, registry, c_eff_num=None, c_eff_den=None):
    """capture: {event_hash, t0_ns, p0_nm, c_eff:[num,den] (provenance only,
    see erratum), receipts:[signed]}. registry: {node_id: {pos_nm, u_ns,
    tier}}. `c_eff_num`/`c_eff_den` are TRUSTED CALLER INPUT (default:
    `horizon.measure`'s frozen conservative fiber bound) - never read from
    `capture` itself. Returns aggregate + per-receipt."""
    num = C_EFF_NUM if c_eff_num is None else c_eff_num
    den = C_EFF_DEN if c_eff_den is None else c_eff_den
    t0 = capture["t0_ns"]
    p0 = tuple(capture["p0_nm"])
    per = []
    verdicts = []
    for r in capture["receipts"]:
        body = r["body"]
        nid = body["node_id"]
        # Gate 1: signature authentic
        if not verify_receipt(r):
            per.append({"node_id": nid, "verdict": "REJECTED",
                        "witness": {"gate": "signature"}})
            verdicts.append("REJECTED"); continue
        # Gate 2: known node
        node = registry.get(nid)
        if node is None:
            per.append({"node_id": nid, "verdict": "REJECTED",
                        "witness": {"gate": "unknown_node"}})
            verdicts.append("REJECTED"); continue
        # Gate 3: event binding
        if body["event_hash"] != capture["event_hash"]:
            per.append({"node_id": nid, "verdict": "REJECTED",
                        "witness": {"gate": "event_binding"}})
            verdicts.append("REJECTED"); continue
        # Gate 4: surveyed position matches registry
        if tuple(body["node_pos_nm"]) != tuple(node["pos_nm"]):
            per.append({"node_id": nid, "verdict": "REJECTED",
                        "witness": {"gate": "surveyed_position"}})
            verdicts.append("REJECTED"); continue
        # Gate 5: budgeted light-cone consistency (exact, trusted c_eff)
        res = classify(t0, p0, body["recv_time_ns"], tuple(node["pos_nm"]),
                       node["u_ns"], num, den)
        per.append({"node_id": nid, "tier": node["tier"], **res})
        verdicts.append(res["verdict"])

    if "REJECTED" in verdicts:
        agg = "REJECTED"
    elif "APPARATUS_LIMITED" in verdicts:
        agg = "APPARATUS_LIMITED"
    elif verdicts:
        agg = "PASS"
    else:
        agg = "EMPTY"
    return {"aggregate": agg, "per_receipt": per,
            "event_hash": capture["event_hash"],
            "c_eff_declared": capture.get("c_eff"),
            "c_eff_trusted": [num, den]}
