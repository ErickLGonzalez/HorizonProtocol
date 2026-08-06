"""Exact-integer occultation geometry: link-up/down between a ship and a
ground station, and the occultation interval it produces.  [SOUND]

SP-1 (see docs/sp1-spec.md), built on SP-0's `Worldline`
(`horizon/worldline.py`, unedited by this module — only imported from).

Given two worldlines (e.g. ship and ground station) and an occulting body
modeled as a sphere with its own `Worldline` (center) and an integer
`radius_nm`, the link is DOWN at time `t` iff the minimum distance from the
body's center to the straight segment between the two endpoints' positions
(each evaluated at `t` via `Worldline.position_at`) is <= `radius_nm`.

Exact-integer test, no float, no sqrt, no division (mirrors the closed-form
"compare squared quantities" discipline of `horizon.geometry`): with
`A`/`B` the two endpoint positions and `C` the body center at time `t`,
`AB = B - A`, `AC = C - A`,

    ab2   = AB . AB
    ac_ab = AC . AB

  - `ab2 == 0` (A and B coincide): the "segment" is a point; compare
    `AC . AC` directly.
  - `ac_ab <= 0`: the closest point on the segment is clamped to `A`;
    compare `AC . AC`.
  - `ac_ab >= ab2`: the closest point is clamped to `B`; compare `BC . BC`.
  - otherwise (`0 < ac_ab < ab2`, `ab2 > 0`): the closest point is the
    interior projection. The unclamped squared distance is
    `AC.AC - ac_ab**2 / ab2`; rather than dividing, the inequality
    `dist^2 <= r^2` is multiplied through by `ab2` (positive in this
    branch), which is an exact integer comparison with NO division at all:

        AC.AC * ab2 - ac_ab**2  <=  r_nm**2 * ab2
"""


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def is_link_down(t_ns: int, endpoint_a, endpoint_b, body, radius_nm: int) -> bool:
    """True iff the straight segment between `endpoint_a.position_at(t_ns)`
    and `endpoint_b.position_at(t_ns)` passes within `radius_nm` of
    `body.position_at(t_ns)` — exact integer arithmetic only."""
    a = endpoint_a.position_at(t_ns)
    b = endpoint_b.position_at(t_ns)
    c = body.position_at(t_ns)
    ab = _sub(b, a)
    ac = _sub(c, a)
    ab2 = _dot(ab, ab)
    r2 = radius_nm * radius_nm
    if ab2 == 0:
        return _dot(ac, ac) <= r2
    ac_ab = _dot(ac, ab)
    if ac_ab <= 0:
        return _dot(ac, ac) <= r2
    if ac_ab >= ab2:
        bc = _sub(c, b)
        return _dot(bc, bc) <= r2
    return _dot(ac, ac) * ab2 - ac_ab * ac_ab <= r2 * ab2


def occultation_interval(t_lo: int, t_hi: int, endpoint_a, endpoint_b, body,
                          radius_nm: int, t_hint=None, scan_steps: int = 2000):
    """Find the contiguous `[t_enter, t_exit]` (inclusive integer ns) within
    `[t_lo, t_hi]` during which `is_link_down` is True, or `None` if no
    down-interval is found in range.

    Assumes a SINGLE contiguous down-interval in `[t_lo, t_hi]` (a
    straight-line flyby occults a given link at most once) — the caller's
    geometry must guarantee this; it is not re-derived here. This is not a
    closed-form root solve: `is_link_down` is piecewise (three branches
    above), so the entry/exit boundary is located by exact integer
    bisection directly on that boolean predicate. Every query along the
    way is the exact test, so the located boundary is exact — found by
    search rather than algebra, but no less exact for it (`//` throughout,
    never `/`).

    `t_hint`, if given and already inside the down-interval, skips the
    initial coarse scan used to locate any point inside it. `scan_steps`
    bounds how fine that initial scan is; a down-interval narrower than
    `(t_hi - t_lo) // scan_steps` can be missed — callers with a known
    approximate down-interval should pass `t_hint` instead of relying on
    the scan.
    """
    def down(t):
        return is_link_down(t, endpoint_a, endpoint_b, body, radius_nm)

    anchor = t_hint if t_hint is not None and down(t_hint) else None
    if anchor is None:
        step = max(1, (t_hi - t_lo) // scan_steps)
        t = t_lo
        while t <= t_hi:
            if down(t):
                anchor = t
                break
            t += step
        if anchor is None:
            return None

    lo, hi = t_lo, anchor
    if down(lo):
        t_enter = lo
    else:
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if down(mid):
                hi = mid
            else:
                lo = mid
        t_enter = hi

    lo, hi = anchor, t_hi
    if down(hi):
        t_exit = hi
    else:
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if down(mid):
                lo = mid
            else:
                hi = mid
        t_exit = lo

    return (t_enter, t_exit)
