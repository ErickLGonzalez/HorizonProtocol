# SP-3 Engineering Specification — Proper-Time Divergence

**Program:** HorizonProtocol · **Sprint:** SP-3 (capstone of the spaceship
series) · **Tier:** BENCHMARK · **Claim class:** ENGINEERING_REFERENCE ·
**Promotion:** none · **Empirical claim:** NONE · **Builds on:** SP-0
(`Worldline`, #11), SP-1 (occultation + light-delay, #12), SP-2
(uncertainty envelope / two-floor gate), and the causal substrate's vector
clocks (`mnemesis.vclock`, MNX1).

## 0. Positioning record (repo history)

*(Per SP-0 §0 convention.)*

- **The physics is the manuscript's weak-form theorem:** observers on
  divergent worldlines accumulate different proper time
  (`dτ/dt ≈ 1 + Φ/c² − v²/2c²`), so no global simultaneity exists;
  permanence is conditional on the dark-energy equation of state. SP-3 is
  that theorem in code.
- **The distributed-systems analogue is prior art, and SP-3 aligns with
  it, not against it:** ordering by causal lineage instead of physical
  clocks is exactly what vector clocks (Fidge/Mattern 1988) and causal
  consistency do, and what LCC 2026 formalizes as the single-observer
  frame. **SP-3 does not claim "order by causality not clocks" as novel.**
  Its contribution is that here the clock divergence is *physically real
  and permanent* (relativistic), not merely skew/latency — so the
  substrate is not an optimization but the *only* correct mechanism, and
  the light cone (exact-integer, physical) is what reconciles the
  per-node proper times.
- **Applied gap (space) open as far as published work shows** (Starling/
  DSA, FAME, CCSDS use purpose-built consistency / master-clock
  correlation, not causal-lineage ordering across relativistic clocks).
  "Not found" ≠ "does not exist."

## 1. What was built (additive, on top of SP-0/SP-1/SP-2)

### 1.1 Per-node proper time (`horizon/proper_time.py`)
`weak_field_rate(v2_nm2_per_ns2, phi_nm2_per_ns2=0)` returns an exact
rational `(num, den)` for `dτ/dt_coord ≈ 1 + Φ/c² − v²/2c²` — deliberately
the weak-field, low-velocity expansion, NOT the exact relativistic
`sqrt(1 - v²/c²)`. **Honest note on this choice:** the exact relativistic
form is irrational for a generic velocity; this module's entire point is
to stay exact, so it uses the formula that is *already* rational in its
integer inputs rather than approximating an irrational one. This is
disclosed as an approximation of the physics (the manuscript itself writes
`≈`), not a claim of exact general relativity.

`ProperTimeClock(node_id, rate_num, rate_den, t0_coord_ns=0, tau0_ns=0)`
gives `tau_at(t_coord) = tau0 + floor(rate_num * (t_coord - t0_coord) /
rate_den)` — exact integer floor division (`//`), the same technique
`LinearWorldline` (SP-0) uses for rational velocity.

**The critical guard (F2 — the reason this module exists):**
`ProperTimeStamp` carries the `node_id` it was stamped by; its comparison
operators (`<`, `<=`, `>`, `>=`, `==`) RAISE `ValueError` if asked to
compare stamps from two DIFFERENT nodes. There is no shared "now" across
divergent proper times — a stray `stamp_a < stamp_b` across nodes fails
loudly at the point of the attempted comparison rather than silently
returning a physically meaningless answer.

### 1.2 Substrate ordering as the sole cross-node order (`horizon/reconcile.py`)
`Event(node_id, vclock, t_coord_ns, locator, proper_time_stamp=None)`
bundles a node's vector clock (lineage), its position in the shared
coordinate frame (`locator`: a `Worldline` for an exact position, or an
SP-2 `TrajectoryEnvelope` for an uncertain one), and — for provenance/
logging only — its own `ProperTimeStamp`.

`reconcile(event_a, event_b)` decides `event_a`'s relation to `event_b`
using ONLY: (1) vector-clock happens-before
(`mnemesis.vclock.happens_before`, unmodified — the causal-lineage
signal), and (2) the physical check on that claimed edge —
`causally_admissible_wl` (SP-0) when both positions are exact, or
`two_floor_verdict` (SP-2) when the target's position is an envelope.
`event.proper_time_stamp` is never read by `reconcile` — every returned
witness carries `"proper_time_used_for_ordering": False` as a literal,
checkable record of that.

**Verdict vocabulary note (an honest inconsistency in the source handoff,
resolved here):** section 1.3 of the handoff specifies
`BEFORE`/`AFTER`/`CONCURRENT`/`APPARATUS_LIMITED` as `reconcile`'s output;
its SP3-E description instead lists
`ADMITTED`/`REJECTED`/`APPARATUS_LIMITED`/`CONCURRENT`, reusing
`two_floor`'s vocabulary loosely. This module follows section 1.3's
explicit contract for `reconcile`'s return value and records the
underlying `ADMITTED`/`REJECTED`/`APPARATUS_LIMITED` physical check in the
witness's `physical_check.verdict` field, so both vocabularies are visible
and traceable to which check produced them — see `horizon/reconcile.py`'s
module docstring.

**Decision table** (`event_a` -> `event_b`):

| lineage | physical check | `reconcile` verdict |
|---|---|---|
| a before b | ADMITTED | `BEFORE` |
| a before b | APPARATUS_LIMITED | `APPARATUS_LIMITED` |
| a before b | REJECTED | `CONCURRENT` (lineage claim the cone forbids — never trusted) |
| b before a | (symmetric) | `AFTER` / `APPARATUS_LIMITED` / `CONCURRENT` |
| neither | — | `CONCURRENT` (no lineage edge either direction) |

## 2. Tests (`tests/test_sp3_proper_time.py`)

- **SP3-A:** `weak_field_rate` matches the hand-computed formula exactly;
  a stationary node's clock equals coordinate time exactly (rate 1/1); a
  moving node's clock strictly lags; two nodes at different velocities
  provably diverge over time by exact rational arithmetic. Runtime float
  inputs at every public boundary raise `TypeError` (F1), the same
  discipline as every prior SP module's `_require_int` guards.
- **SP3-B:** comparing `ProperTimeStamp`s across different nodes raises
  for every comparison operator; comparing within the same node is fine.
  A dedicated case confirms `reconcile`'s verdict and physical-check
  witness are IDENTICAL whether or not wildly misleading proper-time
  stamps are attached — proving no code path reads them (F2, the theorem's
  "no shared now" enforced in code, not just documented).
- **SP3-C (the headline):** the ship's clock has drifted far enough behind
  ground's (via the SAME weak-field rate divergence as SP3-A, accumulated
  over a long baseline) that comparing `tau` values directly gives the
  WRONG temporal order; `reconcile`, using only lineage + the light cone,
  recovers the correct order (`BEFORE`) — genuinely computed, not
  hand-asserted, and cross-checked against `causally_admissible_wl`
  directly.
