"""Three-verdict admissibility gate over position uncertainty:
ADMITTED / REJECTED / APPARATUS_LIMITED.  [SOUND]

SP-2 (see docs/sp2-spec.md). This is the two-floor pattern already
established in this repo for MEASURED-TIME uncertainty
(`horizon.measure.classify_measured_receipt`, `horizon.capture_verify`:
REJECTED only below the absolute vacuum-c floor, APPARATUS_LIMITED between
that floor and a more conservative one, ADMITTED only once even the
conservative floor is cleared) — applied here to POSITION uncertainty
instead of clock uncertainty. The frozen `causally_admissible`
(`horizon.geometry`, imported, never redefined) is the sole admissibility
test in spirit; this module only ever evaluates its extremal-distance form
against a `TrajectoryEnvelope` (`horizon.uncertainty`, imported, never
redefined) — it never invents a second notion of admissibility.

Given two events at `(t1, side1)` and `(t2, side2)`, where each side is
EITHER a definite position (a length-3 sequence of exact ints) OR a
`TrajectoryEnvelope` (uncertain position, exact center + radius at that
time) — either side may be either kind, including both at once:

  - **ADMITTED**: the WORST case (the two sides' farthest-apart possible
    positions, at exact distance `d + r1 + r2` where `d` is the distance
    between the two centers and `r1`/`r2` are each side's radius, 0 for a
    definite position) still satisfies admissibility — true for every
    position combination either side allows.
  - **REJECTED**: the BEST case (closest-possible positions, at exact
    distance `max(0, d - r1 - r2)`) still FAILS — physically impossible
    for every combination (the absolute floor; `t2 < t1` is the degenerate
    instance, checked FIRST and unconditionally, since a negative time gap
    fails regardless of any position — this must be checked before
    touching either envelope's `radius_at`, which is undefined before its
    own contact time).
  - **APPARATUS_LIMITED**: neither of the above — the two envelopes
    straddle the light cone, so some position combinations would be
    admissible and others would not.

Exact-integer test, no float, no sqrt: let `D = dist2(center1, center2)`
(exact, `horizon.geometry.dist2`, unmodified), `r = r1 + r2`, and
`L = C_NM_PER_NS * dt`. Both extremal distances involve the irrational
`sqrt(D)` in general, but comparing `L` against them is done by moving `r`
to the same side as `L` FIRST (both sides then non-negative) and only THEN
squaring — which needs no sqrt at all:

    ADMITTED   iff  L >= r  and  (L - r)**2 >= D
    REJECTED   iff  D > r*r  and  (L + r)**2 < D      (or dt < 0, unconditionally)
    else            APPARATUS_LIMITED

(`ADMITTED`'s and `REJECTED`'s conditions are mutually exclusive: since
`(L - r)**2 <= (L + r)**2` whenever `L >= r >= 0`, `D` cannot be both
`<= (L - r)**2` and `> (L + r)**2` at once. With `r1 = r2 = 0` this
collapses exactly to `causally_admissible`'s own boolean condition, with
no `APPARATUS_LIMITED` band possible — a definite/definite pair is always
decisively `ADMITTED` or `REJECTED`.)
"""
from horizon.geometry import C_NM_PER_NS, dist2
from horizon.uncertainty import TrajectoryEnvelope


def _require_int(value, what):
    if not isinstance(value, int):
        raise TypeError(f"{what} must be an exact int, got {type(value).__name__}: {value!r}")
    return value


def _resolve(t_ns: int, side):
    """`(position, radius)` for `side` at `t_ns` — either a `TrajectoryEnvelope`
    (center + radius) or a definite position (a length-3 sequence of exact
    ints, radius 0). Rejects a runtime float in a definite position, the
    same discipline as every other public boundary in this module (a float
    slipping in here would silently switch `dist2`'s arithmetic to
    floating point)."""
    if isinstance(side, TrajectoryEnvelope):
        return side.center_at(t_ns), side.radius_at(t_ns)
    pos = tuple(side)
    for i, c in enumerate(pos):
        _require_int(c, f"position component [{i}]")
    return pos, 0


def two_floor_verdict(t1: int, p1, t2: int, envelope) -> dict:
    """Classify the admissibility of `(t1, p1) <-> (t2, envelope)` against
    the two extremal floors described in the module docstring. `p1` may be
    a definite position OR itself a `TrajectoryEnvelope` — uncertainty on
    either side (or both) is handled identically, by summing the radii.
    Returns `{"verdict": ..., "witness": {...}}`; the witness always names
    which floor (or neither) decided the verdict."""
    _require_int(t1, "t1")
    _require_int(t2, "t2")
    dt = t2 - t1
    witness = {"t1": t1, "t2": t2, "dt_ns": dt}
    if dt < 0:
        # checked before resolving either side: a TrajectoryEnvelope's
        # radius_at is undefined before its own contact time, and a
        # negative dt fails admissibility unconditionally regardless of
        # position anyway (the kernel's own dt<0 short-circuit)
        witness["reason"] = "negative_dt"
        return {"verdict": "REJECTED", "witness": witness}

    center1, r1 = _resolve(t1, p1)
    center2, r2 = _resolve(t2, envelope)
    r = r1 + r2
    d2 = dist2(center1, center2)
    lhs = C_NM_PER_NS * dt
    witness.update({
        "center1_nm": center1, "center2_nm": center2,
        "radius1_nm": r1, "radius2_nm": r2, "radius_nm": r,
        "dist2_to_center_nm2": d2, "c_dt_nm": lhs,
    })

    worst_case_admitted = lhs >= r and (lhs - r) ** 2 >= d2
    best_case_rejected = d2 > r * r and (lhs + r) ** 2 < d2

    if worst_case_admitted:
        witness["reason"] = "worst_case_in_envelope_admissible"
        return {"verdict": "ADMITTED", "witness": witness}
    if best_case_rejected:
        witness["reason"] = "best_case_in_envelope_still_fails_vacuum_floor"
        return {"verdict": "REJECTED", "witness": witness}
    witness["reason"] = "envelope_straddles_the_light_cone"
    return {"verdict": "APPARATUS_LIMITED", "witness": witness}
