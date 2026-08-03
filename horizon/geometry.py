"""Exact light-cone geometry kernel.  [SOUND]

Units: nanometers (position), nanoseconds (time).
c = 299_792_458 nm/ns exactly (since c = 299,792,458 m/s).

The single security-critical predicate is `causally_admissible`:
an influence from (t1, p1) to (t2, p2) is admissible iff

    t2 >= t1   and   (c * (t2 - t1))**2 >= |p2 - p1|**2

evaluated in exact integer arithmetic. This is the timelike-or-null
(causal) condition; no square roots, no floats, no tolerance.
"""
import math

C_NM_PER_NS = 299_792_458  # exact


def dist2(p1, p2) -> int:
    """Exact squared Euclidean distance in nm^2."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dz = p2[2] - p1[2]
    return dx * dx + dy * dy + dz * dz


def causally_admissible(t1: int, p1, t2: int, p2) -> bool:
    """True iff event 2 lies in the closed future light cone of event 1."""
    dt = t2 - t1
    if dt < 0:
        return False
    lhs = (C_NM_PER_NS * dt) ** 2
    return lhs >= dist2(p1, p2)


def admissibility_witness(t1: int, p1, t2: int, p2) -> dict:
    """Exact integer witness for the admissibility decision (for certificates)."""
    dt = t2 - t1
    lhs = (C_NM_PER_NS * dt) ** 2 if dt >= 0 else None
    rhs = dist2(p1, p2)
    return {
        "dt_ns": dt,
        "c_nm_per_ns": C_NM_PER_NS,
        "lhs_c_dt_squared": lhs,
        "rhs_dist_squared_nm2": rhs,
        "admissible": causally_admissible(t1, p1, t2, p2),
    }


def min_light_time_ns(p1, p2) -> int:
    """Smallest integer dt (ns) with (c*dt)^2 >= dist^2 (exact)."""
    d2 = dist2(p1, p2)
    if d2 == 0:
        return 0
    r = math.isqrt(d2)
    if r * r < d2:
        r += 1  # r = ceil(sqrt(d2))
    dt = -(-r // C_NM_PER_NS)  # ceil(r / c)
    while dt > 0 and (C_NM_PER_NS * (dt - 1)) ** 2 >= d2:
        dt -= 1
    while (C_NM_PER_NS * dt) ** 2 < d2:
        dt += 1
    return dt
