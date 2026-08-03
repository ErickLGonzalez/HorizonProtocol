# HorizonProtocol

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
| L1 | Distance bounding / position proofs | H3 (planned) |
| L2 | Relativistic commitments | H2 (planned) |
| L3 | Cone certificates + causal ledger | **H1 (this release)** |
| L4 | Causal-disjointness independence beacons | H4 (planned) |

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
python3 scripts/run_h1.py     # runs all gates, writes certificates/h1_certificate.json
python3 -m unittest discover tests -v
```

Requires Python 3.9+. Standard library only.

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

## Roadmap

- **H2** — relativistic commitment simulator (two-agent Kent-style sustain
  rounds; binding gate = the same integer cone predicate).
- **H3** — distance bounding with an explicit collusion attack demonstrator
  (the classical break, reproduced honestly, as a negative control).
- **H4** — independence beacons: entropy XOR from stations with certified
  spacelike emission events.

*Naming note: the working name during design was “Horos” (ὅρος, boundary
stone — the ancestor of “horizon”); the H-series sprint prefix keeps it.*
