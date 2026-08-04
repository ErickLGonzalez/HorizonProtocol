"""The unified latency-budget gate.  [SOUND]

One predicate serves both deep-space tasks:

  (a) AUTHENTICATED TELEMETRY: given a packet claiming emission at (t0, p_src)
      and received at (t_recv, p_dst), is the arrival consistent with a vacuum
      light path from the claimed source worldline? A packet that arrives
      *earlier* than light permits from its claimed origin is forged.

  (b) TRAJECTORY ATTESTATION: given a challenge issued at (t_c, p_verifier) and
      a response received at (t_r, p_verifier), the round-trip time bounds the
      prover's distance TWO-SIDED, closing one specific misrepresentation
      direction (see erratum 2 for exactly which, and its honest limit): a
      prover whose TRUE distance is FARTHER than its claim cannot physically
      respond fast enough to meet the nearer claim's round trip, and is
      REJECTED regardless of how promptly it answers ("too slow for the
      claimed distance"). A response arriving impossibly fast for the claim
      is REJECTED on the ordinary FTL floor. Only a response landing in the
      narrow window around the exact round-trip requirement, once clock
      uncertainty and a declared resolve slack are accounted for, attests the
      claimed position under that (registered, not universal - see erratum 2)
      threat model.

Both reuse the exact vacuum-c floor from `horizon.geometry`/`horizon.distance`
directly - no reimplementation of the ceiling-search arithmetic. In vacuum
c_eff = 1 (H5/H6's fiber loophole, c_eff < 1, does not apply in space). A
declared clock-uncertainty `u_ns` is applied in the claimant's favour on
whichever side of a boundary benefits them; a receipt whose adjusted time
falls within `resolve_ns` of a required floor is APPARATUS_LIMITED rather
than REJECTED - never a silent PASS on an unresolvable margin.

(Erratum 1: an earlier version of this module compared a SQUARED margin
(`(c*eff)^2 - dist^2`, units nm^2) against a `resolve_ns2` parameter whose
name implied nanoseconds-squared. Because that margin scales quadratically
with distance while a clock uncertainty of U nanoseconds only ever shifts it
by approximately `2 * C^2 * required_ns * U` near the boundary - not a fixed
`U^2` - a `resolve_ns2` value sized to represent a real, small clock
uncertainty (e.g. derived by literally squaring a nanosecond figure) was
astronomically smaller than the interplanetary-scale margin and therefore had
no practical effect: the APPARATUS_LIMITED band would not trigger for any
realistic clock uncertainty. Every gate in this module now compares
NANOSECOND quantities directly - `dt_adjusted_ns` against an exact integer
`required_ns` floor - exactly mirroring `horizon.measure`'s dual-floor design
in H5/H6, which never compares squared quantities for a classification
decision either.

Erratum 2: an earlier version of `trajectory_attested` checked ONLY the lower
("too fast") bound, on the reasoning - borrowed uncritically from
`telemetry_consistent`, where it is correct - that arriving later than the
minimum is never itself suspicious. For ROUND-TRIP attestation this reasoning
does not fully transfer, but the fix has a precise, asymmetric scope - it is
NOT "both misrepresentation directions are now closed":

  - A prover whose TRUE distance is FARTHER than its claim (e.g. genuinely at
    Mars, claiming to be co-located with the verifier) CANNOT speed up its
    response beyond its own true physical minimum - responding as fast as
    physically possible, its RTT already exceeds what the nearer claim
    allows. The upper ("too slow") bound added here closes this direction
    soundly, matching H3's original terrestrial `deadline` gate's intended
    purpose (`docs/h3-spec.md`): "a farther prover cannot meet this."

  - A prover whose TRUE distance is CLOSER than its claim (e.g. co-located
    with the verifier, claiming to be on Mars) can ALWAYS defeat ANY
    combination of timing bounds by simply delaying its response until the
    RTT matches the claimed (farther) distance's requirement - nothing
    prevents a prover from choosing to respond later than it could. This is
    not an implementation gap closeable by more gate math: it is a
    structural limitation of round-trip-timing-only distance bounding
    (present in the classical distance-bounding literature generally, not
    specific to this repository). `tests/test_h7b_latency_gate.py`'s
    `test_registered_limitation_claiming_farther_than_true_is_not_caught`
    demonstrates this as a passing test, deliberately, rather than leaving
    it silently assumed solved - the same discipline H3-C uses for the
    classical position-verification collusion break. Closing this direction
    would require binding the round trip to an unpredictable, per-round
    challenge the prover cannot precompute (a rapid-bit exchange, not
    modeled here) or leaning on the quantum layer's own properties (BE(Q)/
    no-cloning) - out of scope for this classical timing gate; see
    `docs/h7-spec.md`, section 3b.)
"""
from .distance import min_round_trip_ns
from .geometry import min_light_time_ns


