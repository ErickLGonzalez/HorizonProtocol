# Quantum-Layer Design Note — Bounded-Entanglement QPV

**Program:** HorizonProtocol · **Status:** DESIGN ONLY, NO IMPLEMENTATION ·
**Claim class:** ENGINEERING_REFERENCE (design) · **Empirical claim:** NONE

This document specifies what a future, separately-reviewed quantum layer
would need to satisfy to close the gap H3-C deliberately demonstrates. It
contains no code and proposes none for this repository. Nothing here is
implemented, and nothing here should be read as a claim that it has been.

## 1. Problem statement

H3-C reproduces, on purpose, the classical impossibility result of
Chandran, Goyal, Moriarty, and Ostrovsky (2009, "Position Verification in
the Random Oracle Model"): **any classical distance-bounding / position-
verification protocol can be defeated by a set of colluding provers**, none
of whom is individually at the claimed position, provided they can
communicate with each other faster than light could travel between the
verifiers and back. H3-C's own test suite constructs exactly such a
collusion and shows every classical multilateration gate ADMITTING a
claim with no single agent present at the claimed location - reported
honestly as `EXPECTED_ATTACK_SUCCESS`, not hidden or explained away.

The property missing from H3's classical layer is **collusion
resistance**: soundness against multiple spatially-distributed adversaries
who share classical (or, as this note will make precise, bounded quantum)
correlations and unlimited classical communication between rounds. Classical
timing alone cannot provide this, because classical information is
perfectly copyable and forwardable: any classical challenge a verifier
sends can be relayed, in principle instantaneously with enough
computation and prearranged shared randomness, to wherever it is most
useful to answer from. No amount of tightening a classical clock budget
closes this gap - it is structural, not a matter of engineering
precision.

## 2. Model: the bounded-entanglement adversary `BE(Q)`

Quantum Position Verification (QPV) protocols attempt to restore soundness
by having the verifiers send **quantum states** (not classical bits) as
challenges. The security argument does not rely on the adversary's
computational bounds; it relies on **entanglement being a limited,
non-clonable resource**:

- **No-cloning:** colluding provers cannot copy an unknown quantum state
  to consult it independently, the way they could copy a classical
  challenge.
- **Monogamy of entanglement:** if two provers each hold a share of an
  entangled state with a verifier's system, the strength of one prover's
  correlation with the verifier bounds how strongly the *other* prover can
  be correlated with it. This is the basis on which a bounded-entanglement
  security proof rests: colluders who pre-share at most `Q` entangled
  qubits face a success probability that degrades as a function of `Q`,
  rather than being able to defeat the protocol unconditionally.
- **`BE(Q)`:** the adversary model considered here is explicitly a
  colluding set of provers who may pre-share **at most `Q` entangled
  qubits** before the protocol begins, plus unbounded classical
  communication and unbounded local computation, but who cannot generate
  fresh entanglement with the verifiers' systems mid-protocol beyond what
  the protocol itself transmits.

**This must be stated up front, not discovered later:** it is a known
result (Buhrman et al., 2014, "Position-Based Quantum Cryptography:
Impossibility and Constructions") that **unconditional QPV - security
against adversaries with unbounded pre-shared entanglement - is
impossible**. Any adversary with enough entangled qubits can, in
principle, defeat any single-round position-verification protocol using a
quantum teleportation-based attack requiring entanglement exponential in
the number of qubits the honest protocol transmits. A quantum layer here
would therefore only ever claim security in the `BE(Q)` model for a
declared, finite `Q` - never unconditional soundness. This is the quantum
analogue of H1-H4's "claim-scope firewall": the model is declared, and
security is conditional on it holding.

## 3. Candidate protocol sketch: `QPV_BB84`-style

A minimal candidate, at the level of *requirements* rather than
implementation:

1. Two (or more) verifiers `V_A`, `V_B`, positioned so that classical or
   quantum signals from each reach the claimed position `P` at
   geometrically distinguishable times, exactly as H3's multilateration
   already establishes for the classical layer.
2. `V_A` prepares a single qubit in one of the four BB84 states (chosen
   uniformly among `{|0>, |1>, |+>, |->}`) and sends it toward `P`,
   timed so it is scheduled to arrive at `P` at a precise instant `t*`.
3. `V_B` sends the corresponding measurement basis (a single classical
   bit: rectilinear or diagonal) toward `P`, timed to arrive at
   **exactly** `t*` as well - the two transmissions are engineered to
   intersect only at the claimed position, at the claimed instant.
4. A prover genuinely at `P` receives the qubit and the basis
   simultaneously, measures immediately in the announced basis, and
   classically broadcasts the measurement outcome back to both verifiers
   before a deadline set by the light-cone geometry (reusing H3's exact
   `deadline_ns` gate unchanged).
5. The verifiers ADMIT the position claim iff the returned outcome is
   correct *and* both directional light-cone deadlines are met - a
   classical gate identical in form to H3's, now composed with a quantum
   correctness check.

**Requirements this sketch imposes, stated as engineering constraints, not
implementation choices:**

- *Loss tolerance:* photon loss in transit is the dominant practical
  failure mode; a real deployment needs either a loss-tolerant variant
  (repeated rounds with a declared acceptable loss rate, threshold-based
  admission) or a heralded-transmission channel. This note does not
  specify one; a real implementation would need to.
- *Timing precision:* the "intersect only at `P`, only at `t*`" property
  requires clock synchronization and geometric precision tighter than
  H1's demo HMAC-keyed stations assume; H5's uncertainty-budget discipline
  (declare `U_ns`, refuse to certify inside the resolve margin) is the
  right template for how such precision would need to be declared and
  bounded, not asserted.
- *Slow quantum communication:* qubits cannot (with current or foreseeable
  technology) travel at a rate remotely approaching classical network
  throughput without loss growing prohibitively; a `BE(Q)` protocol is a
  low-rate, high-value primitive (one position attestation, not a
  streaming channel), and any design must not imply otherwise.

## 4. Interface to H3

A QPV round would **compose with**, not replace, H3's classical layer:

- **Classical gate as necessary condition:** every candidate quantum round
  is only meaningful if it also satisfies H3's classical multilateration
  gate (`horizon.distance.multilateration`) unchanged - the light-cone
  deadline math does not change when the payload becomes quantum.
- **Quantum gate as the collusion-resistant addition:** the quantum
  correctness check (step 5 above) is what would defeat H3-C's
  demonstrated collusion attack, since a colluding prover *not* at `P`
  cannot, without violating the `BE(Q)` bound, correctly answer a
  challenge that intersects only at `P` at `t*`.
- **What the combined certificate would record:** everything H3's
  certificate already records (per-verifier RTT witnesses, claimed
  position, failing verifiers if any), plus: the declared entanglement
  bound `Q`, the qubit-and-basis transmission schedule and its
  geometric-intersection witness, the measurement-outcome-correctness
  verdict per round, and an explicit count of rounds run (since a single
  round's soundness is probabilistic in `Q`, exactly as a bounded-error
  cryptographic proof requires reporting a soundness *error*, not a binary
  certainty).
- **Verdict vocabulary extension:** this repository's existing vocabulary
  (`PASS`, `FAIL`, `ADMITTED`, `REJECTED`, `APPARATUS_LIMITED`,
  `EXPECTED_ATTACK_SUCCESS`) has no member for "secure only conditional on
  a stated resource bound holding." A quantum layer would need a new
  verdict, e.g. `CONDITIONAL(BE(Q))`, applied to the *aggregate* claim
  only - never silently upgraded to `PASS`, and always carrying the `Q`
  it is conditional on. This mirrors H1-H4's discipline of naming the
  adversary model in the certificate rather than leaving it implicit.

## 5. Explicit non-goals / honesty

- This repository will **not** implement quantum hardware, a quantum
  simulator, or any quantum-cryptographic primitive. This document
  specifies what a future, **separately reviewed** layer must satisfy; it
  is not a commitment to build one here.
- No claim that any such layer, if built, would constitute a deployed or
  deployable cryptosystem.
- Security in this model is **conditional on the entanglement bound
  `Q` holding** - a `BE(Q)`-secure protocol says nothing about an
  adversary who exceeds `Q`, and unconditional QPV is a known
  impossibility (section 2). Any future certificate must carry this
  conditionality explicitly, the same way H2's certificate names its
  adversary model rather than claiming unconditional binding.
- No claim that passing any future quantum-layer benchmark constitutes
  evidence about physics beyond the declared, cited theoretical results.

## 6. Registered assumptions (testable statements)

- QA1: no-cloning and monogamy-of-entanglement bounds, as established in
  the cited literature, hold for the physical system a future
  implementation would use. (Assumed from established quantum theory;
  not something this repository would test.)
- QA2: a future protocol's soundness error is a decreasing function of the
  number of independently-sampled rounds run, for fixed `Q`. Falsified if
  an implementation's measured soundness error does not decrease with
  additional rounds under a fixed, declared `Q`.
- QA3: the classical multilateration gate (H3, reused unchanged) remains
  a necessary condition - falsified if any proposed composition admits a
  position claim that fails H3's classical gate.
- QA4: any claimed `Q` bound is declared and frozen per certificate, the
  same way H2's `P_FIELD` and H5's `c_eff`/`U_ns` are declared and frozen
  - falsified if a future implementation varies `Q` without recording the
  change and re-tagging per `docs/release-checklist.md`.

## Prohibited claims (repository-wide, verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside each layer's stated
  model.
- No claim that H3's classical layer resists collusion (H3-C proves the
  opposite on purpose).
- No claim that H4 certifies statistical randomness.
- No claim that H5's synthetic-consistent fixtures are real measurements.
- No claim that any passing benchmark is evidence about physics.

## References (context only, not reproduced or re-derived here)

- Chandran, Goyal, Moriarty, Ostrovsky. "Position Verification in the
  Random Oracle Model," 2009 (the classical impossibility H3-C
  reproduces).
- Buhrman, Chandran, Fehr, Gelles, Goyal, Ostrovsky, Schaffner.
  "Position-Based Quantum Cryptography: Impossibility and Constructions,"
  2014 (the unconditional-QPV impossibility and the bounded-entanglement
  model this note adopts).
- Kent, Munro, Spiller. "Quantum Tagging: Authenticating Location via
  Quantum Information and Relativistic Signalling Constraints," 2011
  (an early bounded-attacker QPV construction).
