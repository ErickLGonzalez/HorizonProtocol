"""Relativistic commitment: chain algebra, timing gates, verification. [SOUND]

Kent/Lunghi-style two-agent sustained bit commitment, modeled exactly.
All chain arithmetic is over the Mersenne prime field GF(2^61 - 1); all
timing gates reuse the exact integer light-cone kernel from
`horizon.geometry`. No floats, no tolerances.

This module is on the trusted path: it never imports a world-model
module. What it certifies is (a) algebraic consistency of the
commit-sustain-reveal chain and (b) the geometric precondition that the
two agent sites are causally isolated within each response window. It
does NOT constitute a security proof of binding against arbitrary
adversaries (see docs/h2-spec.md, "Claim-scope firewall").
"""
import hashlib

from .events import canonical
from .geometry import admissibility_witness, min_light_time_ns

# ---- frozen parameters (H2) -------------------------------------------------
P_FIELD = 2 ** 61 - 1                       # Mersenne prime; chain arithmetic mod P
SITE_1 = (0, 0, 0)                          # nm
SITE_2 = (30_000_000_000_000, 0, 0)         # nm  (30 km along x)
DT_RESP_NS = 50_000                         # response window (ns)
K_SUSTAIN = 8                               # sustain rounds
DT_ROUND_NS = 40_000                        # round period (ns)
SEED_H2 = "H2-FROZEN-SEED-v1"


# ---- deterministic derivation ----------------------------------------------
def derive_field_element(seed: str, label: str, counter: int) -> int:
    """SHA-256(seed || label || counter) reduced mod P_FIELD (deterministic)."""
    h = hashlib.sha256(f"{seed}||{label}||{counter}".encode("utf-8")).digest()
    return int.from_bytes(h, "big") % P_FIELD


def derive_secrets(seed: str, k_sustain: int) -> list:
    """Committer secrets a_0 .. a_K."""
    return [derive_field_element(seed, "secret-a", k) for k in range(k_sustain + 1)]


def derive_challenges(seed: str, k_sustain: int) -> list:
    """Verifier challenges r_0 .. r_K."""
    return [derive_field_element(seed, "challenge-r", k) for k in range(k_sustain + 1)]


# ---- chain algebra ----------------------------------------------------------
def commit_response(a0: int, b: int, r0: int) -> int:
    """Round 0:  y_0 = (a_0 + b * r_0) mod P."""
    if b not in (0, 1):
        raise ValueError("committed bit must be 0 or 1")
    return (a0 + b * r0) % P_FIELD


def sustain_response(ak: int, ak_prev: int, rk: int) -> int:
    """Round k>=1:  y_k = (a_k + a_{k-1} * r_k) mod P."""
    return (ak + ak_prev * rk) % P_FIELD


def verify_reveal(rounds: list, b: int, secrets: list, k_sustain: int) -> dict:
    """Recompute every chain equation against the transcript.

    `rounds` is a list of dicts with integer fields "k", "r", "y".
    `k_sustain` is the protocol's frozen K: rounds must be exactly the
    contiguous set {0, 1, ..., k_sustain} (no truncation, gaps,
    duplicates, or reordered/negative indices) before any algebra is
    checked, else a short or skipped-round transcript could otherwise be
    ADMITTED. `secrets` is the revealed a_0..a_K. Verdict: ADMITTED, or
    REJECTED with the first failing round index and both integer sides
    as the exact witness.
    """
    if b not in (0, 1):
        return {"verdict": "REJECTED",
                "witness": {"gate": "revealed_bit_domain", "b": b}}
    expected_count = k_sustain + 1
    if len(rounds) != expected_count:
        return {"verdict": "REJECTED",
                "witness": {"gate": "round_count",
                            "expected": expected_count, "got": len(rounds)}}
    ks = [rec["k"] for rec in rounds]
    if sorted(ks) != list(range(expected_count)):
        return {"verdict": "REJECTED",
                "witness": {"gate": "round_sequence",
                            "expected": list(range(expected_count)),
                            "got": ks}}
    if len(secrets) != len(rounds):
        return {"verdict": "REJECTED",
                "witness": {"gate": "secret_count",
                            "expected": len(rounds), "got": len(secrets)}}
    for rec in rounds:
        k, r, y = rec["k"], rec["r"], rec["y"]
        if k == 0:
            expected = commit_response(secrets[0], b, r)
        else:
            expected = sustain_response(secrets[k], secrets[k - 1], r)
        if expected != y:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "chain_consistency",
                                "failing_round": k,
                                "lhs_transcript_y": y,
                                "rhs_recomputed": expected,
                                "field_prime": P_FIELD}}
    return {"verdict": "ADMITTED", "rounds_checked": len(rounds)}


