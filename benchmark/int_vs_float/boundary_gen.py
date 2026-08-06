"""Near-light-cone boundary vector generator, across magnitudes.

For a chosen magnitude and integer dt (ns), `C_NM_PER_NS * dt` is an EXACT
integer nanometer radius sitting exactly on the null cone - not an
approximation of a target distance, a genuine point on it, because C and dt
are both integers. `boundary_dt_ns` snaps dt to a multiple of 3 so that
radius, dx0 = radius/3, dy0 = dz0 = 2*radius/3 form an exact Pythagorean
quadruple (1:2:2:3, since 1^2+2^2+2^2=3^2): (dx0, dy0, dz0) is a genuine
on-cone point with all THREE coordinates nonzero, not one. This matters for
Test 2 (reproducibility): a single-nonzero-coordinate vector makes
`dx^2+dy^2+dz^2` degenerate to one nonzero term regardless of summation
order, so neither "sum in a different order" nor "sum via a different
algorithm" can exhibit the non-associativity they're meant to probe - a
one-axis vector cannot distinguish `xyz` from `zyx` summation, nor
`sumsq` from `hypot`, because there is nothing to reorder. Perturbing only
the dx0 axis by `k` nanometers then sweeps straight through the boundary
exactly as before: k=0 is exactly null (admissible, the closed future cone
includes its own boundary), k>0 is spacelike (must be rejected), k<0 is
timelike (must be admitted) - and the integer gate gets every one of these
exactly right by construction (T1, faithfulness), independent of which
axis the perturbation lands on.

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
    """Nearest integer dt (ns) to target_radius_nm / C, snapped down to a
    multiple of 3 (via exact integer division - no float division of a
    possibly-huge int) so C*dt is exactly divisible by 3, minimum 3 ns.
    The multiple-of-3 snap is what makes the 1:2:2:3 multi-axis
    decomposition in `boundary_pairs` exact - see module docstring."""
    q, r = divmod(target_radius_nm, C_NM_PER_NS)
    if 2 * r >= C_NM_PER_NS:
        q += 1
    dt = max(q, 1)
    dt -= dt % 3
    return max(dt, 3)


def boundary_pairs(label):
    """Yield one boundary-vector dict per offset in OFFSETS_NM for the given
    magnitude label (a key of MAGNITUDES_NM). The unperturbed point
    (dx0, dy0, dz0) is an exact on-cone Pythagorean quadruple with all
    three coordinates nonzero (see module docstring); `k` perturbs only
    the dx0 axis, same as sweeping a single coordinate before, but now
    against a genuinely multi-axis baseline."""
    target_radius_nm = MAGNITUDES_NM[label]
    dt_ns = boundary_dt_ns(target_radius_nm)
    radius_nm = C_NM_PER_NS * dt_ns  # exact: a genuine point on the null cone
    third = radius_nm // 3
    assert third * 3 == radius_nm  # exact by construction (dt_ns is a multiple of 3)
    dx0, dy0, dz0 = third, 2 * third, 2 * third  # 1^2+2^2+2^2 = 3^2
    t1, t2 = 0, dt_ns
    p1 = (0, 0, 0)
    for k in OFFSETS_NM:
        p2 = (dx0 + k, dy0, dz0)
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
