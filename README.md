# HorizonProtocol

[![gates](https://github.com/ErickLGonzalez/HorizonProtocol/actions/workflows/gates.yml/badge.svg)](https://github.com/ErickLGonzalez/HorizonProtocol/actions/workflows/gates.yml)

**Trust rooted in causal structure.** A cryptographic stack whose certificate
authority is the speed of casuality.

HorizonProtocol is the engineering companion to a simple physical thesis: an
observer's operational reality is worldline-indexed — its causal domain,
proper-time history, accessible observables, and assigned state all attach to
a trajectory, and the light cone bounds what any party can have done. Signals
can be delayed but never accelerated past *c*; therefore arrival times are
unforgeable geometric evidence. This repository turns that constraint into
verifiable primitives.

## The layer map

| Layer | Primitive | Status |
|---|---|---|
| L0 | Timing fabric (synchronized, surveyed stations) | modeled in H1 |
| L0 | Timing fabric over real measurements | **H5 (this release)** |
| L0 | Timing fabric over real measurements, real geography | **H6 (this release)** |
| L0 | Genuine multi-node capture, signed receipts, tiered clock uncertainty | **H8 (this release)** |
| L0.5 | Deep-space latency-budget gate + BE(Q) collusion resistance | **H7 (this release)** |
| L1 | Distance bounding / position proofs | **H3 (this release)** |
| L2 | Relativistic commitments | **H2 (this release)** |
| L3 | Cone certificates + causal ledger | **H1 (this release)** |
| L4 | Causal-disjointness independence beacons | **H4 (this release)** |

## H1 — Cone Certificates & the Causal Ledger

Everything runs on an exact integer lattice: positions in **nanometers**,
times in **nanoseconds**, so that *c* = 299,792,458 nm/ns **exactly**. The
security-critical predicate — "does event B lie in the closed future light
cone of event A?" — is the pure integer comparison

```
(c · Δt)² ≥ Δx² + Δy² + Δz²
```

No floats, no tolerances, no rounding anywhere in an admissibility decision.
This predicate is machine-checked, not just tested: `formal/` proves five
theorems about it (faithfulness to the real light-cone condition, sharp
null-cone boundary, future monotonicity, and boundary-search minimality) with
the Z3 SMT solver over the integers (`docs/formal-kernel-spec.md`).

**Cone certificate:** an event (hash + claimed emission time/position) plus
signed receipts from surveyed stations. The standalone verifier re-checks,
from certificate contents alone: station identity, receipt authenticity,
event binding, surveyed position, and the exact light-cone gate for every
receipt. Verdicts are `PASS` or `REJECTED` with the violated gate and its
exact integer witness.

**Causal ledger:** a DAG whose dependency edges must pass the same gate.
Spacelike-separated events are stored as *concurrent* — the ledger never
fabricates an order the geometry does not certify.

## Quickstart

```bash
python3 scripts/run_all.py              # runs every H1-H9 + MNX1 + RT1 gate set + certificate validation
python3 -m unittest discover tests -v   # 239 tests
python3 scripts/validate_certificates.py
python3 scripts/bench.py                # performance report (informational, not a gate)
python3 scripts/demo_mnx.py             # MnemesisOS causal-memory demo, end to end
python3 scripts/demo_h7.py              # deep-space telemetry demo: honest probe vs. Earth spoofer

# optional: the machine-checked kernel proof (the ONE non-stdlib dependency
# in this repository, confined entirely to formal/ - see docs/formal-kernel-spec.md)
pip install z3-solver && python3 scripts/run_formal.py
```

Requires Python 3.9+. Standard library only, with one documented, optional
exception (`z3-solver`, for `formal/` alone - `scripts/run_all.py` reports it
as SKIPPED rather than failing if it isn't installed).

## Continuous verification

Every push and pull request to `main` re-runs the full test suite, every
H-series gate set, and the certificate validator across Python 3.9, 3.11,
and 3.12 (`.github/workflows/gates.yml`). The build fails on any
degradation - "all gates green" is enforced by CI, not asserted in prose.

## Discipline

- Exact arithmetic on every security gate (`SOUND` tag); heuristic components
  carry located warnings in the aggregate certificate.
- Negative controls are first-class: forged MACs, FTL receipts, rogue
  stations, wrong-event bindings, and position lies must be REJECTED
  deterministically, each with an explicit witness.
- The verifier is standalone: it never imports the world simulator, and a
  third party can re-verify any certificate from its contents plus the public
  station registry.
- Certificates record source hashes, gate results, soundness tags, the
  adversary model, and the aggregate verdict.

## Honest limits (read before trusting)

H1's adversary model is a **single forger without station keys**. Colluding
multi-site adversaries defeat *classical* position verification in general
(Chandran–Goyal–Moriarty–Ostrovsky); closing that gap is the quantum layer's
job (bounded-entanglement QPV), which is out of scope here. HMAC with
demo-derived keys stands in for real signatures. Simulated arrival times are
computed, not measured. See `docs/h1-spec.md` for the full statement.

## Shipped sprints

- **H2** — relativistic commitment simulator (two-agent Kent-style sustain
  rounds; binding gate = the same integer cone predicate).
- **H3** — distance bounding with an explicit collusion attack demonstrator
  (the classical break, reproduced honestly, as a negative control).
- **H4** — independence beacons: entropy XOR from stations with certified
  spacelike emission events.
- **H5** — real-measurement bridge: cone certificates over actual measured
  arrival times instead of computed ones, gated by an explicitly declared,
  certificate-recorded uncertainty budget (`docs/h5-spec.md`). Refuses to
  certify a marginal measurement as PASS — it reports `APPARATUS_LIMITED`
  instead, naming the node and margin.
- **H6** — the same H5 gate, over real cloud-region geography instead of an
  abstract site rig: WGS84 lat/lon/alt quantized once to the exact nm
  lattice (`horizon/geo_frame.py`), then HMAC-authenticated stations at
  real distances up to ~12,000 km (`docs/h6-spec.md`). No new gate math —
  H6 is real-geography input feeding H5's already-reviewed dual-floor
  budgeted classifier and authenticated receipts, not a second
  implementation.
- **H7** — deep-space groundwork: a single latency-budget gate unifying
  authenticated telemetry and trajectory attestation over real Earth-Mars
  distances (3-22 min one way; vacuum c_eff = 1, the *tightest* form of
  the exact gate), plus an exact-fraction bounded-entanglement (BE(Q))
  tracker supplying the collusion resistance classical distance-bounding
  cannot (`docs/h7-spec.md`). Reuses `geometry.min_light_time_ns` and
  `distance.min_round_trip_ns` directly rather than a parallel
  implementation. Emits `CONDITIONAL(BE(Q))`, never an unconditional
  security claim.
- **H8** — the program's first contact with real timing: cone certificates
  from a physically-consistent, honestly-labeled `MEASURED_MODEL` capture
  (not a computed or `SYNTHETIC_CONSISTENT` fixture) across real
  geographically-separated cloud regions, with HMAC-signed per-node
  receipts and tiered clock uncertainty (NTP/PTP/GNSS) (`docs/h8-spec.md`).
  The key finding: a co-located node is `APPARATUS_LIMITED` at every tier
  (no time-of-flight, no distance attestation, at any clock precision, by
  construction — not a defect), while an intermediate node (~475 km)
  demonstrably transitions `APPARATUS_LIMITED` → `ADMITTED` as the tier
  tightens from NTP to PTP. `scripts/live_capture.py` is the quarantined,
  non-CI on-ramp to a genuine live capture over provisioned hosts.

**Known limitation demonstrated:** gate H3-C reproduces the classical
collusion break of position verification (CGMO 2009) as `EXPECTED_ATTACK_SUCCESS` — see `docs/h3-spec.md`. Closing that gap is the design-only
quantum layer (`docs/quantum-layer-spec.md`); it is not implemented here.

## Companion program: machine-checked kernel proof (C1)

`formal/` proves five theorems about `causally_admissible` with the Z3 SMT
solver over the integers, rather than testing it on samples: faithfulness to
the real (non-integer) light-cone condition with no rounding gap, a sharp
null-cone boundary, future monotonicity, and minimality of the boundary-search
algorithm (`docs/formal-kernel-spec.md`). `z3-solver` (pip) is this
repository's only non-stdlib dependency, confined entirely to this directory
- `scripts/run_all.py` reports the proof gate as SKIPPED, not FAIL, if it
isn't installed, so the rest of the repository stays stdlib-only.

Reviewing the originally-shipped proof found one theorem (null-cone
exactness) formulated as a self-referential integer tautology that reported
"PROVEN" regardless of whether the underlying predicate was even correct -
concretely confirmed the query stayed `unsat` even against a deliberately
broken predicate. Fixed to route through genuine free variables so the proof
is actually sensitive to the kernel it's supposed to be checking, with a
regression test asserting exactly that sensitivity going forward.

**What T1 costs a floating-point implementation, in numbers:**
`benchmark/int_vs_float/` builds a faithful (not strawman) floating-point
control for the same predicate and measures the gap T1 proves away -
verdict-mismatch rate near the boundary, cross-setting reproducibility
divergence, and the honest speed line (`docs/int-vs-float-results.md`). The
claim is soundness and reproducibility, not speed: a zero-tolerance float64
gate still misjudges 1/3 of near-boundary pairs at interplanetary magnitude
once its resolution runs out, and a "reasonable" relative tolerance admits
spacelike pairs up to 78 meters off the light cone at that scale, while the
integer gate is exactly correct
(T1) and bit-identical across every setting tested; the honest speed line
shows the integer gate faster than naive float64 at every magnitude tested
in this environment, not the other way around.

## Companion program: independent red-team harness (RT1, extended by H9)

`redteam/` is a separate attacker module (own certificate, own program
name `RT1`) that tries to make gates ADMIT/PASS without authorization,
hitting each gate through only its public API — never by importing
verifier internals or reading a station's private key. Eight attack
classes (differential timing fuzz against an independently-implemented
Decimal-based reference, budgeted-gate boundary/margin fuzz,
cone-certificate and measured-certificate forgery fuzz, causal-ledger
cycle fuzz plus named scenarios, and — added for H8's capture surface —
signed-capture replay fuzz and a capture-verify boundary/trust-boundary
fuzz), 13,000+ deterministic trials, zero bypasses as of this writing.
`docs/h9-spec.md` documents H9 — the roadmap's own name for the same
harness extended to attack H8 — as one shared toolkit rather than a
second, duplicate attacker package; see `docs/redteam-spec.md` for the
full attack-class detail.

## Companion program: MnemesisOS convergence (MNX1)

`mnemesis/` is a small, separate package (own certificate, own program
name) demonstrating that `horizon.ledger.CausalLedger` **is** a
provenance-aware, multi-observer memory: writes are events, the merge
gate is the same light-cone gate (reused unmodified), and concurrent
writes are retained with provenance rather than silently overwritten.
Gate MNX-D proves the memory's ordering matches `CausalLedger` edge for
edge. A logical (vector-clock) ordering is also provided for contexts
without physical geometry. See `docs/mnemesis-convergence.md` and
`scripts/demo_mnx.py`.

## Design notes and next steps

- `docs/quantum-layer-spec.md` — the original bounded-entanglement QPV
  design note; H7 now implements the classical groundwork it described
  (the BE(Q) security-parameter tracker and the interface a real quantum
  channel would plug into), but H7 is groundwork, not the full quantum
  layer — no quantum channel is implemented, only its documented contract.
- `docs/engineering-roadmap.md` — the roadmap that scoped D1 (float
  guard), D2 (benchmark), E1 (kernel consolidation), the red-team harness
  (RT1/H9), H8 (genuine multi-node capture, delivered as a labeled
  `MEASURED_MODEL` stand-in plus a quarantined live on-ramp), and C1 (the
  machine-checked kernel proof, `formal/`) delivered above. D2's own
  finding - `CausalLedger.precedes()` scans the full edge set per visited
  node, fitting a ~quadratic scaling exponent on `scripts/bench.py`'s
  measurements - is now filed AND fixed: `horizon.reachability_cache` adds
  an additive, opt-in `precedes_fast()` (adjacency-indexed BFS, ~linear on
  the same measurements), cross-checked for agreement against the kept,
  unchanged `precedes()` reference in `tests/test_reachability_cache.py`.
  The genuine LIVE capture over real, operator-provisioned hosts that this
  note once flagged as open has since been run: see H8-LIVE below.

## H8-LIVE — genuine multi-node capture over real cloud geography

Four Azure VMs across `eastus`/`centralus`/`westus2`/`westeurope`, surveyed
from Azure's published region coordinates, captured and verified with the
unmodified `horizon.capture_verify.verify_capture` — the on-ramp H8 shipped
as its "next step" is no longer hypothetical. Two synchronization tiers
(NTP, then a tighter chrony-tracked tier) reproduced the predicted
apparatus-limited-to-admitted transition as clock uncertainty tightened,
with one honest nuance: the specific node predicted to transition first
didn't; a different node showed an analogous transition instead. See
`docs/h8-live-report.md` and `certificates/h8_live_certificate.json`.

## Companion program: causal-store (D0 — engine skeleton)

`causal-store/` is a self-contained sibling project applying the same
kernel to a different problem: a coordination-free, geo-distributed event
store where writes the light cone proves causally independent commit
without a consensus round trip, and only genuine causal dependencies
serialize. It vendors a frozen, hash-verified copy of `geometry.py` rather
than importing `horizon.geometry` — deliberately, per
`docs/distributed-system-design.md`'s "shared by value, not by coupling"
principle, so the engine stays correct even where `horizon` isn't present
(gate D0-F guards against drift between the two copies). On a modeled
5-region, 5000-write benchmark: ~85% of writes commit coordination-free, a
modeled ~6.8x latency reduction vs a total-order baseline (latency is
MODELED, not measured on real links — a recorded heuristic warning).
Reviewing the shipped skeleton found two bugs before first commit: a
`resolves()` check that compared raw elapsed time to clock uncertainty
instead of the margin to the true light-time floor (the same
"disconnected-proxy" bug class this repository's H-series and `formal/`
gates have each caught once before), and a `write()` path that never
checked whether an existing frontier entry causally dominated an incoming
write, letting a stale write resurface as a live conflict candidate. Both
are fixed, with regression tests reproducing the original counterexamples.
See `causal-store/docs/d0-spec.md`.

*Naming note: the working name during design was “Horos” (ὅρος, boundary
stone — the ancestor of “horizon”); the H-series sprint prefix keeps it.*