# ---- timing / isolation gates ----------------------------------------------
def isolation_gate(site_a, site_b, dt_resp_ns: int) -> dict:
    """Causal-isolation precondition for one response window.

    PASS iff a signal emitted at one site CANNOT reach the other within
    the response window: NOT causally_admissible(t, A, t + dt_resp, B),
    i.e. dt_resp_ns < min_light_time_ns(A, B), decided exactly.
    A configuration that fails this gate cannot support the binding
    claim: verdict APPARATUS_LIMITED (refuse to certify, never PASS).
    """
    mlt = min_light_time_ns(site_a, site_b)
    w = admissibility_witness(0, site_a, dt_resp_ns, site_b)
    isolated = not w["admissible"]
    return {
        "verdict": "PASS" if isolated else "APPARATUS_LIMITED",
        "dt_resp_ns": int(dt_resp_ns),
        "one_way_light_time_ns": mlt,
        "exact_witness": w,
        "detail": ("response window shorter than one-way light time; sites "
                   "causally isolated per window" if isolated else
                   "response window admits light-speed signalling between "
                   "sites; configuration cannot support the binding claim"),
    }


def sustained_isolation_gate(site_a, site_b, dt_round_ns: int,
                             dt_resp_ns: int) -> dict:
    """Causal-isolation precondition across the FULL sustained schedule.

    `isolation_gate` only rules out signalling within a single response
    window. But rounds recur every `dt_round_ns` at alternating sites, so
    a signal emitted at the very start of round k's window has until the
    close of round k+1's window - `dt_round_ns + dt_resp_ns` later - to
    arrive at the other site. PASS iff that longer interval is ALSO
    causally inadmissible: NOT causally_admissible(0, site_a,
    dt_round_ns + dt_resp_ns, site_b). A schedule that fails cannot
    support cross-round isolation: verdict APPARATUS_LIMITED (refuse to
    certify, never PASS).
    """
    total_ns = dt_round_ns + dt_resp_ns
    mlt = min_light_time_ns(site_a, site_b)
    w = admissibility_witness(0, site_a, total_ns, site_b)
    isolated = not w["admissible"]
    return {
        "verdict": "PASS" if isolated else "APPARATUS_LIMITED",
        "dt_round_ns": int(dt_round_ns),
        "dt_resp_ns": int(dt_resp_ns),
        "dt_round_plus_resp_ns": total_ns,
        "one_way_light_time_ns": mlt,
        "exact_witness": w,
        "detail": ("round period plus response window shorter than "
                   "one-way light time; consecutive rounds at alternating "
                   "sites remain causally isolated" if isolated else
                   "round period plus response window admits light-speed "
                   "signalling between sites before the next round's "
                   "deadline; schedule cannot support the binding claim"),
    }


def response_in_window(t_challenge_ns: int, t_response_ns: int,
                       dt_resp_ns: int) -> dict:
    """Exact check that a response lands inside its window."""
    dt = t_response_ns - t_challenge_ns
    ok = 0 <= dt < dt_resp_ns
    return {"verdict": "ADMITTED" if ok else "REJECTED",
            "dt_ns": dt, "window_ns": int(dt_resp_ns)}


# ---- transcript hash chain --------------------------------------------------
def round_record_hash(prev_hash_hex: str, record: dict) -> str:
    """h_k = SHA-256(h_{k-1} || canonical(record))."""
    h = hashlib.sha256()
    h.update(bytes.fromhex(prev_hash_hex))
    h.update(canonical(record))
    return h.hexdigest()


GENESIS_HASH = hashlib.sha256(b"H2-TRANSCRIPT-GENESIS").hexdigest()


def chain_transcript(rounds: list) -> list:
    """Compute the running hash chain over round records."""
    hashes, prev = [], GENESIS_HASH
    for rec in rounds:
        prev = round_record_hash(prev, rec)
        hashes.append(prev)
    return hashes


def verify_transcript_chain(rounds: list, claimed_hashes: list) -> dict:
    """Recompute the hash chain; REJECT at the first mismatching round."""
    prev = GENESIS_HASH
    for i, rec in enumerate(rounds):
        prev = round_record_hash(prev, rec)
        if i >= len(claimed_hashes) or prev != claimed_hashes[i]:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "transcript_hash_chain",
                                "failing_round": rec["k"],
                                "recomputed": prev,
                                "claimed": (claimed_hashes[i]
                                            if i < len(claimed_hashes) else None)}}
    return {"verdict": "ADMITTED", "rounds_checked": len(rounds)}
