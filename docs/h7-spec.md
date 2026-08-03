# H7 Engineering Specification — Bounded-Entanglement QPV for Deep-Space Telemetry

**Program:** HorizonProtocol · **Benchmark:** H7 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE · **Security verdict class:** CONDITIONAL(BE(Q))

## 1. Objective and honest reframing

Extend HorizonProtocol toward deep-space use with a single **latency-budget
gate** that unifies two tasks and a **bounded-entanglement (BE(Q))** security
tracker that supplies the collusion resistance classical distance-bounding
cannot (H3-C demonstrated the classical break).

The pivotal reframe: over interplanetary distances a challenge-response round is
bounded by light-travel time (Earth-Mars: 3-22 min one way, 6-45 min round
trip). Quantum position verification therefore **cannot** locate a probe in real
time -- and that is the theory being correct, not failing. Instead:

  * **Authenticated telemetry:** is a received packet's arrival pattern
    consistent with a vacuum light path from the claimed emitter worldline? A
    packet arriving sooner than light permits from its claimed origin is forged.
  * **Trajectory attestation:** does a prover's response schedule prove its
    claimed position within the round-trip light budget (lower bound only -
    see section 3)?

Both are the same exact-integer inequality, and both **reuse the existing H1/H3
kernel functions directly** (`geometry.min_light_time_ns`,
`distance.min_round_trip_ns`) rather than reimplementing the ceiling-search
arithmetic a second time. **The latency is the security budget:** the same
light delay that forbids real-time location also forbids any adversary from
forging faster than light.

## 2. Vacuum tightens the gate

Terrestrially the fiber loophole forces an in-medium speed factor c_eff < 1
(H5/H6 used 3/5). In vacuum c_eff = 1 exactly, so the deep-space gate is the
*tightest* form of the exact light-cone predicate, not the loosest. This is a
physics gift specific to the space setting.

## 3. The unified gate (SOUND)

Positions in nm, times in ns, c exact (H1 kernel), c_eff = 1.

