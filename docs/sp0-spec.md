# SP-0 Engineering Specification — Worldline Refactor (moving-node foundation)

**Program:** HorizonProtocol · **Sprint:** SP-0 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 0. Repo-history record — conclusions this spec builds on

*(Recorded here so the reasoning is repo history, not just chat.)*

1. **Int-vs-float kernel benchmark (HorizonProtocol #10, merged).** A
   faithful float64/float32 light-cone gate vs the frozen integer gate.
   Findings: float's verdict-mismatch vs the exact condition rises with
   magnitude and is worst at interplanetary scale, where float64's mantissa
   cannot resolve a nanometer offset (real security-verdict flips — admits
   spacelike pairs, rejects timelike). Integer reproducibility divergence is
   exactly 0.0 across precision / summation-order / sqrt-algorithm settings.
   Honest surprise: integer was *faster* than naive float64 at every
   magnitude tested in that environment (no sqrt; both sides squared) — not
   the expected bignum-loses story, and scoped to that environment. Thesis
   remains soundness + reproducibility, not speed. -> This is why a
   spaceship system must be integer: at Mars distances float cannot resolve
   the lattice, so a float trajectory would flip admissibility. The exact
   integer worldline is mandatory, not a preference. See
   `docs/int-vs-float-results.md`.

2. **Federated cross-region reorder measurement (MnemesisOS #548, merged,
   admissible).** Real US<->Europe-West link, PTP chrony, lag ~83ms, clock
   offsets us-to-sub-ms (offset << lag => admissible). Measured
   reorder_ratio by phase: steady 0.000/0.000, peak 0.000/0.006,
   partition->reconnect 0.845/0.989. Conclusion: on a healthy link this
   workload barely reorders (substrate is safe insurance there); the
   substrate's value is concentrated in partition/reconnect events (network
   split / failover / offline-then-sync), where newest-wins would corrupt
   ~85-99% of contested state and the causal substrate holds it correct.
   Honest caveat: steady~=0 may be driven-write-rate-dependent; it was a
   driven, not organic, workload. -> A spaceship makes this permanent and
   physical: relativistic proper-time divergence means ship-time and
   ground-time never share a "now", so causal-lineage ordering is
   continuously mandatory, not just during partitions.

3. **Causal-substrate field-benchmark null (MnemesisOS #540, merged, honest
   negative).** Real LLM judge (gpt-5-mini, retain-both) vs
   FC-SH/LongMemEval/LoCoMo: causal ties newest-wins because those datasets
   are 100% ordering / 0% semantic residue with arrival-order ===
   causal-lineage (no out-of-order regime unless fabricated, which was
   correctly refused). Default-on not justified by field data. -> Reinforces
   that the substrate earns its keep specifically in the out-of-order
   regime — which a moving spaceship produces continuously by physics.

4. **Weak-form causal-divergence theorem (manuscript section 2).** Observers
   diverge into disjoint causal domains / algebras / proper-times; there is
   no shared "now" (permanence conditional on the dark-energy equation of
   state). -> The spaceship is the operational case of this theorem: each
   node stamps its own proper time and the light cone reconciles them,
   because a shared clock provably does not exist.

**One-line synthesis for the repo:** the spaceship is not a new
application — it is the regime where every prior honest narrowing
(integer-because-float-cant-resolve-interplanetary, causal-because-no-
shared-clock, APPARATUS_LIMITED-because-light-delay-makes-position-
uncertain) becomes simultaneously load-bearing. SP-0 lays the foundation by
making position a function of time.

## 1. Objective

Promote each node's fixed `pos_nm` to an exact-integer worldline
`pos_nm(t)` evaluated at event-time, so the light-cone gate works for a
moving node (a spaceship) — additively, with the frozen kernel untouched
and every existing Earth test still green. This is the foundation the
spaceship series (SP-1..SP-3) builds on.

## 2. What changes (additive, kernel frozen)

