# Reference Design: A Causally-Grounded Distributed Data System

**HorizonProtocol as substrate · MnemesisOS as interoperable memory · two tracks
(performance and provenance) converging on one engine**

Version 0.1 (design) · engineering reference · not a specification of a shipped
product. Every mechanism here maps to code that exists (HorizonProtocol H1–H9,
the MnemesisOS convergence) or to a named, bounded extension.

---

## 0. Thesis and the one honest boundary

Every distributed datastore fights the absence of a global "now." The standard
answers — Lamport clocks, vector clocks, CRDTs, Spanner/TrueTime commit-wait — are
approximations of a physical fact: **which events could have caused which is fixed
by the speed of light.** This system makes that fact first-class and exact. An
event's place in the order is not a convention; it is a geometric decision,
certified in exact integer arithmetic against a machine-checked light-cone kernel,
and tamper-evident because forging an order would require forging a signal history
faster than light.

**The honest boundary, stated once, up front:** the geometric decision only adds
value when signal flight-time between nodes exceeds their clock uncertainty. Inside
a single datacenter (nodes microseconds apart, clocks microseconds uncertain) the
geometry cannot resolve and every verdict is APPARATUS_LIMITED — you gain nothing.
The advantage *grows with physical distance*. Therefore the system is **hybrid by
design**: it runs a logical (vector-clock) ordering as the always-available
fallback and layers geometric certification on top exactly where the geometry can
resolve. This is not a compromise; it is the correct architecture, and both
orderings already exist behind one interface in the MnemesisOS convergence.

---

## 1. The shared engine (where both tracks meet)

Both tracks — performance and provenance — are the **same core** with different
policies bolted on. Defining the core once is what lets them converge cleanly at
the end (Section 6).

### 1.1 Layers

```
  L4  Application API            put / get / resolve / query-order
  L3  Causal ledger (the store)  events, partial-order DAG, conflict retention
  L2  Ordering interface         before(a,b) · concurrent(a,b) · witness(a,b)
        ├─ GeometricOrdering     exact light-cone gate (HorizonProtocol kernel)
        └─ LogicalOrdering       vector-clock happens-before (fallback)
  L1  Exact kernel               causally_admissible (machine-checked, frozen)
  L0  Timing fabric              PTP/NTP per node + PUBLISHED measured uncertainty U
```

The critical seam is **L2**. The store (L3) never knows whether it is ordering by
geometry or by logic — it calls `before`/`concurrent`/`witness` on an injected
ordering object. That single indirection is what makes the system
system-software-independent (Section 5) and MnemesisOS-interoperable (Section 4):
anything that satisfies the L2 contract can drive the store, and the store can
drive anything that consumes its events.

### 1.2 The event (the atom both tracks share)

```
Event = {
  event_id,               # hash of the canonical payload
  payload,                # opaque to the engine
  clock: {                # ONE of:
    time_ns, pos_nm, u_ns # geometric: measured time, surveyed position, measured uncertainty
    | vc: {node: counter} # logical: vector clock
  },
  origin_node,            # who wrote it
  supersedes: [event_id], # claimed causal predecessors
  signature,              # per-node key (Ed25519 in production)
}
```

A write may supersede a prior event **only if** the ordering says the prior is in
its causal past. A supersession that fails is refused with a witness — the exact
integers (geometric) or the vector-clock pair (logical). Concurrent events are
retained with provenance, never overwritten. This is the MnemesisOS `CausalMemory`
behavior exactly.

### 1.3 The three verdicts propagate up from L1

Every ordering decision is ADMITTED / REJECTED / APPARATUS_LIMITED. The store's
job is to route on them, and this is precisely where the two tracks diverge in
policy while sharing the engine:

- **ADMITTED** — a real causal edge; both tracks record it.
- **REJECTED** — impossible (beyond the absolute vacuum floor); both tracks refuse
  with witness.
- **APPARATUS_LIMITED** — geometry can't resolve at this tier. **This verdict is
  the fork.** The performance track treats it as "assume concurrent, proceed
  coordination-free." The provenance track treats it as "fall back to logical
  ordering and record that the geometric certificate was unavailable here."

---

## 2. Track P1 — Performance: coordination-free by geometry