def telemetry_consistent(t0, p_src, t_recv, p_dst, u_ns, resolve_ns=0):
    """(a) Packet-origin consistency. Exact integers, vacuum (c_eff=1)."""
    dt = t_recv - t0
    if dt < 0:
        return {"verdict": "REJECTED",
                "witness": {"reason": "arrival_before_emission", "dt_ns": dt}}
    dt_adjusted = dt + u_ns  # clock error helps the (honest or dishonest) claimant
    required_ns = min_light_time_ns(p_src, p_dst)
    w = {"dt_ns": dt, "u_ns": u_ns, "dt_adjusted_ns": dt_adjusted,
         "required_ns": required_ns, "resolve_ns": int(resolve_ns),
         "margin_ns": dt_adjusted - required_ns}
    if dt_adjusted < required_ns - resolve_ns:
        return {"verdict": "REJECTED", "witness": w}
    if dt_adjusted < required_ns:
        return {"verdict": "APPARATUS_LIMITED", "witness": w}
    return {"verdict": "ADMITTED", "witness": w}


def trajectory_attested(t_challenge, p_verifier, t_response,
                        p_claimed, proc_ns, u_ns, resolve_ns=0):
    """(b) Round-trip position attestation, TWO-SIDED (see module docstring,
    erratum 2). Exact integers, vacuum.

    `required_ns` is the exact round-trip time to `p_claimed`
    (`horizon.distance.min_round_trip_ns`, reused unmodified). The response,
    adjusted for processing delay and clock uncertainty, must land within
    `resolve_ns` of `required_ns` on EITHER side to be APPARATUS_LIMITED, and
    exactly at or beyond it (within that band) to be ADMITTED:

      dt = (t_response - t_challenge) - proc_ns
      too fast to attest the claimed distance -> dt + u_ns < required_ns - resolve_ns
      too slow to attest the claimed distance -> dt - u_ns > required_ns + resolve_ns

    A prover whose TRUE distance is FARTHER than `p_claimed` is soundly
    caught by the upper check: it cannot respond faster than its own true
    round trip requires, which already exceeds what the nearer claim allows.
    A prover whose TRUE distance is CLOSER than `p_claimed` can still defeat
    this (and any timing-only check) by delaying its response to match the
    claimed distance's requirement - this is a registered, structural
    limitation, not solved by this function; see the module docstring,
    erratum 2, and `tests/test_h7b_latency_gate.py`'s
    `test_registered_limitation_claiming_farther_than_true_is_not_caught`.
    """
    rtt = t_response - t_challenge
    if rtt < 0:
        return {"verdict": "REJECTED",
                "witness": {"reason": "response_before_challenge", "rtt_ns": rtt}}
    dt = rtt - proc_ns
    dt_adjusted_low = dt + u_ns    # benefit of doubt against the lower (too-fast) bound
    dt_adjusted_high = dt - u_ns   # benefit of doubt against the upper (too-slow) bound
    required_ns = min_round_trip_ns(p_verifier, p_claimed)
    w = {"rtt_ns": rtt, "proc_ns": proc_ns, "u_ns": u_ns, "dt_ns": dt,
         "dt_adjusted_low_ns": dt_adjusted_low, "dt_adjusted_high_ns": dt_adjusted_high,
         "required_ns": required_ns, "resolve_ns": int(resolve_ns),
         "margin_low_ns": dt_adjusted_low - required_ns,
         "margin_high_ns": dt_adjusted_high - required_ns}
    if dt_adjusted_low < required_ns - resolve_ns:
        return {"verdict": "REJECTED", "witness": {**w, "reason": "too_fast_for_claimed_distance"}}
    if dt_adjusted_high > required_ns + resolve_ns:
        return {"verdict": "REJECTED", "witness": {**w, "reason": "too_slow_for_claimed_distance"}}
    if dt_adjusted_low < required_ns or dt_adjusted_high > required_ns:
        return {"verdict": "APPARATUS_LIMITED", "witness": w}
    return {"verdict": "ADMITTED", "witness": w}
