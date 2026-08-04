"""Bounded-entanglement security tracker.  [SOUND]

Classical position verification is broken by colluding adversaries with NO
entanglement (Chandran-Goyal-Moriarty-Ostrovsky 2009). Quantum position
verification restores security PROVIDED the adversary's pre-shared entanglement
is bounded: this is the BE(Q) model. Unconditional QPV is impossible (attacks
exist using exponential entanglement; a linear lower bound is also known).

This module does NOT implement quantum optics. It tracks the SECURITY PARAMETER
exactly: for a protocol committing k qubits with a per-round soundness gap, it
computes (in exact integer / rational arithmetic) the adversary's success bound
and the entanglement threshold Q below which the protocol is sound. The emitted
verdict is CONDITIONAL(BE(Q)) with Q named. All arithmetic is exact.
"""
from fractions import Fraction


def adversary_success_bound(k_committed, per_round_gap_num, per_round_gap_den):
    """Exact bound on a bounded-entanglement adversary's acceptance probability.

    Model: for a parallel-committed QPV protocol, fixing a threshold k on
    successfully committed qubits yields adversarial acceptance that decays
    exponentially in k (Escola-Farras et al. 2026). We represent the per-round
    honest advantage as an exact fraction p = num/den in (0,1); the adversary
    bound over k independent rounds is p^k (exact rational).
    """
    p = Fraction(per_round_gap_num, per_round_gap_den)
    if not (0 < p < 1):
        raise ValueError("per-round gap must be a fraction strictly in (0,1)")
    bound = p ** k_committed
    return bound  # exact Fraction


def entanglement_threshold(k_committed):
    """The BE(Q) threshold: known results give a LINEAR lower bound on the
    entanglement (in the classical-information size) needed to attack, and an
    exponential general upper bound. We record the linear security threshold
    Q_secure = k (qubits of pre-shared entanglement below which soundness holds
    for the linear-lower-bound family) as an exact integer parameter."""
    return {"Q_secure_linear": k_committed,
            "attack_general_upper": f"exponential in k (=2^O({k_committed}))",
            "note": "sound for adversaries pre-sharing < Q_secure_linear EPR pairs"}


def beq_verdict(k_committed, per_round_gap_num, per_round_gap_den,
                target_soundness_num=1, target_soundness_den=10**9):
    """Emit a CONDITIONAL(BE(Q)) verdict with exact witnesses."""
    bound = adversary_success_bound(k_committed, per_round_gap_num,
                                    per_round_gap_den)
    target = Fraction(target_soundness_num, target_soundness_den)
    meets = bound <= target
    thr = entanglement_threshold(k_committed)
    return {
        "verdict": "CONDITIONAL_BE_Q" if meets else "INSUFFICIENT_ROUNDS",
        "conditional_on": "bounded pre-shared entanglement (BE(Q) model)",
        "k_committed": k_committed,
        "adversary_bound_num": bound.numerator,
        "adversary_bound_den": bound.denominator,
        "adversary_bound_float": float(bound),
        "target_soundness_float": float(target),
        "meets_target": meets,
        "entanglement_threshold": thr,
        "citations": ["CGMO2009 (classical impossibility)",
                      "Kent-Munro-Spiller 2011 (quantum tagging)",
                      "Escola-Farras et al. 2026 (loss-tolerant single-shot BE QPV)"],
    }
