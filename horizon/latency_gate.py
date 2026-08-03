"""The unified latency-budget gate.  [SOUND]

One predicate serves both deep-space tasks:

  (a) AUTHENTICATED TELEMETRY: given a packet claiming emission at (t0, p_src)
      and received at (t_recv, p_dst), is the arrival consistent with a vacuum
      light path from the claimed source worldline? A packet that arrives
      *earlier* than light permits from its claimed origin is forged.

  (b) TRAJECTORY ATTESTATION: given a challenge issued at (t_c, p_verifier) and
      a response received at (t_r, p_verifier), the round-trip time bounds the
      prover's distance from below; a response arriving before the round trip
      to the claimed position is impossible -> the claimed position is not
      attested. (Only the lower/"too fast" bound is checked - a response
      arriving LATER than the claimed distance would require is not itself
      evidence of misrepresentation at interplanetary scale, where legitimate
      processing/queueing variance routinely exceeds any short constant
      `proc_ns`; H3's terrestrial distance-bounding deadline bound does not
      transfer to this setting, and is deliberately not reproduced here.)

Both reuse the exact vacuum-c floor from `horizon.geometry`/`horizon.distance`
directly - no reimplementation of the ceiling-search arithmetic. In vacuum
c_eff = 1 (H5/H6's fiber loophole, c_eff < 1, does not apply in space). A
declared clock-uncertainty `u_ns` is applied in the claimant's favour; a
receipt whose adjusted time falls short of the required floor by less than
`resolve_ns` is APPARATUS_LIMITED rather than REJECTED - never a silent PASS
on an unresolvable margin.

(Erratum: an earlier version of this module compared a SQUARED margin
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
decision either.)
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
    """(b) Round-trip position attestation (lower bound only - see module
    docstring). Exact integers, vacuum.

    ADMITTED iff `(t_response - t_challenge - proc_ns) + u_ns` is at or
    above the exact minimal round-trip time to `p_claimed`
    (`horizon.distance.min_round_trip_ns`, reused unmodified). A response
    that could not have covered the round trip even with the full
    clock-uncertainty benefit of the doubt is REJECTED: the claimed
    position is not attested.
    """
    rtt = t_response - t_challenge
    if rtt < 0:
        return {"verdict": "REJECTED",
                "witness": {"reason": "response_before_challenge", "rtt_ns": rtt}}
    dt_adjusted = (rtt - proc_ns) + u_ns
    required_ns = min_round_trip_ns(p_verifier, p_claimed)
    w = {"rtt_ns": rtt, "proc_ns": proc_ns, "u_ns": u_ns,
         "dt_adjusted_ns": dt_adjusted, "required_ns": required_ns,
         "resolve_ns": int(resolve_ns), "margin_ns": dt_adjusted - required_ns}
    if dt_adjusted < required_ns - resolve_ns:
        return {"verdict": "REJECTED", "witness": w}
    if dt_adjusted < required_ns:
        return {"verdict": "APPARATUS_LIMITED", "witness": w}
    return {"verdict": "ADMITTED", "witness": w}
