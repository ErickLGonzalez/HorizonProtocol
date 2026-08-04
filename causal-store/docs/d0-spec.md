# D0 Engineering Specification — Coordination-Free Causal Store (performance-first)

**Program:** causal-store · **Benchmark:** D0 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none · **Empirical claim:** NONE

## 1. Objective
A geo-distributed event store whose performance thesis is: two writes that the
light cone proves causally independent (spacelike) cannot have caused each other,
so they commit WITHOUT coordination. Only genuine causal dependencies serialize.
This targets the dominant cost in geo-distributed transactions — wide-area round
trips for consensus/2PC — which financial and other latency-critical systems pay
on every write under total-order protocols.

## 2. Architecture (three contracts, one engine)
- **L1 kernel** (`geometry.py`): exact-integer light-cone predicate (reused from
  HorizonProtocol, machine-checked). Never modified.
- **L2 ordering contract** (`ordering.py`): `before(a,b)`, `concurrent(a,b)`,
  `witness(a,b)`. Three implementations: `GeometricOrdering` (exact light cone,
  resolves only when time-gap exceeds combined clock uncertainty), `LogicalOrdering`
  (vector-clock happens-before, always resolves), `HybridOrdering` (geometric where
  it resolves, logical fallback elsewhere — the production default). This is the
  ONLY coupling point; it is a stable ABI.
- **StoreBackend contract** (`store.py`): `append`, `events_for_key`, `all_events`.
  A minimal `InMemoryBackend` ships for testing; a real memory/database layer plugs
  in here WITHOUT the engine importing it.

## 3. The coordination-free decision (the core)
On write, the engine computes the relation to the current frontier for the key:
- frontier empty -> commit free.
- write causally after the whole frontier -> supersede, commit free (no coordination).
- write spacelike to the whole frontier -> commit free, retained as concurrent.
- mixed -> supersede the ancestors it follows, retain the rest with provenance; a
  single LOCAL decision using the exact order — still no global consensus round.
Conflicts (concurrent writes to one key) are RETAINED with provenance, never
dropped, so nothing a coordination-free commit produces is lost. Supersession
claims that are not causally valid are REJECTED with a witness.

## 4. Exactness boundary
All ordering/admissibility decisions are exact integer (geometry.py, ordering.py:
float-guard clean, enforced by gate D0-E, not merely claimed). The only
float/division is `coordination_free_rate()`, a reporting metric explicitly
annotated as outside the trusted path.

## 5. Gates
- D0-A: ordering contract — geometric before/concurrent; resolves-only-beyond-
  uncertainty (including the fixed margin-to-floor boundary case, see erratum
  below); logical happens-before; hybrid geometric-then-logical fallback.
- D0-B: store — disjoint keys all coordination-free; spacelike same-key retained as
  conflict; causal supersede without coordination; non-ancestor supersede REJECTED;
  nothing lost on coordination-free commits; a causally-stale write is REJECTED
  rather than resurrected as a live conflict candidate (see erratum below).
- D0-C: backend swappable via contract; engine imports no concrete DB.
- D0-D: benchmark — coordination-free rate > 0.7 and modeled speedup > 2x on a
  5-region workload; deterministic across runs.
- D0-E: exactness boundary — `ordering.py`/`geometry.py` contain zero floats,
  true division, or `sqrt`/`float()` calls; `store.py`'s one float/division
  site is exactly `coordination_free_rate()`, the documented reporting metric.
- D0-F: the vendored `causalstore/geometry.py` copy is byte-identical to
  `horizon/geometry.py` — no silent drift in the kernel shared by value.

## 5.1 Erratum (fixed before first commit)
Two bugs were found and fixed during integration review, before any certificate
was committed:
- `GeometricOrdering.resolves()` originally tested the RAW elapsed time against
  combined clock uncertainty (`abs(dt) > combined_u`), with no reference to the
  light-time floor the pair actually requires. A pair can have many seconds of
  elapsed time (dwarfing a microsecond-scale `combined_u`) while sitting within
  nanoseconds of its OWN (also large) required floor — exactly the boundary a
  resolution check exists to catch. Fixed: `resolves()` now compares the MARGIN
  between the measured `dt` and the exact `min_light_time_ns` floor against the
  combined uncertainty, never the raw elapsed time.
- `CausalStore.write()` classified a new write's relation to the frontier by
  checking only "after the whole frontier" or "concurrent with the whole
  frontier," falling through to conflict-retention for everything else —
  including a write that is causally BEFORE an existing frontier member. That
  let a stale write (an old vector clock or geometric timestamp) resurrect an
  already-superseded value as a live CONFLICT candidate. Fixed: `write()` now
  checks for frontier members that dominate the incoming write and REJECTS with
  `reason: "stale_write_dominated_by_existing_frontier"` before any other
  classification.

Both are regression-tested (D0-A, D0-B) with the concrete counterexamples that
found them.

## 6. Benchmark result (this release)
5 regions, 5000 writes, 2000 keys: ~85% coordination-free, modeled ~6.8x lower
average latency than a total-order baseline (assumptions: 80 ms wide-area RTT,
0.05 ms local commit). Latency is MODELED, not measured on real links (heuristic
warning recorded) — a real deployment must measure wide-area behavior.

## 7. Interop (deferred, decoupled)
A memory/database layer integrates via the StoreBackend contract; a different
timing source or ordering scheme integrates via the L2 contract. Neither requires
the engine to import it. The engine runs standalone on the in-memory backend. (A
separate memory-layer project is intentionally NOT a dependency of D0.)

## 8. Registered falsifiers
- F1: any spacelike-independent write forced to coordinate -> performance defect.
- F2: any concurrent write silently dropped (not retained) -> correctness defect.
- F3: coordination-free commit claimed correct for a non-commutative same-key op
  without conflict retention -> correctness-scope violation.
- F4: any float/tolerance entering an ordering decision (ordering.py/geometry.py)
  -> exactness defect (float-guard is the standing check).
- F5: the engine importing a concrete database or an external memory project ->
  independence defect.

## 9. Claim scope
Certifies that the coordination-free engine executes and satisfies its gates, and
that its advantage is real and deterministic on a modeled geo workload. It is NOT a
production database, NOT a measured-latency benchmark on real links, and NOT a
consensus/replication protocol (fault tolerance and durability are future tracks).
Correctness of coordination-free commit assumes commutative/CRDT-safe ops or
conflict retention; non-commutative same-key ops still coordinate.
