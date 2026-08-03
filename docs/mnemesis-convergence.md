# MnemesisOS x HorizonProtocol — Convergence (MNX1)

**Program:** MnemesisOS x HorizonProtocol · **Benchmark:** MNX1 ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. The structural claim (demonstrated, not just asserted)

An earlier design note argued that `horizon.ledger.CausalLedger` and cone
certificates are structurally identical to a provenance-aware,
multi-observer memory. This document's companion code (`mnemesis/`)
demonstrates the identity mechanically rather than by analogy: the
memory's ordering agrees, edge for edge, with the `CausalLedger`
admissibility gate (gate MNX-D), and the same exact light-cone kernel
(`horizon.geometry`, unmodified) decides both.

The mapping is exact:

| Memory concept | HorizonProtocol concept |
|---|---|
| a write (key := value by an observer) | an event with (time, position) |
| "this write supersedes that one" | a causal dependency edge A -> B |
| supersession admissibility | the light-cone gate (c·Δt)² ≥ Δx² |
| two writes neither superseding the other | spacelike-separated / concurrent events |
| conflict surfaced for resolution | concurrent events stored unordered |
| provenance of a value | the cone certificate / event witness |
| refused overwrite (with reason) | REJECTED edge (with exact witness) |

The consequence is a memory with a property most distributed stores lack:
**an overwrite that could not causally have observed the value it claims to
replace is refused, with a witness.** Silent last-writer-wins is impossible
by construction; it is not a policy but a geometric fact.

## 2. Concurrent writes: retain, don't collapse (the PGSD pattern)

When two observers write the same key with no causal order between them,
`CausalMemory.get` does not pick a winner. It returns `CONFLICT` with all
candidates and their provenance, deferring resolution - the "retain
ambiguous interpretations as parallel candidates with provenance, defer
selection to a final phase" pattern from provenance-guided superset
decompilation, already flagged for transfer in the Global-Variables
program. Resolution is an explicit operation (`CausalMemory.resolve`): a
new write that is in the causal future of *every* current candidate. An
observer that cannot see all candidates cannot resolve the conflict -
again a geometric fact, not a convention.

This is also the Global-Variables fact-store culture made operational:
append-only, provenance-carrying, with invalidation by causally-later
writes rather than destruction.

**Errata (fixed, not merely noted):** an earlier version of `resolve`
looked up `chosen_wid` in the ENTIRE store rather than restricting it to
`key`'s current frontier candidates, so a write id belonging to a
different key (or one already superseded) could be "chosen" to resolve a
conflict it was never actually a candidate for. `resolve` now rejects any
`chosen_wid` outside the target key's frontier (`not_a_frontier_candidate`).
Separately, `put` was not idempotent: retrying an identical
`(key, value, observer, clock)` call re-appended the same write id to the
key's index (`_frontier` then saw it twice, and `get` could falsely report
`CONFLICT` against itself) and, if the retry declared a different
`supersedes`, silently rewrote the original write's provenance - a direct
violation of "append-only." `put` now recognizes a repeated write id and
returns the original admission unchanged.

## 3. Two clocks, one interface

Geometry is not always available (a purely logical distributed system has
no metric). `mnemesis.memory.CausalMemory` is therefore clock-agnostic: it
takes an `ordering` object exposing `before(a, b)` and `concurrent(a, b)`,
and this repository ships two:

- **`GeometricOrdering`** - exact light-cone ordering over `{"time_ns",
  "pos_nm"}` clocks, reusing `horizon.geometry.causally_admissible`
  UNCHANGED (test MNX-D asserts the import by source inspection). This is
  the physically-grounded mode, correct for real distributed nodes with
  surveyed positions and measured time (the H5/H6 substrate).
- **`LogicalOrdering`** - vector-clock happens-before (`mnemesis.vclock`),
  the standard partial order, for contexts without geometry.

