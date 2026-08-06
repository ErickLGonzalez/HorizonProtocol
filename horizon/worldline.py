"""Exact-integer worldlines: a node's position as a function of time.  [SOUND]

SP-0 (see docs/sp0-spec.md). Promotes a node's fixed `pos_nm` to a trajectory
so the frozen light-cone kernel (`horizon.geometry.causally_admissible`) can
be evaluated against a *moving* node (a spaceship) without touching that
kernel at all — see `causally_admissible_wl` below, which evaluates each
side's worldline to a point and then defers entirely to the unmodified
predicate.

`horizon/geometry.py` is byte-hash-pinned by several committed certificates
(`certificates/h5_certificate.json` through `h9`, `h8_live*`) via
`scripts/validate_certificates.py`'s `source_hashes` check — even an
additive append to that file breaks those certificates' recorded hash. The
wrapper therefore lives here, in this new module, and only ever *imports*
`causally_admissible`; `horizon/geometry.py` itself is left completely
unedited by SP-0 (verify with `git diff --stat horizon/geometry.py`).

Exactness rule (non-negotiable — HorizonProtocol #10 showed float64 cannot
resolve a nanometer offset at interplanetary scale, which flips real
admissibility verdicts): `position_at` returns exact integer nanometers at
an exact integer nanosecond, for every worldline in this module. Fractional
velocities are carried as exact (numerator, denominator) integer pairs and
floor-divided (`//`, never `/`) to an integer nm result — no float ever
enters the computation.
"""
from horizon.geometry import causally_admissible


class Worldline:
    """A trajectory: `position_at(t_ns)` -> exact integer `(x_nm, y_nm, z_nm)`."""

    def position_at(self, t_ns: int):
        raise NotImplementedError


class FixedWorldline(Worldline):
    """A stationary node — today's fixed `pos_nm`, as the constant-worldline
    special case. `position_at` ignores `t_ns` and always returns `pos_nm`."""

    def __init__(self, pos_nm):
        self.pos_nm = tuple(pos_nm)

    def position_at(self, t_ns: int):
        return self.pos_nm


def _as_rational(component):
    """Normalize one velocity component to an exact (numerator, denominator)
    integer pair with denominator > 0. A plain int `v` is `(v, 1)`; a
    `(num, den)` tuple is taken as-is (sign folded into the numerator)."""
    if isinstance(component, tuple):
        num, den = component
        if den == 0:
            raise ValueError("velocity denominator must be nonzero")
        if den < 0:
            num, den = -num, -den
        return (num, den)
    return (component, 1)


class LinearWorldline(Worldline):
    """A coasting node: `position_at(t) = p0 + v * (t - t0)`, exact on the
    integer nm/ns lattice.

    `v_nm_per_ns` is a length-3 sequence, one component per axis; each
    component is either a plain integer (whole nm/ns) or an exact
    `(numerator, denominator)` rational for sub-unit velocities. The result
    is always floor-divided (`//`) to an integer nm — never a float."""

    def __init__(self, p0_nm, t0_ns: int, v_nm_per_ns):
        self.p0_nm = tuple(p0_nm)
        self.t0_ns = t0_ns
        self.v_nm_per_ns = tuple(_as_rational(c) for c in v_nm_per_ns)

    def position_at(self, t_ns: int):
        dt = t_ns - self.t0_ns
        return tuple(
            p0 + (num * dt) // den
            for p0, (num, den) in zip(self.p0_nm, self.v_nm_per_ns)
        )


def causally_admissible_wl(a, t1: int, b, t2: int) -> bool:
    """Worldline-aware wrapper: evaluate each side's worldline to an exact
    integer point at its own event time, then defer entirely to the FROZEN
    `causally_admissible` — imported, never redefined or modified — to
    decide admissibility on those two points.

    `a` and `b` are any object exposing `position_at(t_ns) -> (x_nm, y_nm,
    z_nm)` (a `Worldline`, e.g. `FixedWorldline` or `LinearWorldline`
    above). All moving-node logic lives in the worldline evaluation; the
    admissibility test itself never changes."""
    p1 = a.position_at(t1)
    p2 = b.position_at(t2)
    return causally_admissible(t1, p1, t2, p2)
