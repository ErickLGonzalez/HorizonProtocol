# HorizonProtocol — Engineering Roadmap: From Disciplined Model to Defensible System

**Program:** HorizonProtocol (H-series) + MnemesisOS convergence

## Status addendum (this repository, current)

This document was supplied as a forward-looking roadmap. Against the
state described in its own header ("H1-H7 merged/green... manuscript
drafted"), this repository's actual state when the roadmap arrived was
H1-H6 + MNX1 - H7 had not yet been integrated, and the module names this
document references (`latency_gate`, `beq`, `multinode`, `memory`)
matched neither the shipped H6 code (which reuses `horizon.measure`, not
a `multinode` module) nor an as-yet-unintegrated H7. H7 was supplied and
integrated separately (`docs/h7-spec.md`) in the same pass that closed
part of this roadmap; the sections below are otherwise preserved as
delivered, with completed items marked.

**Closed in this pass:**
- **D1 (float-guard CI test):** `tests/test_float_guard.py` - AST-based,
  fails the build on a float literal, true division, `math.sqrt`, or
  `float(...)` outside a documented (module- or line-level) exception
  list. Wired into CI via the existing `unittest discover tests` step.
- **D2 (performance benchmark):** `scripts/bench.py` - gate cost at
  terrestrial/interplanetary magnitudes, cone-certificate verification
  time vs. station count, and ledger reachability vs. edge count with a
  fitted scaling exponent. Confirmed the suspected finding: `precedes()`
  fits ~O(edges^1.9) on this run (see `bench_report.json`), consistent
  with its full-edge-set scan per visited node. Reported, not fixed (a
  cache would be additive future work per this roadmap's own D2 note).
- **E1 (kernel consolidation):** `tests/test_kernel_consolidation.py`
  makes "exactly one canonical kernel" a permanent, CI-enforced invariant
  (no duplicate `causally_admissible`/`CausalLedger`/etc. definitions
  anywhere in the repo, and no file named `geometry.py`/`ledger.py`
  outside `horizon/`) rather than a one-time cleanup - the H6/MNX1/H7
  vendored copies were already deleted at their own integration time.
- **B1 (independent red-team harness, "H9" in this document):**
  implemented as a separate, non-H-numbered program `redteam/`
  (benchmark id `RT1`) rather than claiming a specific H-series slot -
  see `docs/redteam-spec.md`. Five attack classes, 11,000+ deterministic
  trials, zero bypasses as of this writing.
- **H7** (deep-space latency-budget gate + BE(Q) tracker) integrated; see
  `docs/h7-spec.md`, including an erratum found and fixed during
  integration (a squared-margin/nanosecond-unit mismatch in the original
  `latency_gate.py` that left its APPARATUS_LIMITED band practically
  inert at interplanetary scale).

**Not attempted in this pass (explicitly deferred, not silently
dropped):**
- **A1/A2 (H8, genuine multi-node capture):** requires real,
  geographically-separated hosts under the operator's control; out of
  scope for an automated session without provisioned infrastructure.
- **C1 (formally verified kernel):** requires a proof assistant (Lean 4
  or Dafny) not installed in this environment.

---

*Original document follows, unedited.*

---

**Program:** HorizonProtocol (H-series) + MnemesisOS convergence
**Status at time of writing:** H1–H7 merged/green; MnemesisOS convergence (MNX1)
green; manuscript drafted. All results run on computed or synthetic-fixture data.
**Purpose of this document:** define the next engineering phase, whose single
theme is *making contact with reality and with adversaries* — closing the gap
between an internally consistent, honestly-labeled model and a system a skeptic
would call validated.

**Governing invariants (unchanged, apply to every task below):** stdlib-only for
runtime/verifier/test; exact integer arithmetic on every security gate; additive
changes only; SOUND/HEURISTIC tags with located warnings; verifiers never import
simulators; deterministic certificates; negative controls with explicit witnesses;
claim-scope firewall in every spec (`ENGINEERING_REFERENCE`, `promotion_allowed:
false`, `empirical_claim: NONE`); zip deliverables < 25 MB; the repo owner pushes.

---

## 0. The one-paragraph thesis

The program's greatest strength — relentless honesty discipline — makes one gap
conspicuous: nothing here has touched a real clock or a real photon, and every
rejection so far is the system rejecting inputs it constructed. Three moves close
that gap, in priority order: **(P1) real capture** makes the system *true*;
**(P2) an independent red-team harness** makes it *trusted*; **(P3) a formally
verified kernel** makes it *rigorous*. Two cheap supporting tasks — **(P4) a
float-guard CI test** and **(P5) a performance benchmark** — defend the central
method claim and answer the deployability question. A final **(P6) consolidation**
pass removes the vendored-kernel drift risk the overlays have introduced.

Ranked by leverage: P1 (makes it real) → P2 (makes it trusted) → P3 (makes it
rigorous), with P4/P5 folded in alongside and P6 as hygiene.

---

## Phase A — Real-world contact (highest leverage)

### A1. Sprint H8 — Genuine multi-node capture

**Problem it solves.** H5/H6 have the *shape* of measurement but run on
`SYNTHETIC_CONSISTENT` fixtures. No cone certificate has ever been computed from
a timestamp a machine actually measured. This is the first question a skeptic
asks and the thing that converts the program from model to system.

**Deliverable.** A capture-and-verify pipeline producing the first cone
certificate over authentic network latency between real, geographically separated
hosts.

**Scope.**
- **Nodes:** 3 minimum (triangle enables cross-checking), ideally 4–5, in
  genuinely separated regions (e.g. three small cloud VPS instances on different
  continents, or three physical machines on different networks). Record each
  node's surveyed position (data-center published coordinates, or GPS if
  physical) converted to the nm lattice via the existing H6 `geo_frame`.
- **Timing source, tiered by rigor:**
  - Tier 1 (minimum): NTP-disciplined system clocks; declared U_ns ≈ 5 ms.
  - Tier 2 (better): PTP (IEEE 1588) where the network supports it; U_ns ≈ 50 µs.
  - Tier 3 (aspirational): GNSS-disciplined oscillators; U_ns ≈ 1 µs.
  Record the tier and U_ns per node in the certificate. The budgeted gate from
  H5/H6 already consumes U_ns; H8 supplies *measured* rather than computed inputs.
- **Protocol:** one node emits a hashed event; all nodes record measured receive
  times via a timestamping capture (extend the quarantined `capture.py` from H6
  into an authenticated, signed capture — see A2 dependency). Build the cone
  certificate; classify each receipt ADMITTED / REJECTED / APPARATUS_LIMITED
  under the measured U_ns.

**Honest expectations (write these into the spec before running).**
- Over real internet paths, signals travel through fiber at ~0.6c and routes are
  not straight lines, so the raw one-way times will *exceed* the vacuum light
  time. The gate must therefore certify *consistency* ("could a real signal path
  produce this?"), not the tight vacuum bound. This is exactly the c_eff < 1
  budgeted gate; H8 is where it earns its keep.
- Expect many receipts to land APPARATUS_LIMITED at NTP tier — clock error (ms)
  will dominate the geometry at continental scale (tens of ms). **This is a
  successful outcome, not a failure:** the system correctly reporting that
  millisecond clocks cannot resolve millisecond geometry is the discipline
  working. Tighter tiers (PTP/GNSS) move receipts from APPARATUS_LIMITED to
  ADMITTED, and demonstrating that *transition* across tiers is the strongest
  possible result.

**Gates.**
- H8-A: capture pipeline records real timestamps from ≥3 real nodes;
  deterministic *replay* of a committed capture reproduces identical verdicts.
- H8-B: honest capture yields ADMITTED or APPARATUS_LIMITED per receipt (never a
  spurious REJECTED for a real, in-budget signal).
- H8-C: a **live spoof control** — a fourth process claiming to emit from a
  distant node while actually co-located with the verifier — is REJECTED (or,
  honestly, flagged if NTP error masks it, which itself is a documented finding
  about the tier's resolution).
- H8-D: tier-transition demonstration — the same geometry re-run at a tighter
  declared U_ns moves at least one receipt from APPARATUS_LIMITED to ADMITTED.

**Registered falsifiers.** F1: a real in-budget signal REJECTED → gate or budget
defect. F2: a co-located spoof ADMITTED at a tier whose U_ns should resolve it →
security defect. F3: capture non-determinism on replay of a committed dataset.
F4: any raw measured time presented as a vacuum-light result (must carry c_eff).

**Effort:** medium. The verification code largely exists (H5/H6); the new work is
the capture harness, node provisioning, and honest handling of the tiers. The
intellectual content is in the expectations section, not the code.

### A2. Signed capture (prerequisite slice of A1)

Extend `capture.py` into an authenticated capture: each node signs its
(event_hash, position, receive_time) receipt with a per-node key (HMAC as the
stdlib stand-in, with a documented note that Ed25519 is the deployment target).
This is what makes H8-C meaningful — without signatures a spoof is trivial. Keep
it a separate, small module so the trusted verifier still imports no capture code.

---

## Phase B — Adversarial hardening (makes it trusted)

### B1. Sprint H9 — Independent red-team harness

**Problem it solves.** Every REJECTED verdict today rejects inputs the system
itself constructed — cooperative forgeries. H3-C is the only genuine adversary in
the codebase, and it is one we invited. Real hardening requires an *independent*
attacker that tries to make gates accept without authorization.

**Deliverable.** A red-team module, separate from all verifiers, that attempts to
pass each gate illegitimately and is scored on whether anything slips through.
Zero successful bypasses is the pass condition; any bypass is a filed defect with
a regression test.

**Attack classes (minimum set).**
- **Timing fuzz:** property-based generation of (position, time) tuples near the
  light-cone boundary; assert no spacelike pair is ever ADMITTED and no timelike
  pair ever REJECTED. Use stdlib `random` with frozen seeds (keep stdlib-only),
  or permit `hypothesis` *in tests only* if the team accepts a test-time dep.
- **Boundary attacks:** exhaustive probing of the resolve-margin band — can an
  attacker tune U_ns or a receipt time to force APPARATUS_LIMITED where the true
  verdict is REJECTED (turning a rejection into an ambiguous non-answer)?
- **Replay:** resubmit a valid receipt for a different event / time / node; assert
  event-binding and position gates catch it.
- **Clock-skew exploitation:** within a declared U_ns budget, search for the
  worst-case skew that maximizes admitted forgeries; report the residual attack
  surface as an explicit number (attacks admitted per million attempts at each
  tier). This *quantifies* assurance-grade rather than asserting it.
- **Ledger attacks:** attempt to insert an edge that creates a causal cycle or a
  backward-in-time dependency; assert the DAG admissibility gate refuses.

**Gates.** H9-A through H9-E, one per attack class, each PASS = zero illegitimate
acceptances (or, where the tier genuinely cannot resolve, a *quantified and
documented* residual, not a silent pass).

**Registered falsifiers.** F1: any attack admitted that the stated adversary
model claims to exclude. F2: the harness importing any verifier internals that
would let it "cheat" its way to a pass (it must attack through the public gate
only). F3: a residual attack surface reported as zero when fuzzing finds nonzero.

**Effort:** medium, high value. This is the difference between "we tested it" and
"we tried to break it and reported what we found."

---

## Phase C — Rigor (makes it defensible at the foundation)

### C1. Formally verified admissibility kernel

**Problem it solves.** The entire stack reduces to one predicate,
`causally_admissible` — a ~5-line integer comparison. It is small enough to
*prove* correct rather than merely test, which almost no security project can say
of its core.

**Deliverable.** A machine-checked proof, in a proof assistant (Lean 4 or Dafny),
of the theorem:

  For all integer t1,t2 and integer 3-vectors p1,p2, the integer predicate
  (t2 ≥ t1) ∧ ((c·(t2−t1))² ≥ |p2−p1|²) holds **iff** the real-number condition
  (t2 ≥ t1) ∧ (c·(t2−t1) ≥ ‖p2−p1‖) holds,

i.e. the exact-integer gate agrees with the real light-cone condition on every
lattice input, with no rounding gap. Also prove `min_light_time_ns` returns the
true minimal admissible dt (the isqrt boundary-correction is correct).

**Why it is finishable.** The predicate is total, integer, and branch-free; the
proof is a matter of squaring/monotonicity lemmas the assistant's arithmetic
tactics largely discharge. Bounded scope, high symbolic payoff.

**Deliverable form.** A `formal/` directory with the proof source, a README
explaining the correspondence to `geometry.py`, and a note in the manuscript that
the kernel is machine-checked. This is the kind of artifact that changes how a
reviewer weights everything built on top of it.

**Effort:** medium; specialized skill (proof assistant) but bounded surface.

---

## Phase D — Cheap supporting tasks (fold in alongside)

### D1. Float-guard CI test (self-defending exactness claim)

**Problem.** The central method claim — "no floats in any security gate" — lives
in discipline and review, not enforcement.

**Deliverable.** A stdlib `ast`-based test that walks every trusted-path module
(`geometry`, `certificate`, `ledger`, `latency_gate`, `beq`, `multinode`, `memory`
+ orderings) and **fails the build** if it finds: a float literal, a `/` true-
division, `math.sqrt`, or a `float(...)` call, anywhere outside docstrings and
comments. Whitelist the deliberate float boundary (geodesy in `geo_frame`, the
`_float` reporting fields in `beq`) by explicit, documented exception list.

**Effort:** small (a few hours). Wire into `.github/workflows/gates.yml`.

### D2. Performance benchmark + scaling curve

**Problem.** Gate cost and ledger scaling are uncharacterized. `(c·dt)²` at
interplanetary scale is a large bignum; the ledger's `precedes` reachability
query looked O(edges) per call and will bite at scale.

**Deliverable.** A `bench/` harness (stdlib `time.perf_counter_ns`) reporting:
per-gate latency at terrestrial and interplanetary magnitudes; cone-certificate
verification time vs node count; ledger admissibility + reachability time vs
edge count, with a fitted scaling curve. Output a JSON perf certificate and a
one-page summary. If reachability is worse than linear at useful sizes, file it
and consider a transitive-closure cache (additive, does not touch the gate).

**Effort:** small–medium. Answers "demonstrator or deployable infrastructure?"

---

## Phase E — Hygiene (prevents future drift)

### E1. Kernel consolidation

**Problem.** H1–H7 and the MnemesisOS overlay each *vendor* their own
`geometry.py` (and some `ledger.py`). Additive-only holds within the main repo,
but the overlays can silently diverge from the canonical kernel.

**Deliverable.** One shared `horizon` package; every overlay imports from it
rather than carrying a copy. A single top-level `run_all.py` that runs H1–H9 +
MNX + bench + float-guard, and a CI matrix (Py 3.9/3.11/3.12) that fails on any
degradation. Finish wiring `validate_certificates.py` (hash-drift detection) as
the enforcement that a certificate always matches the code that produced it.

**Effort:** small–medium, mechanical. Do this *after* H8/H9 land so it consolidates
a stable set rather than a moving target.

---

## Sequencing and decision points

**Recommended order:** A (H8 real capture) → B (H9 red-team) → C (formal kernel),
with D1/D2 folded in during A/B and E1 as the closing consolidation. Rationale:
each phase answers the next-most-damaging skeptical question in turn — *is it
real, is it trusted, is it proven* — and the cheap defenders (float-guard,
benchmark) ride along without their own critical path.

**Thresholds that change the plan.**
- If real capture (H8) shows the budgeted gate cannot cleanly separate honest
  signals from spoofs at any affordable timing tier, that is a genuine *finding*
  about the primitive's terrestrial resolution — file it, and let it reshape the
  manuscript's claims (it strengthens the honesty, it does not sink the work).
- If red-team (H9) finds a boundary/skew bypass, freeze promotions and fix before
  any further sprint — a known bypass outranks new features.
- If the formal proof (C1) surfaces a lattice input where the integer gate and
  the real condition disagree, that is a kernel defect of the highest severity —
  it would mean the exactness claim is false, and everything above it must be
  re-audited.
- If performance (D2) shows the gate is milliseconds not microseconds at
  interplanetary magnitudes, the deep-space (H7) framing needs a stated
  throughput caveat.

**What NOT to do next.** No new *primitives* until real capture and red-team land
— breadth is not the gap, contact-with-reality is. No relaxing the stdlib-only or
exact-integer invariants to chase performance; if a bignum path is slow, cache
around it additively rather than converting a gate to floats.

---

## Definition of done for this phase

- H8 emits at least one cone certificate from genuinely measured timestamps
  across ≥3 real nodes, with tier and U_ns recorded, and a demonstrated
  APPARATUS_LIMITED→ADMITTED transition across timing tiers.
- H9 red-team runs all attack classes with zero undocumented bypasses; any
  residual attack surface is quantified per tier, not asserted absent.
- The admissibility kernel carries a machine-checked correctness proof.
- Float-guard and the benchmark run in CI; certificates validate against source
  hashes; one shared kernel, no vendored copies.
- Every new sprint ships code + tests + deterministic certificate + spec with
  registered falsifiers, and the manuscript is updated to cite the real-capture
  result and the formal kernel.

*Closing note: the work is already unusually honest. This phase spends that
honesty where it pays most — by going and finding out whether the thing works on
real signals, whether it survives a real attacker, and whether its one load-
bearing line is provably correct. Those three answers, in that order, are what
turn discipline into evidence.*
