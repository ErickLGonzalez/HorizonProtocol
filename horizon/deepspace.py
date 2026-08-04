"""Deep-space link geometry: real Earth-Mars separations on the exact lattice. [SOUND]

Distances are exact integers in nanometers; times in nanoseconds; c exact
(reuses geometry.C_NM_PER_NS). In VACUUM the in-medium factor is c_eff = 1
(num=den=1): the fiber loophole that forces c_eff<1 terrestrially vanishes in
space, so the interplanetary gate is the *tightest* form of the exact gate.
"""
from .geometry import C_NM_PER_NS, min_light_time_ns

# Earth-Mars center-to-center separation extremes (approx, meters -> nm).
# Closest approach ~ 54.6e9 m; farthest (superior conjunction) ~ 401e9 m.
AU_M = 149_597_870_700
M_TO_NM = 1_000_000_000

EARTH_MARS_MIN_M = 54_600_000_000      # ~0.365 AU
EARTH_MARS_MAX_M = 401_000_000_000     # ~2.68 AU
EARTH_MARS_TYP_M = 225_000_000_000     # ~1.5 AU typical

C_EFF_VACUUM = (1, 1)  # exact: light in vacuum


def one_way_light_time_ns(distance_m: int) -> int:
    """Exact integer one-way light time for a vacuum path of given metres.
    Delegates to `geometry.min_light_time_ns` (a collinear 1-D distance is
    the same exact quantity that function's general 3-D ceiling search
    computes) rather than reimplementing the ceiling arithmetic - one
    kernel, not two."""
    d_nm = distance_m * M_TO_NM
    return min_light_time_ns((0, 0, 0), (d_nm, 0, 0))


def light_time_table():
    rows = []
    for label, d in [("closest", EARTH_MARS_MIN_M),
                     ("typical", EARTH_MARS_TYP_M),
                     ("farthest", EARTH_MARS_MAX_M)]:
        owlt = one_way_light_time_ns(d)
        rows.append({"regime": label, "distance_m": d,
                     "one_way_light_time_ns": owlt,
                     "one_way_light_time_s": owlt / 1e9,
                     "round_trip_min": (2 * owlt) / 1e9 / 60})
    return rows
