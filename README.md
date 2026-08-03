# HorizonProtocol

[![gates](https://github.com/ErickLGonzalez/HorizonProtocol/actions/workflows/gates.yml/badge.svg)](https://github.com/ErickLGonzalez/HorizonProtocol/actions/workflows/gates.yml)

**Trust rooted in causal structure.** A cryptographic stack whose certificate
authority is the speed of light.

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
python3 scripts/run_all.py              # runs every H1-H6 + MNX1 gate set + certificate validation
python3 -m unittest discover tests -v   # 141 tests
python3 scripts/validate_certificates.py
python3 scripts/demo_mnx.py             # MnemesisOS causal-memory demo, end to end
```

Requires Python 3.9+. Standard library only.

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

**Known limitation demonstrated:** gate H3-C reproduces the classical
collusion break of position verification (CGMO 2009) as `EXPECTED_ATTACK_SUCCESS` — see `docs/h3-spec.md`. Closing that gap is the design-only
quantum layer (`docs/quantum-layer-spec.md`); it is not implemented here.

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

## Design notes (writing only, no crypto implementation)

- `docs/quantum-layer-spec.md` — how a bounded-entanglement Quantum
  Position Verification layer would sit above H3 to close the collusion
  gap H3-C demonstrates.

*Naming note: the working name during design was “Horos” (ὅρος, boundary
stone — the ancestor of “horizon”); the H-series sprint prefix keeps it.*