**Goal:** eliminate consensus for events the geometry proves independent.

**The core move.** Two writes that are spacelike-separated *cannot* have caused
each other — the light cone says so. Therefore they can be applied in either order
with identical results and **need no coordination at all**. Where blockchains and
Paxos/Raft impose a total order (and pay latency for it), this system imposes only
the *partial* order that physically exists, and runs everything else in parallel.

**Mechanism.**
1. On write, compute the ordering verdict against the current frontier for the key.
2. If every relation to concurrent writes is `concurrent` (spacelike), **commit
   locally and immediately** — no round trip. The write is a new maximal element;
   there is nothing to coordinate with.
3. If a write is causally after existing writes (ADMITTED past), it supersedes them
   locally; propagate lazily.
4. Only genuine causal conflicts (two writes each claiming to supersede a shared
   past, resolvable) require the resolve protocol — and even that is a *local*
   decision by any node in the causal future of both, not a global consensus round.

**What you get.** Throughput scales with causal independence. In a geo-distributed
workload where most writes touch different keys or regions, nearly everything is
concurrent and commits without coordination. The APPARATUS_LIMITED verdict is
handled optimistically here: if the geometry can't prove order, assume concurrent
and proceed; a later tightening (or a logical-clock cross-check) can reconcile if
needed. This is safe because the provenance track (P2) is what guarantees nothing
is *lost* — P1 optimizes latency, P2 guarantees auditability, and Section 6 shows
they are the same store.

**Honest limits.** Coordination-free commit is only correct for operations that are
genuinely commutative when concurrent (CRDT-style merge semantics, or last-writer-
wins *with retained provenance* so "last" is never silently lost). Non-commutative
operations on the *same* key still require the resolve protocol. State this per-API
so users know which operations are free and which coordinate.

## 3. Track P2 — Provenance: tamper-evident causal audit

**Goal:** make the causal history of every datum a verifiable, non-repudiable
artifact.

**The core move.** Every event carries a signed receipt and, where geometry
resolves, a **cone certificate**: the event's position in the causal order is
provable against the speed of light from its claimed origin, re-checkable by any
third party from the certificate plus the public node registry, without re-running
anything. Forging an event's place in history requires forging a signal history
that beats light — which the kernel rejects with an exact integer witness.

**Mechanism.**
1. Every write is a signed event; the signature binds payload, origin, position,
   measured time, and measured uncertainty.
2. Where the geometry resolves (flight-time > clock error), attach a cone
   certificate (HorizonProtocol H1/H8) proving the event's causal placement.
3. Where it does not (APPARATUS_LIMITED), record the logical-clock placement AND an
   explicit note that the geometric certificate was unavailable at that tier — the
   audit trail never pretends to a certainty it lacks.
4. The ledger is append-only with provenance: superseded values are retained,
   concurrent values retained as candidates, and every resolution records which
   event resolved which and under what ordering.