**Erratum:** `mnemesis.vclock.happens_before` originally computed
`a != b and leq(a, b)` - a raw dict inequality, not a normalized one. Two
clocks that are the SAME logical instant under zero-padding but differ in
dict representation (e.g. `{"n1": 1}` vs. `{"n1": 1, "n2": 0}`) satisfied
`a != b` in BOTH directions, so `happens_before` reported each before the
other - an antisymmetry violation that would let `CausalMemory.put` admit
a write "superseding" another at the same logical instant. Fixed to the
standard antisymmetric definition, `leq(a, b) and not leq(b, a)`, which
correctly treats such pairs as concurrent (test
`test_zero_padded_equivalent_clocks_are_not_before_each_other`).

Both satisfy the same memory invariants (gates MNX-B, MNX-C), so an
application can start logical and upgrade to geometric where physical
coordinates become available - for example, promoting a vector-clock
store to a cone-certified one once nodes are surveyed. (Whether that
upgrade never *loosens* what the geometric gate would have rejected is
registered as open question Q3 below - not yet implemented or tested.)

## 4. What transfers now vs. later

**Implemented here:** `mnemesis.memory.CausalMemory` (the store),
`GeometricOrdering` / `LogicalOrdering`, `mnemesis.vclock` (vector
clocks), and the conflict/resolve protocol. `mnemesis.memory` imports
`horizon.geometry` directly rather than vendoring a copy - there is
exactly one light-cone kernel in this repository, shared by H1-H6 and
MNX1 alike.

**Directly reusable, unmodified:** `horizon.geometry` (the exact gate),
`horizon.ledger` (the DAG and concurrency query - `CausalLedger` needed no
changes to serve as MNX-D's cross-check), the certificate discipline, and
the negative-control/witness culture.

**Deferred (out of scope at MNX1, registered as future work):**
- a signature/authentication layer so writes are non-repudiable (today
  MNX1 assumes honest observers; Byzantine tolerance is future work,
  mirroring H1-H6's single-forger, non-colluding adversary model);
- garbage collection of deep history under a retention policy that
  preserves provenance for live values;
- geometric<->logical bridging when only *some* nodes are surveyed (see
  Q3);
- integration with H5/H6 measured timestamps so a memory write's clock is
  a real, cone-certified measurement (with its own uncertainty budget)
  rather than a supplied value.

## 5. Registered open questions (as testable statements)

- Q1: does the frontier computation remain exact and order-independent
  under adversarial write interleavings? (MNX-B/C test honest
  interleavings; a Byzantine test is future work.)
- Q2: for a workload with `N` genuinely concurrent writers, does storing
  all pairwise-concurrent writes unordered (rather than forcing an
  arbitrary total order) measurably change downstream read/merge
  correctness, versus only changing audit-trail honesty? (Testable by
  comparing a policy that timestamps-and-orders arbitrarily against one
  that preserves the DAG's genuine concurrency.)
- Q3: does a geometric->logical downgrade ever admit an edge the
  geometric gate would reject? (Must not; a bridging test asserting this
  has not yet been written.)
- Q4: can a resolution be forged by claiming a clock in the future of
  both candidates without physically being there? (This is exactly the
  H3-C collusion question; the answer is the quantum layer's
  (`docs/quantum-layer-spec.md`), not MNX1's.)
- Q5: does H5/H6's uncertainty-budget discipline (declare `U_ns`, refuse
  to certify inside the resolve band) adapt to a memory-write setting
  without a physical light-speed bound to anchor "impossible"? (Not
  attempted here.)

## 6. Claim scope

MNX1 certifies that a provenance-aware causal memory, built on the exact
HorizonProtocol light-cone kernel, executes and satisfies its declared
gates - including that its ordering matches the ledger edge-for-edge
(gate MNX-D). It is NOT a production database, NOT Byzantine-fault-
tolerant, and NOT a security proof. The value demonstrated here is the
identity: HorizonProtocol supplies the causal admissibility layer a
multi-observer memory needs, and `mnemesis.CausalMemory` is that memory.

## Prohibited claims (repository-wide, verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside each layer's stated
  model.
- No claim that H3's classical layer resists collusion (H3-C proves the
  opposite on purpose).
- No claim that H4 certifies statistical randomness.
- No claim that H5's or H6's synthetic-consistent fixtures are real
  measurements.
- No claim that any passing benchmark is evidence about physics.
