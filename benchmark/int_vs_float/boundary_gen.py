"""Near-light-cone boundary vector generator, across magnitudes.

For a chosen magnitude and integer dt (ns), `C_NM_PER_NS * dt` is an EXACT
integer nanometer radius sitting exactly on the null cone - not an
approximation of a target distance, a genuine point on it, because C and dt
are both integers. Placing the second event at that exact radius along one
axis and then perturbing the axis coordinate by `k` nanometers sweeps
straight through the boundary: k=0 is exactly null (admissible, the closed
future cone includes its own boundary), k>0 is spacelike (must be
rejected), k<0 is timelike (must be admitted) - and the integer gate gets
every one of these exactly right by construction (T1, faithfulness).

The offsets span nine orders of magnitude (1 nm to 1,000,000 nm) precisely
so the sweep crosses the point where each float format's mantissa can no
longer resolve the difference - see docs/int-vs-float-results.md for where
that crossover falls at each magnitude.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from horizon.geometry import C_NM_PER_NS, causally_admissible  # noqa: E402

M_TO_NM = 1_000_000_000
KM_TO_NM = 1_000 * M_TO_NM

# Target light-cone radius (nm) at three representative magnitudes. The
# actual radius used is C_NM_PER_NS * boundary_dt_ns(target) - close to
# this but snapped to an exact integer-ns light-travel time.
MAGNITUDES_NM = {
    "metric (~1 m)": 1 * M_TO_NM,
    "continental (~3,000 km)": 3_000 * KM_TO_NM,
    "interplanetary (~78,000,000 km, Earth-Mars opposition)": 78_000_000 * KM_TO_NM,
}

# Offset from the exact null boundary, in nanometers (lattice units).
# Symmetric around 0 (0 = exactly on the cone), nine orders of magnitude.
OFFSETS_NM = [0]
for mag in (1, 10, 100, 1_000, 10_000, 100_000, 1_000_000):
    OFFSETS_NM.append(mag)
    OFFSETS_NM.append(-mag)


def boundary_dt_ns(target_radius_nm):
    """Nearest integer dt (ns) to target_radius_nm / C, via exact integer
    division (no float division of a possibly-huge int) - rounds to
    nearest, ties away from zero, minimum 1 ns."""
    q, r = divmod(target_radius_nm, C_NM_PER_NS)
    if 2 * r >= C_NM_PER_NS:
        q += 1
    return max(q, 1)


def boundary_pairs(label):
    """Yield one boundary-vector dict per offset in OFFSETS_NM for the given
    magnitude label (a key of MAGNITUDES_NM)."""
    target_radius_nm = MAGNITUDES_NM[label]
    dt_ns = boundary_dt_ns(target_radius_nm)
    radius_nm = C_NM_PER_NS * dt_ns  # exact: a genuine point on the null cone
    t1, t2 = 0, dt_ns
    p1 = (0, 0, 0)
    for k in OFFSETS_NM:
        p2 = (radius_nm + k, 0, 0)
        exact_admissible = causally_admissible(t1, p1, t2, p2)
        yield {
            "magnitude": label,
            "radius_nm": radius_nm,
            "dt_ns": dt_ns,
            "offset_nm": k,
            "t1": t1, "p1": p1, "t2": t2, "p2": p2,
            "exact_admissible": exact_admissible,
        }


def all_pairs():
    for label in MAGNITUDES_NM:
        yield from boundary_pairs(label)
