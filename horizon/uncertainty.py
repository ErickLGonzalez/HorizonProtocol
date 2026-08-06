"""Exact-integer position-uncertainty envelope for a node known only as of
its last contact.  [SOUND]

SP-2 (see docs/sp2-spec.md), built on SP-0's `Worldline`
(`horizon/worldline.py`, unedited by this module — only imported from).

Between contacts, a ship's true position is not exactly known: only its
state at the last contact time `t_c` (position, plus declared velocity- and
acceleration-uncertainty bounds) is known, light-delay-corrected. The
`TrajectoryEnvelope` below models the resulting "cone of possibility" as an
exact-integer ball: a center (the best-estimate `nominal` worldline,
evaluated at the query time) and a radius that grows with time-since-contact
under the standard kinematic bound

    u(t) = v_unc * (t - t_c) + (a_max * (t - t_c)**2) / 2

computed with exact integer arithmetic only. The `/2` above is not a float
division: `radius_at` computes it via `_ceil_div`, integer ceiling division,
which ROUNDS UP — the envelope is deliberately never smaller than the true
kinematic bound, only ever equal or (by at most 1 nm, from the ceiling)
larger. Growing the envelope only ever makes `APPARATUS_LIMITED` more
likely relative to a false ADMITTED/REJECTED, never the reverse, so
rounding this way costs nothing on the sound side and is (F1) never a
source of a false-admit or false-reject in `horizon.two_floor`.

On a new signal, `collapse` returns a NEW envelope (this module has no
mutable state) anchored at the new contact time with a fresh, directly
measured uncertainty radius, replacing the accumulated growth — the
cone-of-possibility collapsing back down on contact.
"""


def _ceil_div(a: int, b: int) -> int:
    """Exact integer ceiling division for a >= 0, b > 0 (never a float)."""
    return -(-a // b)


def _require_int(value, what):
    """Reject anything but an exact Python int at a public boundary — same
    rationale as `horizon.worldline._require_int` / `horizon.occultation.
    _require_int`: none of this module's own numeric parameters ever pass
    through a `Worldline.position_at` call (which guards `t_ns` and
    positions), so a caller-supplied float here would silently switch
    `radius_at`'s arithmetic to floating point and reintroduce the
    rounding gap the exact-integer envelope exists to remove."""
    if not isinstance(value, int):
        raise TypeError(f"{what} must be an exact int, got {type(value).__name__}: {value!r}")
    return value


class TrajectoryEnvelope:
    """`nominal`: a `Worldline` (e.g. `LinearWorldline`) giving the
    best-estimate center position at any time. `t_c`: the last contact
    time (ns) this envelope's growth is measured from. `v_unc_nm_per_ns`:
    an exact-integer bound on how much the true position can diverge from
    `nominal` per ns of elapsed time (velocity-uncertainty term).
    `a_max_nm_per_ns2`: an exact-integer bound on the ship's maximum
    acceleration (maneuver capability) driving the quadratic growth term.
    `u_measured_nm`: the baseline (light-delay-corrected, measured)
    uncertainty radius AT `t_c` itself — 0 for a perfect fix, otherwise the
    instrument's own residual uncertainty."""

    def __init__(self, nominal, t_c: int, v_unc_nm_per_ns: int,
                 a_max_nm_per_ns2: int, u_measured_nm: int = 0):
        self.nominal = nominal
        self.t_c = _require_int(t_c, "t_c")
        self.v_unc = _require_int(v_unc_nm_per_ns, "v_unc_nm_per_ns")
        self.a_max = _require_int(a_max_nm_per_ns2, "a_max_nm_per_ns2")
        self.u_measured = _require_int(u_measured_nm, "u_measured_nm")

    def center_at(self, t_ns: int):
        return self.nominal.position_at(t_ns)

    def radius_at(self, t_ns: int) -> int:
        _require_int(t_ns, "t_ns")
        dt = t_ns - self.t_c
        if dt < 0:
            raise ValueError("query time before this envelope's contact time")
        accel_term = _ceil_div(self.a_max * dt * dt, 2)
        return self.u_measured + self.v_unc * dt + accel_term

    def collapse(self, t_new: int, nominal_after, u_measured_nm: int,
                 v_unc_nm_per_ns=None, a_max_nm_per_ns2=None) -> "TrajectoryEnvelope":
        """A fresh envelope anchored at a new contact: the growth from
        `self` is discarded (not carried forward) and replaced by
        `u_measured_nm`, the directly measured (light-delay-corrected)
        uncertainty at `t_new`. `nominal_after` is the new best-estimate
        worldline going forward (typically re-derived from the new fix and
        an updated velocity estimate). `v_unc`/`a_max` default to this
        envelope's values if not given a fresh estimate."""
        return TrajectoryEnvelope(
            nominal_after, t_new,
            self.v_unc if v_unc_nm_per_ns is None else v_unc_nm_per_ns,
            self.a_max if a_max_nm_per_ns2 is None else a_max_nm_per_ns2,
            u_measured_nm=u_measured_nm,
        )
