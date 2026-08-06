"""Exact one-way light-time signal delivery, with occultation blackout
blocking.  [SOUND]

SP-1 (see docs/sp1-spec.md). Reuses `horizon.geometry.min_light_time_ns`
(frozen, unmodified — imported, never redefined) for the exact
ceil(dist/c) one-way light time, and `horizon.worldline`'s
`Worldline.position_at` for exact positions.

This models a signal emitted by a MOVING node (e.g. a ship, on a
`LinearWorldline`) and received by a STATIONARY node (e.g. a ground
station, a `FixedWorldline`): the light time from a moving emitter to a
receiver whose position does not change during transit is exactly
`min_light_time_ns(p_emit, p_receive)` — no light-time equation iteration
is needed for that case (iteration would only be required if the receiver
ALSO moved appreciably during the flight, which SP-1 does not model).
"""
from horizon.geometry import min_light_time_ns


def delivery_time_ns(t_emit: int, emitter, receiver, occultation=None) -> int:
    """Delivery time (ns) of a signal emitted by `emitter` at `t_emit` and
    received by `receiver`, both `Worldline`s.

    `occultation`, if given, is an inclusive `(t_enter, t_exit)` pair (see
    `horizon.occultation.occultation_interval`): `is_link_down` is True for
    every `t` in `[t_enter, t_exit]`, so `t_exit` itself is still blocked
    and the link only reopens at `t_exit + 1`, the first unblocked instant
    on this integer lattice. If `t_emit` falls inside `[t_enter, t_exit]`,
    line-of-sight was down at the moment of emission, so the signal cannot
    actually leave until then — delivery is
    `max(t_emit + light_time_at_emission, (t_exit + 1) +
    light_time_at_reopen)`, i.e. never earlier than a signal re-emitted the
    instant the link comes back up. Outside the occultation window (or if
    none is given), delivery is the plain `t_emit + light_time_at_emission`."""
    p_emit = emitter.position_at(t_emit)
    p_recv = receiver.position_at(t_emit)
    naive = t_emit + min_light_time_ns(p_emit, p_recv)
    if occultation is None:
        return naive
    t_enter, t_exit = occultation
    if t_enter <= t_emit <= t_exit:
        t_reopen = t_exit + 1
        p_emit_reopen = emitter.position_at(t_reopen)
        p_recv_reopen = receiver.position_at(t_reopen)
        from_reopen = t_reopen + min_light_time_ns(p_emit_reopen, p_recv_reopen)
        return max(naive, from_reopen)
    return naive
