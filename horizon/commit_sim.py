"""World model driving a commitment session. [HEURISTIC - located warning]

Located warning: this simulator COMPUTES round timings (challenge at
t0 + k*DT_ROUND_NS, response a fixed processing delay later) rather than
measuring them, and derives all secrets/challenges deterministically from
the frozen seed. It exists so the SOUND gates in `horizon.commitment`
have an honest (or deliberately cheating) world to run in. It is not on
the trusted path: verification code never imports this module.

Roles:
  HONEST      - answers every round with the true secrets; reveals (b, a_0..a_K).
  CHEAT_FLIP  - answers every round honestly (it cannot rewrite history),
                then at reveal claims b' = 1 - b and back-solves a_0' from
                round 0 (a_0' = y_0 - b'*r_0 mod P). Because rounds 1..K
                were already answered with the true a_0, the revealed
                chain is inconsistent at round 1 - which is exactly what
                verify_reveal must catch.
"""
from .commitment import (P_FIELD, SITE_1, SITE_2, DT_RESP_NS, K_SUSTAIN,
                         DT_ROUND_NS, SEED_H2, derive_secrets,
                         derive_challenges, commit_response, sustain_response,
                         chain_transcript)

HONEST = "HONEST"
CHEAT_FLIP = "CHEAT_FLIP"

RESPONSE_PROC_NS = 10  # fixed in-window processing delay (world model)


def run_session(role: str, b: int, seed: str = SEED_H2,
                k_sustain: int = K_SUSTAIN,
                site_1=SITE_1, site_2=SITE_2,
                dt_round_ns: int = DT_ROUND_NS,
                t0_ns: int = 0) -> dict:
    """Drive a full commit -> sustain -> reveal session. Deterministic."""
    secrets = derive_secrets(seed, k_sustain)
    challenges = derive_challenges(seed, k_sustain)

    rounds = []
    for k in range(k_sustain + 1):
        site = site_1 if k % 2 == 0 else site_2
        t_challenge = t0_ns + k * dt_round_ns
        t_response = t_challenge + RESPONSE_PROC_NS
        if k == 0:
            y = commit_response(secrets[0], b, challenges[0])
        else:
            y = sustain_response(secrets[k], secrets[k - 1], challenges[k])
        rounds.append({"k": k, "site_nm": list(site), "r": challenges[k],
                       "y": y, "t_challenge_ns": t_challenge,
                       "t_response_ns": t_response})

    t_commit = rounds[0]["t_challenge_ns"]
    t_reveal = t0_ns + (k_sustain + 1) * dt_round_ns

    if role == HONEST:
        reveal = {"b": b, "secrets": list(secrets)}
    elif role == CHEAT_FLIP:
        b_flip = 1 - b
        a0_forged = (rounds[0]["y"] - b_flip * challenges[0]) % P_FIELD
        reveal = {"b": b_flip, "secrets": [a0_forged] + list(secrets[1:])}
    else:
        raise ValueError(f"unknown role: {role}")

    return {"rounds": rounds,
            "transcript_hashes": chain_transcript(rounds),
            "reveal": reveal,
            "t_commit_ns": t_commit,
            "t_reveal_ns": t_reveal,
            "binding_duration_ns": t_reveal - t_commit,
            "role": role, "seed": seed}
