"""Distance bounding: RTT bound math, multilateration consistency. [SOUND]

Brands-Chaum-style timing gates on the exact nm/ns lattice. For a
verifier V issuing a challenge at t_c and receiving the response at t_r,
with declared processing delay PROC:

  RTT = t_r - t_c

Two exact gates per verifier against a claimed position P:

  ftl_floor:  (C * (RTT - PROC))**2 >= 4 * dist2(V, P)
              (RTT - PROC >= 2*d/c: the response cannot have covered the
              round trip faster than light — same physics as H1-E's
              forged receipt, in RTT form)
  deadline:   RTT <= 2 * min_light_time_ns(V, P) + PROC
              (the response arrived as fast as a prover AT P could
              answer; a farther prover cannot meet this)

A claim is ADMITTED by a verifier iff both gates hold, REJECTED otherwise
with the violated gate and its exact integers. Multilateration ADMITS a
claim iff every verifier admits it.

This module is on the trusted path: it never imports the world-model
module; the H3-B suite asserts this. The known classical collusion
break (Chandran-Goyal-Moriarty-Ostrovsky 2009) is demonstrated, on
purpose, in gate H3-C — see docs/h3-spec.md, claim-scope firewall.
"""
import math

from .geometry import C_NM_PER_NS, dist2, min_light_time_ns

# ---- frozen parameters (H3) -------------------------------------------------
V1 = (0, 0, 0)
V2 = (20_000_000_000_000, 0, 0)
V3 = (0, 20_000_000_000_000, 0)
V4 = (0, 0, 20_000_000_000_000)
VERIFIERS = {"V1": V1, "V2": V2, "V3": V3, "V4": V4}
P_CLAIM = (6_000_000_000_000, 6_000_000_000_000, 0)
PROC_NS = 25
SEED_H3 = "H3-FROZEN-SEED-v1"


def min_round_trip_ns(v_pos, p_pos) -> int:
    """Smallest integer T with (C*T)^2 >= 4*dist2 (exact round-trip floor).

    Note min_round_trip_ns <= 2*min_light_time_ns for the same pair, so
    any RTT below this floor is also strictly below 2*min_light_time_ns.
    """
    d2 = 4 * dist2(v_pos, p_pos)
    if d2 == 0:
        return 0
    r = math.isqrt(d2)
    if r * r < d2:
        r += 1
    t = -(-r // C_NM_PER_NS)
    while t > 0 and (C_NM_PER_NS * (t - 1)) ** 2 >= d2:
        t -= 1
    while (C_NM_PER_NS * t) ** 2 < d2:
        t += 1
    return t


def deadline_ns(v_pos, p_pos, proc_ns: int) -> int:
    """Latest admissible response time for a prover AT the claimed position."""
    return 2 * min_light_time_ns(v_pos, p_pos) + proc_ns


def rtt_bound_witness(rtt_ns: int, proc_ns: int, v_pos, p_claim) -> dict:
    """Single-verifier verdict with exact integer witnesses for both gates."""
    dt = rtt_ns - proc_ns
    d2_claim = dist2(v_pos, p_claim)
    lhs = (C_NM_PER_NS * dt) ** 2 if dt >= 0 else None
    rhs = 4 * d2_claim
    mlt = min_light_time_ns(v_pos, p_claim)
    dl = 2 * mlt + proc_ns

    base = {"rtt_ns": int(rtt_ns), "proc_ns": int(proc_ns),
            "rtt_minus_proc_ns": dt, "c_nm_per_ns": C_NM_PER_NS,
            "lhs_c_dt_squared": lhs, "rhs_4_dist_squared_nm2": rhs,
            "min_light_time_ns": mlt, "deadline_ns": dl}

    if dt < 0 or lhs < rhs:
        base.update({"gate": "ftl_floor", "verdict": "REJECTED",
                     "detail": "response faster than light permits for the "
                               "claimed position (RTT - PROC < 2*d/c)"})
        return base
    if rtt_ns > dl:
        base.update({"gate": "deadline", "verdict": "REJECTED",
                     "detail": "response later than a prover at the claimed "
                               "position could answer (RTT > 2*mlt + PROC)"})
        return base
    base.update({"gate": "rtt_bound", "verdict": "ADMITTED"})
    return base


def multilateration(measurements: dict, proc_ns: int, p_claim,
                    verifiers: dict = None) -> dict:
    """Verify a position claim against all verifiers' RTT measurements.

    measurements: {verifier_id: rtt_ns}. ADMITTED iff every verifier
    admits; else REJECTED naming the failing verifiers with exact
    witnesses.
    """
    verifiers = VERIFIERS if verifiers is None else verifiers
    per_verifier, failing = {}, []
    for vid in sorted(verifiers):
        w = rtt_bound_witness(measurements[vid], proc_ns, verifiers[vid], p_claim)
        per_verifier[vid] = w
        if w["verdict"] != "ADMITTED":
            failing.append(vid)
    return {"verdict": "ADMITTED" if not failing else "REJECTED",
            "failing_verifiers": failing,
            "per_verifier": per_verifier,
            "p_claim_nm": [int(x) for x in p_claim]}
