# H1 Engineering Specification — Cone Certificates & Causal Ledger

**Program:** HorizonProtocol · **Benchmark:** H1 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Demonstrate, stdlib-only and exactly, that light-cone constraints can serve
as a verification primitive: (i) event receipts checkable against the causal
geometry of a claimed emission; (ii) a dependency ledger that admits only
geometrically possible orderings; (iii) forgeries rejected deterministically
with exact witnesses.

## 2. Unit convention (exactness by construction)

Positions: integers, nanometers. Times: integers, nanoseconds. Then
c = 299,792,458 nm/ns is an exact integer, and the causal gate

    admissible(t1,p1,t2,p2)  :=  (t2 ≥ t1) ∧ ((c·(t2−t1))² ≥ |p2−p1|²)

is decided in exact integer arithmetic. `min_light_time_ns` (earliest
integer arrival light permits) is computed with `math.isqrt` plus exact
boundary correction — no floating point.

## 3. Trusted path vs world model

Trusted path (SOUND): `geometry.py`, `events.py`, `certificate.py`,
`ledger.py`, receipt verification in `stations.py`.
World model (HEURISTIC, located warnings): `simulate.py` (computes arrival
times), demo key derivation in `stations.py`. The verifier never imports the
simulator; test H1-C asserts this.

## 4. Adversary model (explicit)

IN SCOPE at H1: a forger who does not hold station keys and may fabricate or
tamper receipts, invent stations, lie about station positions, claim FTL
arrivals, or bind receipts to the wrong event.
OUT OF SCOPE at H1 (deliberately): station key compromise; colluding
adversaries co-located with multiple stations (defeats classical PV in
general — quantum layer's job); clock-synchronization attacks (L0 assumed);
relativistic corrections beyond flat spacetime (nm/ns lattice is Minkowski).

## 5. Gates

- **H1-A** geometry kernel: null-ray boundary exact (admissible at d = c·1ns,
  rejected at d = c·1ns + 1nm); minimality of `min_light_time_ns`.
- **H1-B** receipts: HMAC round-trip; any tamper flips verification.
- **H1-C** cone certificate: 5-station honest run PASSes; verifier is
  standalone; empty certificate REJECTED.
- **H1-D** ledger: admissible edge ADMITTED with witness; spacelike edge
  REJECTED with exact witness; concurrency symmetric; reachability
  transitive; backward edges rejected.
- **H1-E** negative controls: FTL receipt (1 ns early), forged MAC, unknown
  station, wrong-event binding, and surveyed-position lie — all REJECTED,
  each naming its violated gate, the FTL case carrying the exact integers
  (c·Δt)² < d².

## 6. Certificate schema (aggregate)

`certificate_version, benchmark_id, program, claim_class, execution_tier,
promotion_allowed, empirical_claim, adversary_model, heuristic_warnings
(located), unit_convention, gates[] (id, description, soundness_tag,
result), aggregate, source_hashes, python_version`.

## 7. Acceptance criteria

`python3 scripts/run_h1.py` exits 0; all five gates PASS; every negative
control REJECTED deterministically; certificate written and self-describing.

## 8. Falsifier directions (registered)

- F1: any admissibility decision that changes under reimplementation in
  exact rational arithmetic → geometry kernel defect, file erratum.
- F2: any forged input accepted by `verify_certificate` under the stated
  adversary model → security defect, file erratum + regression test.
- F3: ledger admits an edge whose exact witness fails the gate → defect.
- F4: demonstration that the H1 receipt scheme is treated anywhere as
  defending against collusion → documentation defect; the claim-scope
  firewall in §4 governs.
