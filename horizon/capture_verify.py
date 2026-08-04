"""Verify a multi-node capture into a cone certificate.  [SOUND]

Consumes SIGNED, MEASURED receipts and classifies each against the claimed
emission event. Verdicts per receipt:

  ADMITTED           consistent with a real signal path within the clock budget
  REJECTED           impossibly early even accounting for U (carries exact
                     integer witness) OR bad signature / binding / coverage
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
  erratum 1 below) - which is what lets a co-located node (zero flight
  distance, floors both zero) correctly read APPARATUS_LIMITED at every
  tier rather than trivially ADMITTED, and what lets a real intermediate
  node move from APPARATUS_LIMITED to ADMITTED as the tier tightens.
  Whichever question is being asked, REJECTED is decided ONLY by the
  absolute vacuum floor - never by the conservative bound or its band.

(Erratum 1: an earlier version of this module conflated the two questions
above: it REJECTED any receipt landing outside the resolution band around
the conservative c_eff floor, with no reference to the absolute vacuum
floor at all. Two consequences followed:

  1a. A genuine, honest signal that happened to travel faster than the
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

  1b. `verify_capture` read `c_eff` directly from the untrusted `capture`
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

Erratum 2: an earlier version of this module took a receipt's ONLY
authenticated content to be `event_hash` - a hash of the raw PAYLOAD, with
no dependence on the claimed emission time/position. Since `t0_ns`/`p0_nm`
were then read straight from the untrusted `capture` object with nothing
binding them to what any receipt actually signed, an attacker holding ANY
legitimately-signed receipt for ANY real event could pair it with a
SELF-CHOSEN `t0_ns`/`p0_nm` (e.g. the receiving node's own position, or any
`t0_ns` solved to satisfy the vacuum floor) and manufacture an ADMITTED
verdict certifying an entirely fabricated emission claim - the receipt's
signature never covered the claim being certified. Fixed: the hash a
receipt actually signs is now computed OVER the full claim -
`event_hash({"payload_hash": ..., "t0_ns": ..., "p0_nm": ...})` - so
changing `t0_ns` or `p0_nm` after receipts are signed changes the hash
those receipts no longer match, and is caught at the `event_binding` gate
exactly like any other tampered field.

Erratum 3: an earlier version of `classify` REJECTED on a negative raw
`dt` (`recv_time_ns - t0_ns < 0`) BEFORE adding the declared clock
uncertainty `u_ns` in the claimant's favor - so a co-located, genuinely
honest receipt whose raw elapsed time was slightly negative purely from
ordinary clock skew (e.g. `dt=-1` with `u_ns=10`) was REJECTED outright,
even though the u_ns-adjusted time was comfortably non-negative and should
have been resolved by the ordinary vacuum-floor comparison like any other
measurement. Fixed: there is no longer a separate raw-dt pre-check; the
adjusted time `eff = dt + u_ns` is compared directly against
`vacuum_floor_ns` (which is always >= 0), so a genuinely impossible raw dt
still gets REJECTED via that same comparison, and ordinary clock skew
within the declared budget does not.

Erratum 4: an earlier version of `verify_capture` iterated whatever
receipts a capture happened to contain with no floor on their count or
distinctness, so a capture containing a single valid receipt - or the same
valid receipt repeated - could reach a non-REJECTED aggregate, defeating
H8's own core claim of genuine MULTI-node corroboration. Fixed:
`verify_capture` now always rejects an empty capture or one repeating the
same `node_id` across receipts (`distinct_sources`, mirroring
`horizon.measure.verify_measured_certificate`'s identical gate exactly),
and optionally - when the trusted caller supplies `required_node_ids` -
rejects a capture that does not cover every one of them (`node_coverage`).

`tests/test_h8e_trust_boundary.py` regression-tests all four.)
"""
from .events import event_hash
from .geometry import min_light_time_ns
from .measure import C_EFF_DEN, C_EFF_NUM, min_transit_time_ns_eff
from .signed_capture import verify_receipt


def classify(t0_ns, p0_nm, recv_time_ns, p_node_nm, u_ns,
            c_eff_num=C_EFF_NUM, c_eff_den=C_EFF_DEN):
    """Budgeted causal-consistency for one measured receipt, exact integers.
    See module docstring for the two-floor / one-band design and why
    REJECTED is decided only by the absolute vacuum floor."""
    dt = recv_time_ns - t0_ns
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


def bound_event_hash(payload_hash, t0_ns, p0_nm):
    """The hash a receipt actually signs: binds the claimed emission time
    and position into the same commitment as the payload, so a receipt
    signed under one (t0_ns, p0_nm) claim cannot be replayed against a
    different one (see module erratum 2)."""
    return event_hash({"payload_hash": payload_hash, "t0_ns": int(t0_ns),
                       "p0_nm": [int(x) for x in p0_nm]})


def verify_capture(capture, registry, c_eff_num=None, c_eff_den=None,
                   required_node_ids=None):
    """capture: {payload_hash, t0_ns, p0_nm, c_eff:[num,den] (provenance
    only, see erratum 1), receipts:[signed]}, where each receipt's
    `body.event_hash` must equal `bound_event_hash(payload_hash, t0_ns,
    p0_nm)` (see erratum 2). registry: {node_id: {pos_nm, u_ns, tier}}.
    `c_eff_num`/`c_eff_den` are TRUSTED CALLER INPUT (default:
    `horizon.measure`'s frozen conservative fiber bound) - never read from
    `capture` itself. `required_node_ids`, when given (a caller-supplied
    trusted set), rejects a capture that does not cover every one of them
    (see erratum 4); omitted, no coverage requirement beyond distinctness.
    Returns aggregate + per-receipt."""
    num = C_EFF_NUM if c_eff_num is None else c_eff_num
    den = C_EFF_DEN if c_eff_den is None else c_eff_den
    t0 = capture["t0_ns"]
    p0 = tuple(capture["p0_nm"])
    receipts = capture["receipts"]

    if not receipts:
        return {"aggregate": "REJECTED", "per_receipt": [],
               "witness": {"gate": "nonempty_receipts"}}

    node_ids = [r["body"]["node_id"] for r in receipts]
    if len(set(node_ids)) != len(node_ids):
        return {"aggregate": "REJECTED", "per_receipt": [],
               "witness": {"gate": "distinct_sources", "node_ids": node_ids}}

    if required_node_ids is not None:
        required = set(required_node_ids)
        got = set(node_ids)
        if got != required:
            return {"aggregate": "REJECTED", "per_receipt": [],
                   "witness": {"gate": "node_coverage",
                               "missing": sorted(required - got),
                               "unexpected": sorted(got - required)}}

    expected_event_hash = bound_event_hash(capture["payload_hash"], t0, p0)

    per = []
    verdicts = []
    for r in receipts:
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
        # Gate 3: event binding - covers payload AND the claimed t0/p0
        if body["event_hash"] != expected_event_hash:
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
    else:
        agg = "PASS"
    return {"aggregate": agg, "per_receipt": per,
            "payload_hash": capture["payload_hash"],
            "expected_event_hash": expected_event_hash,
            "c_eff_declared": capture.get("c_eff"),
            "c_eff_trusted": [num, den]}
