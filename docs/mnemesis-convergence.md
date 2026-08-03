# MnemesisOS Convergence — Design Note

**Program:** HorizonProtocol · **Status:** DESIGN ONLY, NO IMPLEMENTATION ·
**Claim class:** ENGINEERING_REFERENCE (design) · **Empirical claim:** NONE

This document maps `horizon.ledger.CausalLedger` and cone certificates
onto the MnemesisOS problem: reconciling divergent-observer state without
a global "now." It contains no code and proposes none for this
repository. It is sober by design - the mapping is offered as a
structural observation to be tested, not a finished architecture.

## 1. The structural claim

The MnemesisOS problem, stated plainly: a memory substrate serving
multiple observers (agents, replicas, distributed writers) cannot assume
a single global order of events, because no such order exists for
spacelike-separated writes - imposing one anyway either fabricates a
causal relationship the underlying process never had, or silently drops
information about genuine concurrency.

`horizon.ledger.CausalLedger` already embodies the correct primitive for
this, built for an unrelated purpose (certifying that a *dependency*
between two events is geometrically possible): it is a DAG, not a total
order, and it stores concurrent (spacelike-separated) events **as
concurrent**, refusing to sequence what the geometry does not certify
(`test_h1d_ledger.TestLedger.test_concurrency_is_symmetric_nonorder`).
The structural claim of this note is that this is exactly the right shape
for a provenance-aware, multi-observer memory system: **"concurrent
events stored unordered" is the correct primitive for such a system, not
a limitation to be engineered away.** A system that insists on
linearizing every write is a system that has decided to lie about
causality whenever two writers were, in fact, independent.

## 2. Mapping table

| HorizonProtocol concept | Memory-substrate concept |
|---|---|
| Ledger event (hash + time + position) | Memory write, with a verifiable origin |
| Admissibility gate (`causally_admissible`) | Merge admissibility: can write B legitimately depend on write A? |
| Concurrency (`CausalLedger.concurrent`) | Conflict requiring resolution-with-provenance, not silent overwrite |
| Cone certificate (event + signed receipts) | Provenance record: who observed this write, and when, attested |
| Rejection with exact witness | Auditable merge refusal: the specific reason a proposed merge order is impossible, not a bare failure |
| Causal ledger DAG | The memory substrate's dependency graph itself |

Read down the table: every column-two concept already has a
column-one referent with a working, tested implementation in this
repository. Nothing in the mapping requires a new primitive - it requires
recognizing that the primitive already exists and was built to a
stricter standard (exact-integer, adversarial) than most memory systems
demand of themselves.

## 3. The PGSD tie-in

A previously-flagged pattern for transfer - parallel candidate states
carried with provenance, resolution deliberately deferred rather than
forced early (referred to elsewhere as "superset decompilation," PGSD) -
needs exactly the admissibility layer HorizonProtocol supplies: a
mechanism for deciding, **for a candidate merge or resolution step**,
whether it is even *possible* given what each candidate state can
legitimately have known. Where PGSD defers resolution among several
live candidates, HorizonProtocol's causal gate is what would tell the
substrate which candidates are mutually exclusive (one causally
excludes what the other assumed) versus which are genuinely independent
and can be carried in parallel without contradiction. This is a narrower
claim than "HorizonProtocol solves PGSD's deferred-resolution problem":
it supplies the *admissibility test* that problem needs at each
resolution step, not the resolution policy itself.

## 4. What transfers now vs. later

**Directly reusable now**, as-is or with only interface adaptation (no
algorithmic change):

- `horizon.ledger.CausalLedger`'s DAG structure and its `concurrent`/
  reachability queries - a memory substrate can adopt this data structure
  directly for its dependency graph.
- The cone-certificate pattern (event + signed receipts + standalone
  verification) as a template for attaching verifiable provenance to a
  memory write, independent of *how* that write's timestamp was obtained.
- The rejection-with-exact-witness discipline: a merge refusal in a
  memory substrate should, on this model, always name the specific
  conflicting write and the specific reason, not fail generically.

**Needs generalization before reuse:**

- The admissibility gate itself is currently light-cone geometry
  (physical positions, physical light speed). A memory substrate without
  physical position data needs a **logical or vector-clock fallback**:
  the same DAG-with-admissibility-gate shape, but with "admissible" tested
  against logical causality (e.g., vector-clock dominance) rather than
  physical geometry. This is a substitution of the gate predicate, not a
  change to the surrounding ledger structure - `CausalLedger` was written
  generically enough (per H1's design) that this substitution looks
  mechanical, but it has not been attempted or tested.
- H5's uncertainty-budget discipline (declare `U_ns`, refuse to certify
  inside a resolve margin) is a plausible template for a substrate that
  *does* have imprecise physical timestamps (e.g., loosely synchronized
  distributed writers) but wants to avoid HorizonProtocol's H1 tight gate
  falsely rejecting legitimate concurrent writes as conflicting. This has
  not been designed for the memory-substrate case specifically.

**Out of scope for this note:**

- Any actual merge *policy* (last-writer-wins, CRDTs, application-level
  conflict resolution) - this note claims HorizonProtocol supplies the
  admissibility *test*, not a policy for what to do once concurrency is
  detected.
- Performance/scalability of `CausalLedger` at memory-substrate scale (the
  current implementation is a reference/demo DAG, not benchmarked for
  large event counts).
- Any claim that this mapping has been implemented, tested, or run against
  a real MnemesisOS workload.

## 5. Registered open questions (testable statements)

- MQ1: does substituting a vector-clock admissibility predicate into
  `CausalLedger`'s existing DAG/concurrency machinery require changing
  the DAG structure itself, or only the predicate function? (Testable by
  attempting the substitution against the existing test suite's
  structural expectations.)
- MQ2: for a workload with `N` genuinely concurrent writers, does storing
  all pairwise-concurrent writes unordered (rather than forcing a
  arbitrary total order) measurably change downstream read/merge
  correctness, versus only changing audit-trail honesty? (Testable by
  comparing a policy that timestamps-and-orders arbitrarily against one
  that preserves the DAG's genuine concurrency.)
- MQ3: does the cone-certificate provenance pattern (signed receipts +
  standalone verification) impose acceptable overhead at realistic memory
  write rates, or does it need a lighter-weight provenance attestation for
  high-frequency writes? (Testable by benchmarking receipt
  signing/verification throughput against a target write rate.)
- MQ4: can H5's uncertainty-budget discipline be adapted to a logical
  (non-physical) clock setting, or does it fundamentally depend on a
  physical light-speed bound with no logical analogue? (Testable by
  attempting the adaptation and checking whether an "impossible margin"
  concept survives without a physical speed limit to anchor it.)

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
