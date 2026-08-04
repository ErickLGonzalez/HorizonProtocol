"""Quantum optical channel: DOCUMENTED INTERFACE, not an implementation. [SPEC]

This module defines the abstract boundary a real quantum layer must satisfy so
that the classical H7 scaffolding (latency gate + BE(Q) tracker) composes with
it. It contains NO physics and makes NO security claim. A genuine deployment
supplies a concrete channel meeting this contract (e.g. a Deep Space Quantum
Link-class optical terminal); the qubit_sim module is a HEURISTIC stand-in that
also nominally satisfies it for plumbing tests.

Contract (registered assumptions A1-A4):
  A1  The channel delivers a quantum system from a verifier to the prover at a
      speed <= c (vacuum: = c). Timing is measured on the exact ns lattice.
  A2  The prover cannot clone the quantum system (no-cloning).
  A3  A colluding adversary's ability to spoof depends on pre-shared
      entanglement bounded by Q (BE(Q)); soundness holds for Q < Q_secure.
  A4  Loss is handled by a loss-tolerant protocol (e.g. SWAP / HOM
      interference) so that claimed-loss attacks are detectable.

Interface:
  issue_challenge(round_i) -> opaque challenge token
  measure(round_i, at_correct_location: bool) -> response bit
  A real channel returns physical measurement outcomes; the stand-in returns
  deterministic ones. The classical gate never trusts the *value* for security
  beyond the BE(Q) accounting; security rests on timing (latency_gate) AND the
  bounded-entanglement bound (beq), per A1-A4.
"""

REGISTERED_ASSUMPTIONS = {
    "A1": "channel speed <= c; vacuum path => = c; ns-lattice timing",
    "A2": "no-cloning of the delivered quantum system",
    "A3": "collusion resistance holds for pre-shared entanglement Q < Q_secure",
    "A4": "loss-tolerant protocol so claimed-loss attacks are detectable",
}


class QuantumChannel:
    """Abstract contract. Concrete subclasses implement `issue`/`respond`."""
    def issue(self, round_i):
        raise NotImplementedError("supply a concrete quantum channel")

    def respond(self, round_i, at_correct_location):
        raise NotImplementedError("supply a concrete quantum channel")


class SimulatedChannel(QuantumChannel):
    """HEURISTIC stand-in wrapping qubit_sim. Not a quantum device."""
    def __init__(self):
        from . import qubit_sim
        self._sim = qubit_sim

    def issue(self, round_i):
        return self._sim.challenge(round_i)

    def respond(self, round_i, at_correct_location):
        return (self._sim.honest_response(round_i) if at_correct_location
                else self._sim.mismatched_response(round_i))