For a claimed emission `(t0, p_src)` and reception `(t_recv, p_dst)`, with
declared clock uncertainty `u_ns` (applied in the claimant's favor) and a
resolve band `resolve_ns` (nanoseconds, linear - see section 3a):

```
dt_adjusted_ns = (t_recv - t0) + u_ns
required_ns    = min_light_time_ns(p_src, p_dst)      # reused, unmodified
ADMITTED           if dt_adjusted_ns >= required_ns
APPARATUS_LIMITED  if required_ns - resolve_ns <= dt_adjusted_ns < required_ns
REJECTED           if dt_adjusted_ns < required_ns - resolve_ns
```

Trajectory attestation is the same shape over the round trip, reusing
`distance.min_round_trip_ns(p_verifier, p_claimed)` as `required_ns` and
`dt_adjusted_ns = (t_response - t_challenge - proc_ns) + u_ns`. **Only the
lower ("too fast") bound is checked** - see section 3b for why an upper
deadline, present in H3's terrestrial distance-bounding, is deliberately not
reproduced here.

### 3a. Erratum: squared margins cannot represent a linear time budget

An earlier version of `latency_gate.py` computed a SQUARED margin
(`(c*dt_adjusted)^2 - dist^2`, units nm²) and compared it against a parameter
named `resolve_ns2`, implying nanoseconds-squared. This does not work: the
squared margin scales **quadratically** with distance, while a clock
uncertainty of `U` nanoseconds only ever shifts that margin by approximately
`2 * C^2 * required_ns * U` near the boundary - proportional to
`required_ns * U`, not `U^2` in isolation. A `resolve_ns2` value actually
derived from a small, realistic time uncertainty (e.g. literally squaring a
nanosecond figure) was therefore astronomically smaller than the
interplanetary-scale margin and had **no practical effect**: no test in the
original suite exercised a realistic APPARATUS_LIMITED case, only a
degenerate one with `resolve_ns2` set to the entire margin's magnitude.

Fixed: every classification in `latency_gate.py` now compares NANOSECOND
quantities directly - `dt_adjusted_ns` against the exact integer
`required_ns` floor - never a squared quantity. This exactly mirrors
`horizon.measure`'s dual-floor design (see `docs/h5-spec.md`, section 6),
which has the same property for the same reason. `tests/test_h7b_latency_gate.py`
adds a regression test with a realistic 50 µs `resolve_ns` (comparable to
H5/H6's declared `U_ns`) confirming APPARATUS_LIMITED actually triggers, and a
companion test confirming that same small resolve band does not mask a gross
forgery.

### 3b. Why trajectory attestation has no upper (deadline) bound

H3's terrestrial distance-bounding (`horizon/distance.py`) has two gates:
`ftl_floor` (response too fast - REJECTED) and `deadline` (response too slow
for an honest prover truly at the claimed position - also REJECTED, since a
farther prover cannot meet the deadline). H7's `trajectory_attested`
deliberately reproduces only the first. At interplanetary scale, legitimate
processing/queueing/scheduling variance routinely exceeds any short constant
`proc_ns` by orders of magnitude, so "arrived later than the theoretical
minimum" is not itself evidence of anything - unlike H3's tightly-bounded
terrestrial scenario, where `proc_ns` is a genuine, small, near-constant
processing delay and exceeding the deadline is meaningful evidence of
distance. The relevant deep-space threat is an adversary claiming to be
*closer* than it is (impersonating a nearby, faster-responding source) -
exactly what the lower bound catches; an adversary claiming to be *farther*
than it is gains nothing from spoofing a deep-space telemetry link, so that
direction is out of scope by design, not by oversight.

## 4. Bounded-entanglement tracker (SOUND)

Classical PV is broken by zero-entanglement collusion (CGMO 2009). QPV restores
soundness for adversaries pre-sharing < Q_secure EPR pairs; unconditional QPV is
impossible (exponential-entanglement attacks exist; a linear lower bound is
known). `beq.py` computes, in exact rational arithmetic, the adversary's
acceptance bound p^k for k committed qubits at per-round gap p, and reports
whether it meets a declared soundness target, emitting CONDITIONAL(BE(Q)) with Q
named. Example: k=73, p=3/4 gives bound < 1e-9, Q_secure = 73.

`adversary_bound_float`/`target_soundness_float` in the emitted verdict are
float renderings of the exact `Fraction` values, for certificate readability
only - the soundness decision (`meets_target = bound <= target`) is computed
in exact rational arithmetic before those fields are ever created (see
`tests/test_float_guard.py`'s documented line-level exception for these two
fields).

## 5. Quantum layer: interface + quarantined stand-in

`quantum_interface.py` is a DOCUMENTED CONTRACT (assumptions A1-A4: sub-luminal
channel, no-cloning, bounded-entanglement soundness, loss tolerance), not an
implementation. `qubit_sim.py` is a DETERMINISTIC, HEURISTIC stand-in modeling
idealized BB84/SWAP outcomes to exercise plumbing; it is NOT a quantum device,
NOT a security proof, and is quarantined from the verifier path (H7-D asserts the
protocol does not import it). Located warnings appear in every certificate. A
real deployment (Deep Space Quantum Link-class terminal) supplies a concrete
channel meeting the contract.

## 6. Gates

- **H7-A** geometry: exact Earth-Mars light times (closest ~3.04, farthest
  ~22.3 min one way); c_eff = (1,1); light time is exact integer lower bound;
  `one_way_light_time_ns` agrees exactly with `geometry.min_light_time_ns`
  (delegates to it rather than a parallel implementation).
- **H7-B** unified gate: honest telemetry/attestation ADMITTED; impossibly-fast
  arrivals REJECTED with negative margin; a realistic (50 µs) resolve band
  correctly produces APPARATUS_LIMITED at a boundary receipt, and does not
  mask a gross forgery; clock uncertainty (`u_ns`) can rescue a near-boundary
  arrival; the gate module imports only the geometry/distance kernel.
- **H7-C** BE(Q): exact-fraction adversary bound; exponential decay; meets target
  at sufficient k; CONDITIONAL(BE(Q)) label and citations present.
- **H7-D** protocol: full pass = timing ADMITTED AND qubits pass AND BE(Q) met ->
  CONDITIONAL_BE_Q; forged timing or bad qubits -> REJECTED even if the other
  factor is fine; verifier excludes simulator imports.
- **H7-E** negatives: Earth spoofing a Mars packet REJECTED; arrival-before-
  emission REJECTED; stand-in explicitly labeled.

## 7. Certificate extras

`security_verdict_class, application, registered_assumptions (A1-A4),
earth_mars_light_times, demo_beq_verdict (Q_secure), heuristic_warnings
(qubit sim, quantum interface, float-rendering fields)`.

## 8. Registered falsifiers

- F1: any packet accepted whose timing witness fails independent integer recompute.
- F2: any CONDITIONAL_BE_Q verdict where the exact adversary bound exceeds the
  declared target.
- F3: `qubit_sim` or `_sim` imported anywhere in the verifier path.
- F4: the simulator or interface presented as an implemented quantum device or a
  security proof.
- F5: any claim of real-time deep-space position (physically impossible; the
  gate authenticates worldlines, it does not locate in real time).
- F6: any classification decision in `latency_gate.py` comparing a squared
  (nm²-scale) quantity against a nanosecond-scale threshold, or otherwise
  reintroducing the section 3a erratum → gate defect, file erratum.

## 9. Claim scope

H7 is GROUNDWORK. It certifies that the classical scaffolding (exact latency
gate + exact BE(Q) tracker) executes and satisfies its gates, and defines the
interface a future quantum layer plugs into. It is NOT a deployed system, NOT a
quantum-security proof, and NOT evidence about physics. Security is
CONDITIONAL(BE(Q)) and, for the quantum factor, conditional on assumptions
A1-A4 being met by a real channel.
