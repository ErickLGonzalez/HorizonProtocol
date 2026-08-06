"""Three-verdict admissibility gate over a position-uncertainty envelope:
ADMITTED / REJECTED / APPARATUS_LIMITED.  [SOUND]

SP-2 (see docs/sp2-spec.md). This is the two-floor pattern already
established in this repo for MEASURED-TIME uncertainty
(`horizon.measure.classify_measured_receipt`, `horizon.capture_verify`:
REJECTED only below the absolute vacuum-c floor, APPARATUS_LIMITED between
that floor and a more conservative one, ADMITTED only once even the
conservative floor is cleared) — applied here to POSITION uncertainty
instead of clock uncertainty. The frozen `causally_admissible`
(`horizon.geometry`, imported, never redefined) is the sole admissibility
test; this module only ever evaluates it at the two EXTREMAL points of a
`TrajectoryEnvelope` (`horizon.uncertainty`, imported, never redefined) —
it never invents a second notion of admissibility.

Given a definite event `(t1, p1)` and a `TrajectoryEnvelope` for the other
side's position at `t2` (center `c`, radius `r`, both exact integers):

  - **ADMITTED**: the WORST case (farthest point in the envelope from
    `p1`, at exact distance `d + r` where `d = |p1 - c|`) still satisfies
    `causally_admissible` — true for every position the envelope allows.
  - **REJECTED**: the BEST case (closest point in the envelope to `p1`, at
    exact distance `max(0, d - r)`) still FAILS `causally_admissible` —
    physically impossible for every position the envelope allows (the
    absolute floor; `t2 < t1` is the degenerate instance of this, since
    then EVERY position fails regardless of distance).
  - **APPARATUS_LIMITED**: neither of the above — the envelope straddles
    the light cone, so some in-envelope positions would be admissible and
    others would not, and this gate cannot resolve which.

Exact-integer test, no float, no sqrt: let `D = dist2(p1, c)` (exact,
`horizon.geometry.dist2`, unmodified) and `L = C_NM_PER_NS * dt`. Both
`d + r` and `max(0, d - r)` involve the irrational `d = sqrt(D)` in
general, but comparing `L` against them is done by moving `r` to the same
side as `L` FIRST (both sides then non-negative) and only THEN squaring —
which needs no sqrt at all:

    ADMITTED   iff  L >= r  and  (L - r)**2 >= D
    REJECTED   iff  D > r*r  and  (L + r)**2 < D      (or dt < 0, unconditionally)
    else            APPARATUS_LIMITED

(`ADMITTED`'s and `REJECTED`'s conditions are mutually exclusive: since
`(L - r)**2 <= (L + r)**2` whenever `L >= r >= 0`, `D` cannot be both
`<= (L - r)**2` and `> (L + r)**2` at once.)
"""
from horizon.geometry import C_NM_PER_NS, causally_admissible, dist2


def two_floor_verdict(t1: int, p1, t2: int, envelope) -> dict:
    """Classify the admissibility of `(t1, p1) -> (t2, <somewhere in
    envelope>)` against the two extremal floors described in the module
    docstring. Returns `{"verdict": ..., "witness": {...}}`; the witness
    always names which floor (or neither) decided the verdict, and never
    cites a clock/position value that wasn't one of the two exact extremal
    distances actually compared."""
    dt = t2 - t1
    center = envelope.center_at(t2)
    r = envelope.radius_at(t2)
    d2 = dist2(p1, center)
    witness = {
        "t1": t1, "t2": t2, "dt_ns": dt, "p1": tuple(p1), "center_nm": tuple(center),
        "radius_nm": r, "dist2_to_center_nm2": d2,
    }
    if dt < 0:
        witness["reason"] = "negative_dt"
        return {"verdict": "REJECTED", "witness": witness}

    lhs = C_NM_PER_NS * dt
    worst_case_admitted = lhs >= r and (lhs - r) ** 2 >= d2
    best_case_rejected = d2 > r * r and (lhs + r) ** 2 < d2
    witness["c_dt_nm"] = lhs

    if worst_case_admitted:
        witness["reason"] = "worst_case_in_envelope_admissible"
        return {"verdict": "ADMITTED", "witness": witness}
    if best_case_rejected:
        witness["reason"] = "best_case_in_envelope_still_fails_vacuum_floor"
        return {"verdict": "REJECTED", "witness": witness}
    witness["reason"] = "envelope_straddles_the_light_cone"
    return {"verdict": "APPARATUS_LIMITED", "witness": witness}