- **SP3-D:** two genuinely concurrent events (no lineage edge at all) are
  retained as `CONCURRENT`; a *lineage claim* that the light cone forbids
  (the claimed predecessor is causally unreachable) is ALSO demoted to
  `CONCURRENT` rather than silently trusted — the #548 zero-false-
  supersession invariant, now under divergent relativistic clocks (F3).
- **SP3-E (full stack):** composes SP-1's `occultation_interval` (the
  ship's last confirmed contact before going dark), SP-2's
  `TrajectoryEnvelope` (the growing uncertainty since that contact,
  through and past the blackout), and SP-3's divergent proper-time
  clocks. `reconcile` returns `APPARATUS_LIMITED` — the honest verdict —
  with a witness whose `physical_check` visibly came from `two_floor`
  (carries `radius_nm`) and whose `proper_time_used_for_ordering` is
  `False`. A second case shows a tighter, fresher envelope resolves the
  SAME lineage edge definitively to `BEFORE` — the SP2-E narrowing effect,
  now demonstrated through the full stack.

## 3. Deliverables

1. `horizon/proper_time.py` — `weak_field_rate`, `ProperTimeStamp`,
   `ProperTimeClock` (exact-rational per-node proper time; no
   shared-clock conversion; the cross-node comparison guard).
2. `horizon/reconcile.py` — `Event`, `reconcile` (cross-node verdict via
   lineage + the light cone, never proper time).
3. `tests/test_sp3_proper_time.py` — SP3-A..E.
4. `docs/sp3-spec.md` — this document.
5. `tests/test_float_guard.py` — both new modules added to
   `TRUSTED_MODULES`.
6. `horizon/geometry.py`, `horizon/worldline.py`, `horizon/occultation.py`,
   `horizon/light_delay.py`, `horizon/uncertainty.py`, `horizon/two_floor.py`
   — UNCHANGED (`git diff --stat` shows zero changes to any of them).

## 4. Registered falsifiers

- **F1:** any float in proper-time or reconciliation (a floated Lorentz
  factor) → exactness defect. Checked by `tests/test_float_guard.py` (both
  modules in `TRUSTED_MODULES`) and SP3-A's runtime `TypeError` tests.
- **F2:** any cross-node ordering decided by comparing two nodes' proper
  times directly → preferred-frame violation, contradicting the weak-form
  theorem — THE falsifier SP-3 exists to forbid. Checked by SP3-B, both as
  a direct comparison-raises test and as a "verdict is identical
  with/without proper-time stamps attached" behavioral test.
- **F3:** any false-supersession across divergent clocks → the #548
  invariant broken. Checked by SP3-D against `causally_admissible_wl`
  ground truth directly, for both the no-lineage-edge and the
  lineage-claim-forbidden-by-physics cases.
- **F4:** reconciliation claiming `BEFORE`/`AFTER` without both lineage
  AND light-cone support → unsound ordering. Checked by `reconcile`'s
  decision table (section 1.2) and exercised by every SP3-C/D/E test.
- **F5:** claiming "order by causality not clocks" as novel → scope
  violation. Addressed in section 0 above (cites Fidge/Mattern 1988 and
  LCC 2026); the novelty claimed is physical/relativistic permanence +
  exact cone reconciliation, not the ordering principle itself.
- **F6:** frozen kernel or any prior SP module modified → scope violation.
  Checked by `git diff --stat` on all six prior modules showing zero
  changes.

## 5. What SP-3 completes

With SP-3 the spaceship series is whole: position is an exact worldline
(SP-0), survives physical blackout (SP-1), honestly reports position
uncertainty (SP-2), and now orders events correctly even when the clocks
themselves diverge relativistically (SP-3) — using causal lineage
reconciled by the exact light cone, never a shared clock. This is the
weak-form theorem operationalized end to end: a system that stays
causally correct for a moving ship across the solar system.

## 6. Reproduction

```bash
python3 -m unittest tests.test_sp3_proper_time -v
python3 -m unittest discover -s tests   # full suite
git diff --stat horizon/geometry.py horizon/worldline.py horizon/occultation.py \
  horizon/light_delay.py horizon/uncertainty.py horizon/two_floor.py   # all empty
```