The kernel `causally_admissible(t1, p1, t2, p2)` in `horizon/geometry.py`
takes positions as fixed points and is NOT modified by SP-0 — it is
machine-checked (`formal/kernel_proof.py`'s T1 proves it equivalent to the
real light-cone condition), and, independently of the formal proof,
`horizon/geometry.py` as a whole file is SHA-256-pinned by several already
-committed certificates (`certificates/h5_certificate.json` through `h9`,
`h8_live_certificate.json`, `h8_live_ntp_certificate.json` — see
`scripts/validate_certificates.py`'s `source_hashes` check). Even an
additive append to `horizon/geometry.py` breaks those certificates' hash,
so SP-0 does not touch that file at all — confirmed by
`git diff --stat horizon/geometry.py` showing no changes.

SP-0 adds a new module, `horizon/worldline.py`, layered entirely above the
kernel:

- **`Worldline`** — an exact-integer trajectory abstraction with one
  method: `position_at(t_ns) -> (x_nm, y_nm, z_nm)` returning integer nm at
  integer ns.
  - `FixedWorldline(pos_nm)` — a constant; this is exactly today's fixed
    node, so all existing behavior is the constant-worldline special case
    (nothing breaks).
  - `LinearWorldline(p0_nm, t0_ns, v_nm_per_ns)` — a coasting node; position
    is `p0 + v*(t - t0)`, exact on the integer lattice. `v_nm_per_ns` is a
    length-3 sequence; each component is a plain integer (whole nm/ns) or
    an exact `(numerator, denominator)` rational pair for sub-unit
    velocities, floor-divided (`//`) to an integer nm result.
- **`causally_admissible_wl(a, t1, b, t2)`** — a thin wrapper, living in
  `horizon/worldline.py` and *importing* (never redefining) the frozen
  `causally_admissible`: evaluate `p1 = a.position_at(t1)`,
  `p2 = b.position_at(t2)`, then call `causally_admissible(t1, p1, t2, p2)`
  unchanged. The moving-node logic lives entirely in evaluating the
  worldline to a point; the admissibility test is the same exact-integer
  kernel, imported from `horizon/geometry.py` and never copied.

**Exactness rule (non-negotiable, per conclusion #1):** `position_at`
returns exact integers. No float enters a worldline evaluation. Fractional
velocity is carried as an exact integer/rational (numerator, denominator)
pair and floor-divided (`//`, never `/`) to an integer nm result — the
whole point is that at interplanetary scale float cannot resolve the
lattice, so the worldline must be as exact as the kernel it feeds.
`horizon/worldline.py` is registered in `tests/test_float_guard.py`'s
`TRUSTED_MODULES`, so CI enforces zero floats in it, the same as every
other gate-deciding module.

## 3. Tests (additive; all existing tests stay green)

`tests/test_sp0_worldline.py`:

- **SP0-A (fixed-worldline equivalence):** for boundary vectors across
  every magnitude in `benchmark/int_vs_float/boundary_gen.py` (metric,
  continental, interplanetary), `causally_admissible_wl` with two
  `FixedWorldline`s returns byte-identical verdicts to
  `causally_admissible` called directly on the same points, plus the H1-A
  null-ray boundary cases by hand. Proves the refactor changes nothing for
  stationary nodes.
- **SP0-B (linear exactness):** `LinearWorldline` evaluated at a range of
  times returns exact integer positions matching hand-computed reference
  arithmetic, for both whole-integer and exact-rational velocities
  (including negative-denominator normalization and a rejected
  zero-denominator); a direct AST scan of `horizon/worldline.py` confirms
  zero float literals / true-division / `sqrt`/`float()` calls, tying to
  falsifier F1.
- **SP0-C (moving-node admissibility):** a node moving between two events —
  verifies the gate uses `position_at(t_event)` for each endpoint (not a
  frozen snapshot), that a signal admissible against the evaluated
  positions is correctly ADMITTED while one that would require FTL closure
  is REJECTED, and an interplanetary-scale case built from the exact
  on-cone boundary vector where the nanometer lattice matters (admitted
  exactly on the cone, rejected 1 nm past it).
- **SP0-D (integer-necessity tie-in):** reuses the #10 int-vs-float
  benchmark's `causally_admissible_float` — at interplanetary distance, a
  `LinearWorldline` evaluated to a point 1000 nm past the null cone
  (spacelike, correctly REJECTED by the integer worldline) is wrongly
  ADMITTED when the same evaluated point is fed through a faithful float64
  gate. Ties SP-0 directly to the merged benchmark's finding.

## 4. Deliverables

1. `horizon/worldline.py` — `Worldline`, `FixedWorldline`,
   `LinearWorldline` (exact-integer `position_at`), and
   `causally_admissible_wl` (imports, never redefines, the frozen kernel).
2. `tests/test_sp0_worldline.py` — SP0-A..D.
3. `tests/test_float_guard.py` — `horizon/worldline.py` added to
   `TRUSTED_MODULES` so CI enforces the exactness rule on it going forward.
4. `docs/sp0-spec.md` — this document.
5. `horizon/geometry.py` — UNCHANGED (`git diff --stat` shows zero lines
   touched); the frozen `causally_admissible` / `admissibility_witness`
   bodies are byte-identical to before SP-0.

## 5. Registered falsifiers

- **F1:** any float in a `position_at` evaluation -> exactness defect
  (conclusion #1 says float can't resolve the interplanetary lattice; a
  float worldline reintroduces the very unsoundness the integer kernel
  removes). Checked by `tests/test_float_guard.py` (module-level) and
  `test_sp0_worldline.py`'s direct AST scan.
- **F2:** `causally_admissible_wl` with two `FixedWorldline`s ever
  disagreeing with the frozen `causally_admissible` -> the refactor broke
  the stationary case. Checked by SP0-A across every boundary magnitude.
- **F3:** the frozen kernel function body — or the `horizon/geometry.py`
  file containing it — modified in any way -> scope violation (wrap, don't
  alter). Checked by `git diff --stat horizon/geometry.py` being empty, and
  transitively by every certificate hash check in
  `tests/test_a_schema.py` / `scripts/validate_certificates.py` staying
  green.
- **F4:** a `LinearWorldline` returning a position that doesn't match exact
  integer/rational arithmetic -> trajectory-evaluation defect. Checked by
  SP0-B's hand-computed reference comparisons.

## 6. What SP-0 deliberately does NOT do (deferred, in dependency order)

- **SP-1 (occultation = partition/reconnect):** ship goes behind a planet,
  link drops, both keep writing, signal reacquires — the same
  partition->reconnect test shape proven on Earth (#548), now with a
  physical cause and a light-delay reconnect burst. The causal substrate
  (mandatory here per conclusion #2) orders the reconnect flood.
- **SP-2 (trajectory-uncertainty envelope -> APPARATUS_LIMITED):** position
  known only as of last signal minus light-travel time; a cone of
  possibility that grows with time-since-contact and collapses on new
  signal. Two-floor gate: REJECTED only against the absolute physical floor
  (no possible trajectory fits).
- **SP-3 (proper-time divergence):** two nodes at different
  velocities/potentials; events ordered by substrate lineage despite
  divergent clocks — the weak-form theorem (conclusion #4) operationalized,
  combining the integer worldline and the causal substrate.

Each of SP-1..SP-3 maps onto a test shape already proven on Earth; SP-0 is
the foundation that makes position a function of time so they can be built.

## 7. Firewall

- Do NOT modify `horizon/geometry.py` in any way (not just the two named
  kernel functions) — it is byte-hash-pinned by multiple committed
  certificates in addition to being machine-checked.
- No float anywhere in a worldline evaluation (exact integer/rational
  only).
- Do NOT break the stationary case — `FixedWorldline` must reproduce today
  exactly.
- Additive only: new worldline module + new tests; all existing tests stay
  green.

## 8. Reproduction

```bash
python3 -m unittest tests.test_sp0_worldline -v
python3 -m unittest discover -s tests   # full suite, including certificate hash checks
```
