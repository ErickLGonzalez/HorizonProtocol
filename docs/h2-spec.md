# H2 Engineering Specification — Relativistic Commitment Simulator

**Program:** HorizonProtocol · **Benchmark:** H2 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Model a Kent/Lunghi-style two-agent sustained bit commitment and certify,
stdlib-only and exactly, the two things this repository *can* certify:
(a) algebraic consistency of the commit–sustain–reveal chain over
GF(2⁶¹−1); (b) the geometric precondition that the two agent sites are
causally isolated within each response window, with exact light-cone
witnesses. H2 explicitly does **not** claim a security proof of binding.

## 2. Unit convention

Same lattice as H1: positions int nm, times int ns, c = 299,792,458 nm/ns
exactly. Chain arithmetic mod the Mersenne prime `P_FIELD = 2**61 - 1`.
No floats anywhere in an admissibility, chain, or window decision.

## 3. Trusted path vs world model

Trusted path (SOUND): `horizon/commitment.py` (algebra, reveal
verification, isolation gate, window gate, transcript hash chain) plus the
H1 kernel it imports. World model (HEURISTIC, located warning):
`horizon/commit_sim.py` — computes round timings, derives all
secrets/challenges as `SHA-256(seed || label || counter)` from the frozen
seed `"H2-FROZEN-SEED-v1"`, and drives honest/cheating roles. The trusted
module never imports the simulator; test H2-C asserts this.

## 4. Adversary model (explicit)

IN SCOPE at H2: a cheating committer who answered rounds honestly (it
cannot rewrite already-sent responses) and at reveal attempts to open the
flipped bit with a back-solved `a_0` (role `CHEAT_FLIP`); post-hoc
transcript tampering; mis-configured apparatus (sites too close for the
response window).
OUT OF SCOPE (deliberately): arbitrary adversaries; any claim that the
chain algebra is binding in general (indeed, an adversary who back-solves
the *entire* secret vector satisfies the algebra for either bit — binding
in the literature rests on the two-agent isolation structure, which H2
certifies only as a geometric precondition); network/clock attacks (L0
assumed); station key compromise.

## 5. Frozen parameters

`P_FIELD = 2**61 - 1`; `SITE_1 = (0,0,0)`,
`SITE_2 = (30_000_000_000_000, 0, 0)` nm (30 km);
`DT_RESP_NS = 50_000`; `K_SUSTAIN = 8`; `DT_ROUND_NS = 90_000`;
seed `"H2-FROZEN-SEED-v1"`. One-way light time is computed with
`min_light_time_ns`, never hardcoded.

## 6. Chain algebra

Commit (round 0, site 1): verifier issues `r_0`; committer replies
`y_0 = (a_0 + b·r_0) mod P`. Sustain round `k = 1…K` (alternating sites):
`y_k = (a_k + a_{k−1}·r_k) mod P`. Reveal: disclose `b` and all `a_k`; the
verifier recomputes every equation; any mismatch → `REJECTED` with the
first failing round index and both integer sides as witness.

## 7. Gates

- **H2-A (SOUND):** round-trip verifies for `b=0` and `b=1`; flipped-bit
  reveal REJECTED; single altered `a_k` REJECTED naming round `k`.
- **H2-B (SOUND):** exact two-sided isolation:
  `DT_RESP_NS < min_light_time_ns(SITE_1, SITE_2)` — equivalently
  `NOT causally_admissible(t, SITE_1, t + DT_RESP_NS, SITE_2)` — with the
  full `admissibility_witness` recorded; converse control
  `DT_BAD = min_light_time + 1` **is** admissible and yields
  `APPARATUS_LIMITED`.
- **H2-C (SOUND):** K sustained rounds on schedule, every response inside
  its window, sites alternating, chain ADMITTED at reveal, transcript hash
  chain ADMITTED, `binding_duration_ns = t_reveal − t_commit` recorded,
  bit-for-bit deterministic rerun.
- **H2-D (SOUND) negative controls:** (1) `CHEAT_FLIP` REJECTED with
  `failing_round = 1`; (2) sites 1 m apart with the same window →
  `APPARATUS_LIMITED`, scenario aggregate REJECTED (refuse to certify,
  never silently pass); (3) one tampered `y_k` → hash-chain REJECTED
  naming the round.

## 8. Acceptance criteria

`python3 scripts/run_h2.py` exits 0; all four gates PASS; certificate
written with `field_prime, sites_nm, dt_resp_ns, k_sustain,
one_way_light_time_ns, binding_duration_ns, isolation_witnesses[]` and
seed recorded; zero regressions in the H1 suite.

## 9. Registered falsifiers

- F1: any run where a response window ≥ one-way light time yields a PASS
  on the binding/isolation gate → gate defect, file erratum.
- F2: any reveal inconsistency not localized to a round index → defect.
- F3: nondeterminism across reruns (differing certificate content with the
  same seed) → defect.

## 10. Claim-scope firewall (verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside this sprint's stated
  model. The security *argument* for schemes of this family (Kent 2012;
  Lunghi et al. 2015 experimental line) is cited as context only: H2
  certifies the algebra and the geometric precondition; it does not prove
  binding against arbitrary adversaries.
- No claim that passing benchmarks constitutes evidence about physics.
