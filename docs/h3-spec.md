# H3 Engineering Specification — Distance Bounding + Honest Collusion Break

**Program:** HorizonProtocol · **Benchmark:** H3 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Implement Brands–Chaum-style distance bounding and 4-verifier
multilateral position verification on the exact nm/ns lattice — and
reproduce the known classical collusion attack
(Chandran–Goyal–Moriarty–Ostrovsky 2009) as a first-class result, so the
repository permanently documents the limitation instead of hiding it.

## 2. Unit convention

Positions int nm, times int ns, c = 299,792,458 nm/ns exactly. All
admissibility decisions are exact integer comparisons; no floats.

## 3. Trusted path vs world model

Trusted path (SOUND): `horizon/distance.py` (RTT gates, deadlines,
multilateration) plus the H1 kernel it imports. World model (HEURISTIC,
located warning): `horizon/db_sim.py` — computes RTTs for honest,
distant, decoy, and colluding roles; every simulated response respects
the physical floor of its true path (agents may delay, never accelerate
past *c*). The trusted module never imports the simulator; the H3-B suite
asserts this.

## 4. Adversary model (explicit)

IN SCOPE: provers not at the claimed position who cannot signal faster
than light — a distant prover, a decoy-positioned prover that delays
responses, a zero-processing-delay FTL claimer, and (for H3-C, on
purpose) a colluding pre-positioned pair sharing session material in
advance.
OUT OF SCOPE: verifier compromise; clock-synchronization attacks (L0
assumed); any *defense* against collusion — H3-C exists precisely to show
the classical layer has none.

## 5. Frozen parameters

Verifiers (nm): `V1=(0,0,0)`, `V2=(20e12,0,0)`, `V3=(0,20e12,0)`,
`V4=(0,0,20e12)` (20 km rig). `P_CLAIM = (6e12, 6e12, 0)`.
`PROC_NS = 25` (declared, part of the protocol). Seed
`"H3-FROZEN-SEED-v1"`.

## 6. Core gates (exact)

For RTT = t_r − t_c against claimed position P:

- **ftl_floor:** `(C·(RTT−PROC))² ≥ 4·dist2(V,P)` — the round trip cannot
  beat light (RTT − PROC ≥ 2d/c); violated → REJECTED with the exact
  integers `(c·Δt)² < 4d²`.
- **deadline:** `RTT ≤ 2·min_light_time_ns(V,P) + PROC` — the response is
  as fast as a prover AT P could answer; violated → REJECTED with exact
  integers.

Multilateration ADMITS a claim iff every verifier admits it, else
REJECTED naming the failing verifiers. `min_round_trip_ns` (smallest
integer T with `(C·T)² ≥ 4d²`) is computed with `math.isqrt` plus exact
boundary correction and satisfies `min_round_trip_ns ≤ 2·min_light_time_ns`.

## 7. Gates

- **H3-A (SOUND):** honest prover at `P_CLAIM` ADMITTED at each of V1–V4;
  a prover truly ~5 km farther from every verifier
  (`DISTANT_POS = (7e12, 7e12, −4.8e12)` nm) cannot meet any deadline →
  REJECTED at all four with the exact violated inequality.
- **H3-B (SOUND):** honest multilateration ADMITTED; a decoy prover at
  `(6e12, 0, 0)` — closer to V1 (delays to V1's deadline, satisfying its
  bound) but strictly farther from V3 — REJECTED naming V3 with the
  integers.
- **H3-C (SOUND — the honest break):** colluder pair `A1=(1e12,1e12,0)`
  (covers V1) and `A2=(10e12,10e12,5e12)` (covers V2,V3,V4), each
  strictly closer to its covered verifiers than `P_CLAIM` is, sharing
  session material in advance, each answering its side's challenges
  within every deadline (delaying to mimic a prover at `P_CLAIM`). The
  attack **succeeds**: every verifier's bound is satisfied although no
  prover is at `P_CLAIM`. Gate verdict: `EXPECTED_ATTACK_SUCCESS`,
  recorded with `classical_pv_break_demonstrated: true`. **A run where
  the attack fails is a test FAILURE** — it would mean the simulation is
  dishonest about the known impossibility.
- **H3-D (SOUND):** a "prover" claiming `PROC_NS = 0` with RTT strictly
  below light's round trip (and hence strictly below
  `2·min_light_time_ns(V, P_CLAIM)`) → REJECTED with the FTL witness —
  the same physics as H1-E's forged receipt, in RTT form.

## 8. Acceptance criteria

`python3 scripts/run_h3.py` exits 0; H3-A/B/D PASS; H3-C records
`EXPECTED_ATTACK_SUCCESS` (counts as PASS — it is the expected result);
certificate carries `verifiers_nm, p_claim_nm, proc_ns,
per_verifier_bounds[], collusion_demo{...}, claim_scope`; zero
regressions in H1/H2 suites.

## 9. Registered falsifiers

- F1: any parameterization where H3-C's colluders fail while respecting
  the causal gates → the break was mis-modeled; defect.
- F2: any acceptance in H3-B/H3-D whose per-verifier exact witness fails
  on independent recomputation → defect.
- F3: verifier-side code importing the world-model module → defect.

## 10. Claim-scope firewall (verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside this sprint's stated
  model.
- **No claim that H3's classical layer resists collusion — H3-C proves
  the opposite on purpose.** Classical position verification is
  assurance-grade only; mitigation belongs to a quantum layer
  (bounded-entanglement QPV) out of scope for this repository.
- No claim that passing benchmarks constitutes evidence about physics.
