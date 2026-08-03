"""World model for distance bounding sessions. [HEURISTIC - located warning]

Located warning: RTTs are COMPUTED, not measured. Every simulated
response respects the physical floor of its true signal path:

    RTT - PROC >= 2 * min_light_time_ns(V, agent_true_position)

(the simulator will DELAY a response, which physics allows, but never
produce one faster than light, which physics forbids). This module is a
world model only; the trusted verifier (`horizon.distance`) never
imports it.

Roles:
  HONEST         - prover truly at P_CLAIM; answers at its physical minimum.
  DISTANT        - prover truly ~5 km farther from every verifier; answers
                   at its physical minimum (it cannot answer faster).
  DECOY          - prover truly at DECOY_POS; delays to each verifier's
                   deadline when its geometry allows, but cannot meet
                   deadlines for verifiers it is farther from.
  COLLUDER_PAIR  - two pre-positioned agents sharing session material in
                   advance (Chandran-Goyal-Moriarty-Ostrovsky 2009 setting);
                   each answers the challenges arriving on its side,
                   delaying to the deadline so responses mimic a prover
                   at P_CLAIM. The classical attack this reproduces is
                   EXPECTED to succeed.
"""
import hashlib

from .distance import (P_CLAIM, PROC_NS, SEED_H3, VERIFIERS, deadline_ns)
from .geometry import dist2, min_light_time_ns

HONEST = "HONEST"
DISTANT = "DISTANT"
DECOY = "DECOY"
COLLUDER_PAIR = "COLLUDER_PAIR"

# Truly ~5 km from P_CLAIM along the ray away from the verifier centroid:
# strictly farther than P_CLAIM from ALL of V1..V4.
DISTANT_POS = (7_000_000_000_000, 7_000_000_000_000, -4_800_000_000_000)

# Decoy: nearer to V1/V2/V4 than P_CLAIM (can delay to their deadlines)
# but strictly farther from V3 (cannot meet V3's deadline).
DECOY_POS = (6_000_000_000_000, 0, 0)

# Colluders: each strictly closer to its covered subset than P_CLAIM is.
COLLUDER_A1 = (1_000_000_000_000, 1_000_000_000_000, 0)              # covers V1
COLLUDER_A2 = (10_000_000_000_000, 10_000_000_000_000, 5_000_000_000_000)  # covers V2,V3,V4
COLLUDER_COVERAGE = {"V1": "A1", "V2": "A2", "V3": "A2", "V4": "A2"}
COLLUDER_POSITIONS = {"A1": COLLUDER_A1, "A2": COLLUDER_A2}


def session_key(seed: str = SEED_H3) -> str:
    """Pre-shared session material (deterministic; models advance sharing)."""
    return hashlib.sha256(f"{seed}||session-key".encode()).hexdigest()


def _respond(true_pos, v_pos, proc_ns: int, delay_to_ns=None) -> int:
    """Physically honest RTT from `true_pos`: floor is 2*mlt + proc;
    an optional target the agent delays to (never below the floor)."""
    floor = 2 * min_light_time_ns(v_pos, true_pos) + proc_ns
    if delay_to_ns is None:
        return floor
    return max(floor, delay_to_ns)


def run_session(role: str, proc_ns: int = PROC_NS, p_claim=P_CLAIM,
                verifiers: dict = None, seed: str = SEED_H3) -> dict:
    """Produce {verifier_id: rtt_ns} measurements for the given role."""
    verifiers = VERIFIERS if verifiers is None else verifiers
    measurements, agent_positions = {}, {}

    for vid in sorted(verifiers):
        v = verifiers[vid]
        if role == HONEST:
            true_pos = p_claim
            rtt = _respond(true_pos, v, proc_ns)
        elif role == DISTANT:
            true_pos = DISTANT_POS
            rtt = _respond(true_pos, v, proc_ns)
        elif role == DECOY:
            true_pos = DECOY_POS
            rtt = _respond(true_pos, v, proc_ns,
                           delay_to_ns=deadline_ns(v, p_claim, proc_ns))
        elif role == COLLUDER_PAIR:
            agent = COLLUDER_COVERAGE[vid]
            true_pos = COLLUDER_POSITIONS[agent]
            rtt = _respond(true_pos, v, proc_ns,
                           delay_to_ns=deadline_ns(v, p_claim, proc_ns))
            agent_positions[vid] = {"agent": agent, "pos_nm": list(true_pos)}
        else:
            raise ValueError(f"unknown role: {role}")

        # world-model invariant: no simulated response is ever FTL for its
        # true path
        assert rtt - proc_ns >= 2 * min_light_time_ns(v, true_pos)
        measurements[vid] = rtt

    out = {"role": role, "seed": seed, "proc_ns": proc_ns,
           "measurements": measurements,
           "session_key": session_key(seed)}
    if role == COLLUDER_PAIR:
        out["agent_positions"] = agent_positions
        out["strictly_closer_check"] = {
            vid: dist2(COLLUDER_POSITIONS[COLLUDER_COVERAGE[vid]], verifiers[vid])
                 < dist2(p_claim, verifiers[vid])
            for vid in sorted(verifiers)}
    return out