**What you get.** A causal audit trail where each claim is either geometrically
certified or honestly marked as logically-only-ordered. This is the artifact for
data-residency attestation (prove data entered and stayed in a region), content
provenance (bind a datum's existence-event to dispersed timing authorities),
regulated audit logs, and supply-chain integrity — anywhere the *history* is the
product.

**Honest limits.** Provenance is tamper-evident, not tamper-proof: it proves an
inconsistency exists, it does not prevent a node from lying — a lying node produces
a certificate that fails verification, which is detection, not prevention. And the
authentication is only as strong as the key management (Ed25519 per node, not the
HMAC demo stand-in).

## 4. MnemesisOS interoperation (close, but decoupled)

The design goal: **HorizonProtocol and MnemesisOS integrate trivially yet neither
depends on the other's internals.** The mechanism is a single narrow contract at
L2, already present in the MnemesisOS convergence code.

### 4.1 The contract (the only coupling point)

```
Ordering:
    before(a, b)     -> bool          # is a in b's causal past?
    concurrent(a, b) -> bool          # neither before the other?
    witness(a, b)    -> dict          # evidence for the decision

Event clock: either {time_ns, pos_nm, u_ns}  (geometric)
                 or {vc: {...}}               (logical)
```

MnemesisOS already ships `GeometricOrdering` (wrapping the HorizonProtocol kernel)
and `LogicalOrdering` (vector clocks) satisfying this exact contract, and its
`CausalMemory.put/get/resolve` already consumes it. So:

- **HorizonProtocol → MnemesisOS:** HorizonProtocol supplies the `GeometricOrdering`
  and the cone-certificate machinery as a library. MnemesisOS imports it as *an*
  ordering, not *the* ordering. If HorizonProtocol is absent, MnemesisOS still runs
  on `LogicalOrdering` unchanged.
- **MnemesisOS → HorizonProtocol:** MnemesisOS supplies the memory/state substrate
  (the append-only provenance store, conflict retention). HorizonProtocol's ledger
  can persist through it, or not. If MnemesisOS is absent, HorizonProtocol's ledger
  runs on its own in-memory DAG.

### 4.2 Independence guarantees (how we keep them decoupled)

1. **No shared types across the boundary except the L2 contract and the event
   dict.** Neither imports the other's classes; they exchange plain dicts and call
   the three ordering methods. (This is a versioned, documented interface — treat
   it as a stable ABI.)
2. **Capability negotiation, not hard dependency.** At startup each side advertises
   what it provides (geometric ordering? provenance store? PTP timing?). The other
   uses what's present and degrades gracefully to fallbacks when it isn't. A node
   with no PTP advertises only logical ordering; a node with HorizonProtocol but no
   MnemesisOS uses the built-in ledger.
3. **The kernel is frozen and shared by value, not by coupling.** Both systems use
   the same machine-checked `causally_admissible`, but as a vendored, hash-verified
   frozen artifact (the consolidation note's single-copy rule) — an update to the
   kernel is a deliberate, verified event, never an implicit transitive dependency.
4. **Either can be swapped.** A third-party ordering (someone else's timing source)
   or a third-party store (Postgres, an LSM tree) can replace either side as long as
   it meets the contract. The system is substrate-independent by construction.

### 4.3 What "easily integrated" concretely means

Dropping the two together is: import HorizonProtocol's `GeometricOrdering`, hand it
to MnemesisOS's `CausalMemory`, done — you now have a geometrically-certified,
provenance-native memory. Removing either is deleting one import and falling back.
That is the whole integration surface. Small on purpose.

## 5. System-software independence

The stack must not bind to any OS, database, or runtime. Enforced by:

- **Pure-computation core.** The kernel and ordering are stdlib-only exact integer
  arithmetic — no OS calls, no DB, no network in the trusted path. (HorizonProtocol
  already enforces this; the float-guard and machine-checked proof are the standing
  gates.)
- **Timing fabric behind an interface.** L0 exposes only `(measured_time_ns,
  measured_uncertainty_ns)` per node. Whether that comes from PTP hardware, NTP,
  GNSS, or a test harness is behind the interface. The store never knows.
- **Persistence behind an interface.** The ledger defines an append-only log
  contract; back it with memory, files, an embedded KV store, or MnemesisOS. No
  ordering or verification logic lives in the persistence layer.
- **Transport behind an interface.** Event propagation is "deliver this signed event
  to these nodes" — TCP, UDP, message bus, or delay-tolerant bundle protocol, all
  interchangeable. Interplanetary (high-latency) transport is a first-class case,
  not an afterthought, because the whole point is tolerating the absence of a global
  now.

The result: the same engine is designed to run in a unit test, a three-region
cloud deployment, or a delay-tolerant network, with only the L0/persist/transport
adapters changing. As of this writing, H8's multi-node result is a
`MEASURED_MODEL` stand-in over real cloud-region geography, not yet a genuine
live capture (see `docs/HANDOFF-H8-LIVE-Azure.md` for the planned live run over
real provisioned Azure VMs) — the three-region claim above is the design's
target shape, not yet a completed empirical result.

## 6. Convergence: the two tracks are one store

Performance (P1) and provenance (P2) are **not two systems** — they are two policies
over the single engine of Section 1, and they converge because they are the same
append-only causal ledger read two ways:

- P1 reads the ledger's **partial order** to decide what can commit without
  coordination (concurrent ⇒ free).
- P2 reads the same ledger's **provenance and certificates** to produce the audit
  trail (every edge either certified or honestly marked).

They share: the event atom (1.2), the ordering interface (1.1/4.1), the three
verdicts (1.3), and the append-only conflict-retaining store (P2's mechanism is
P1's safety net — nothing P1 commits coordination-free is ever lost, because P2
retains it with provenance).

**The convergence claim, precisely:** a write path that (a) commits immediately when
the geometry proves independence (P1) while (b) emitting a signed, certified,
retained provenance record (P2) gives you *both* low-latency geo-distributed writes
*and* a tamper-evident causal audit trail, from one engine, because coordination-
freedom and auditability are dual readings of the same partial order. Fast because
the geometry says what's independent; trustworthy because the geometry says what's
certified.

## 7. First target (recommended)

Lead with **multi-region audit-provenance datastore** as the beachhead:
- It plays to the strength (continental distance ⇒ geometry resolves ⇒ real
  certificates), dodging the single-datacenter weakness.
- Provenance is a paid product (compliance, residency, content authenticity), so P2
  is the revenue path.
- P1's coordination-free writes are the *performance differentiator* layered on the
  same store — you sell provenance, you win on latency.
- H8's `MEASURED_MODEL` result over real cloud-region geography is directionally
  supportive of exactly this geometry, but is not yet a live-measured
  proof-of-concept (see Section 5) — that upgrade is the next concrete milestone,
  not a completed prerequisite.

Then extend toward delay-tolerant / interplanetary as the long-horizon story, where
the "no global now" architecture is not an optimization but a necessity.

## 8. Build sequence (bounded, each additive, each verified green)

1. **D0 — Engine skeleton.** Lift the MnemesisOS `CausalMemory` + both orderings
   into a standalone `causal-store` package with the L2 contract documented as a
   stable interface. (Mostly exists; this is packaging + the contract doc.)
2. **D1 — Persistence + transport adapters** behind interfaces (memory + file to
   start; the transport is "deliver signed event").
3. **P1-α — Coordination-free commit path:** concurrent ⇒ local commit; measure
   throughput vs a total-order baseline on a geo-distributed workload.
4. **P2-α — Certified provenance path:** attach cone certificates where geometry
   resolves; emit the standalone-verifiable audit trail.
5. **C — Convergence test:** one workload exercising both — coordination-free geo
   writes that simultaneously produce a verifiable audit trail; assert P1's commits
   are all P2-retained (nothing lost).
6. **M — MnemesisOS interop demo:** the same store driven by MnemesisOS as the
   provenance substrate via the L2 contract only, and running standalone without it
   — proving the decoupling.

Each step ships code, tests, deterministic certificates, and a spec with registered
falsifiers, in the established HorizonProtocol discipline. The kernel is never
modified; everything is additive over the machine-checked core.

## 9. Registered risks / falsifiers (design-level)

- R1: if, on a real geo workload, most writes are APPARATUS_LIMITED (clocks too
  coarse for the distances), the geometric advantage collapses to the logical
  fallback — measure the resolve rate per deployment before promising geometric
  benefit.
- R2: coordination-free commit is only correct for commutative/CRDT-safe ops;
  claiming it for non-commutative same-key ops is a correctness defect.
- R3: provenance is detection, not prevention; presenting it as tamper-*proof* is a
  claim-scope violation.
- R4: any coupling between HorizonProtocol and MnemesisOS beyond the L2 contract +
  event dict is an independence defect — file it.
- R5: any float or tolerance entering the ordering decision violates the exactness
  invariant (the float-guard is the standing check).
- R6: describing H8's `MEASURED_MODEL` result, or any other computed/synthetic
  result, as a completed "live" empirical proof-of-concept before a genuine
  `LIVE_CAPTURE` has actually been run and recorded — a claim-scope violation this
  document itself corrected once (see the note in Sections 5 and 7).

---

*This is a design, not a shipped system. Its value is a coherent path: one exact,
machine-checked engine; two policies (fast, trustworthy) that converge because they
read one partial order two ways; and a narrow contract that lets HorizonProtocol and
MnemesisOS integrate in one import yet stand alone. Build it in the same discipline
that got the kernel machine-checked and the first certificate measured across three
continents.*
