"""Idealized qubit-measurement simulator.  [HEURISTIC - QUARANTINED]

LOCATED WARNING: this is NOT a quantum device and NOT a security proof. It is a
DETERMINISTIC model of idealized BB84-style measurement outcomes used only to
exercise the protocol plumbing (challenge issuance, basis matching, response
scoring) end to end. No randomness is used: 'measurement' outcomes are derived
from SHA-256 of a frozen seed and round index, so runs are bit-reproducible.
Real QPV outcomes are probabilistic and hardware-dependent; a genuine
implementation replaces this module wholesale (see docs/h7-spec.md, Quantum
interface). No verifier imports this module (H7-D asserts it).

Model: each round the verifier picks a basis b in {0,1} and a bit x in {0,1}.
An HONEST prover at the right place measures in the correct basis and returns x
(success). A basis-mismatched measurement returns the correct bit only with
probability 1/2 -> modeled deterministically as 'correct iff hash bit set'.
"""
import hashlib

SEED = "H7-QUBIT-SIM-FROZEN-v1"


def _bit(tag, i):
    h = hashlib.sha256(f"{SEED}:{tag}:{i}".encode()).digest()
    return h[0] & 1


def challenge(round_i):
    """Deterministic (basis, bit) challenge for a round."""
    return _bit("basis", round_i), _bit("x", round_i)


def honest_response(round_i):
    """Honest prover measuring in the correct basis returns the correct bit."""
    _, x = challenge(round_i)
    return x


def mismatched_response(round_i):
    """Wrong-basis measurement: correct only half the time (deterministic)."""
    _, x = challenge(round_i)
    return x if _bit("mismatch", round_i) else (x ^ 1)


def score(rounds, responder):
    """Fraction of correct responses over `rounds` rounds, as (correct, total)."""
    correct = sum(1 for i in range(rounds)
                  if responder(i) == challenge(i)[1])
    return correct, rounds
