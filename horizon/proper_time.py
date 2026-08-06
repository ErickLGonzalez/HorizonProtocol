"""Exact-rational per-node proper time.  [SOUND]

SP-3 (see docs/sp3-spec.md), built on `horizon.geometry.C_NM_PER_NS`
(imported, never modified).

Each node accumulates its OWN proper time `tau` at an exact-rational rate
relative to the shared coordinate time the kernel's worldlines are
expressed in:

    dtau/dt_coord = rate_num / rate_den

`weak_field_rate` derives this rate from the standard weak-field, low-
velocity approximation cited in the manuscript (section 2),
`dtau/dt ~= 1 + Phi/c^2 - v^2/(2c^2)` — deliberately the polynomial
weak-field expansion, NOT the exact relativistic `sqrt(1 - v^2/c^2)`: the
exact form is irrational for a generic velocity, and this module's entire
point is to stay exact, so it uses the formula that is already rational in
its integer inputs (`v^2`, `Phi`) rather than approximating an irrational
one. This is an honestly-labeled approximation of the physics, not a claim
of exact relativity — see docs/sp3-spec.md.

`tau_at(t_coord) = tau0 + floor(rate_num * (t_coord - t0_coord) / rate_den)`
— exact integer floor division (`//`), never a float, the same technique
`horizon.worldline.LinearWorldline` uses for rational velocity.

**The critical guard (F2 — the reason this module exists):** a
`ProperTimeStamp` carries the node_id it was stamped by, and its
comparison operators RAISE if asked to compare stamps from two DIFFERENT
nodes. There is no shared "now" across divergent proper times (the
weak-form causal-divergence theorem), so ordering across nodes must never
be decided by comparing `tau` values directly — that is `horizon.reconcile`'s
job, using causal lineage validated by the light cone, never clock
comparison.
"""
from horizon.geometry import C_NM_PER_NS


def _require_int(value, what):
    if not isinstance(value, int):
        raise TypeError(f"{what} must be an exact int, got {type(value).__name__}: {value!r}")
    return value


def weak_field_rate(v2_nm2_per_ns2: int, phi_nm2_per_ns2: int = 0):
    """Exact rational `(num, den)` for `dtau/dt_coord ~= 1 + Phi/c^2 -
    v^2/(2c^2)`, given `v^2` (nm^2/ns^2) and the gravitational potential
    `Phi` (same units, e.g. `-G*M/r`) as exact integers. No sqrt, no float
    — this weak-field formula is already polynomial/rational in its
    inputs, computed over the common denominator `2*c^2`."""
    _require_int(v2_nm2_per_ns2, "v2_nm2_per_ns2")
    _require_int(phi_nm2_per_ns2, "phi_nm2_per_ns2")
    if v2_nm2_per_ns2 < 0:
        raise ValueError("v^2 must be non-negative")
    c2 = C_NM_PER_NS * C_NM_PER_NS
    num = 2 * c2 + 2 * phi_nm2_per_ns2 - v2_nm2_per_ns2
    den = 2 * c2
    return (num, den)


class ProperTimeStamp:
    """One node's own proper-time reading. Comparisons across DIFFERENT
    `node_id`s raise `ValueError` — see module docstring's guard note."""
    __slots__ = ("node_id", "tau_ns")

    def __init__(self, node_id, tau_ns: int):
        self.node_id = node_id
        self.tau_ns = _require_int(tau_ns, "tau_ns")

    def _guard(self, other):
        if not isinstance(other, ProperTimeStamp):
            return NotImplemented
        if other.node_id != self.node_id:
            raise ValueError(
                f"cannot compare proper-time stamps from different nodes "
                f"({self.node_id!r} vs {other.node_id!r}): there is no "
                f"shared 'now' across divergent proper times (SP-3, the "
                f"weak-form causal-divergence theorem). Cross-node order "
                f"must come from horizon.reconcile (causal lineage + the "
                f"light cone), never from comparing tau directly.")
        return None

    def __eq__(self, other):
        guard = self._guard(other)
        if guard is NotImplemented:
            return NotImplemented
        return self.tau_ns == other.tau_ns

    def __lt__(self, other):
        self._guard(other)
        return self.tau_ns < other.tau_ns

    def __le__(self, other):
        self._guard(other)
        return self.tau_ns <= other.tau_ns

    def __gt__(self, other):
        self._guard(other)
        return self.tau_ns > other.tau_ns

    def __ge__(self, other):
        self._guard(other)
        return self.tau_ns >= other.tau_ns

    def __repr__(self):
        return f"ProperTimeStamp({self.node_id!r}, {self.tau_ns})"


class ProperTimeClock:
    """A node's clock: an exact-rational rate relative to coordinate time,
    anchored at `(t0_coord_ns, tau0_ns)`."""

    def __init__(self, node_id, rate_num: int, rate_den: int,
                 t0_coord_ns: int = 0, tau0_ns: int = 0):
        self.node_id = node_id
        _require_int(rate_num, "rate_num")
        _require_int(rate_den, "rate_den")
        if rate_den == 0:
            raise ValueError("rate denominator must be nonzero")
        if rate_den < 0:
            rate_num, rate_den = -rate_num, -rate_den
        self.rate_num = rate_num
        self.rate_den = rate_den
        self.t0_coord_ns = _require_int(t0_coord_ns, "t0_coord_ns")
        self.tau0_ns = _require_int(tau0_ns, "tau0_ns")

    def tau_at(self, t_coord_ns: int) -> int:
        _require_int(t_coord_ns, "t_coord_ns")
        dt = t_coord_ns - self.t0_coord_ns
        return self.tau0_ns + (self.rate_num * dt) // self.rate_den

    def stamp_at(self, t_coord_ns: int) -> ProperTimeStamp:
        return ProperTimeStamp(self.node_id, self.tau_at(t_coord_ns))
