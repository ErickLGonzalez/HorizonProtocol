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
    claimed position within the round-trip light budget (two-sided bound,
    asymmetric scope - see section 3)?

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
`distance.min_round_trip_ns(p_verifier, p_claimed)` as `required_ns`, but is
**two-sided**: both a lower ("too fast") and an upper ("too slow") bound are
checked, applying clock uncertainty in the claimant's favor on whichever side
benefits them (`dt_adjusted_low_ns = dt + u_ns` against the lower bound,
`dt_adjusted_high_ns = dt - u_ns` against the upper bound, where
`dt = t_response - t_challenge - proc_ns`):

```
too fast for claimed distance -> dt_adjusted_low_ns  < required_ns - resolve_ns  (REJECTED)
too slow for claimed distance -> dt_adjusted_high_ns > required_ns + resolve_ns  (REJECTED)
```

This upper bound has a precise, **asymmetric** scope, not a general deadline
- see section 3b for exactly which misrepresentation direction it closes,
which it structurally cannot, and why.

Composed protocol verification (`deepspace_protocol.verify_telemetry_packet`,
H7-D) additionally requires the packet's `(t_recv, p_dst)` to come from a
receipt **signed by a registered station** in a caller-supplied trusted
`registry` - never asserted bare by the packet itself - verified through the
same `known_station -> receipt_mac -> payload_binding -> surveyed_position`
gate sequence `horizon.certificate.verify_certificate` uses (H1), before the
timing gate above ever runs. See section 3c.

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

### 3b. The upper bound's precise, asymmetric scope

*(Erratum: an earlier version of this section argued that `trajectory_attested`
deliberately reproduces only H3's `ftl_floor` gate and not its `deadline`
gate, reasoning that a deep-space adversary "gains nothing" from claiming to
be farther than it truly is. Review found this incomplete: a two-sided bound
is both meaningful and needed, but closes only one of the two
misrepresentation directions - not both, and not the one the original text
implied. This section replaces that reasoning.)*

H3's terrestrial distance-bounding (`horizon/distance.py`) has two gates:
`ftl_floor` (response too fast - REJECTED) and `deadline` (response too slow
for an honest prover truly at the claimed position - also REJECTED, since a
farther prover cannot meet the deadline). H7's `trajectory_attested` now
reproduces both, comparing NANOSECOND quantities directly per section 3a.
The two directions of misrepresentation this closes are **not symmetric**:

- **Farther-than-claimed, claiming closer** (e.g. a prover genuinely at Mars
  claiming to be co-located with the verifier): CLOSED, soundly. The prover's
  own true round-trip minimum for its real (farther) distance already
  exceeds what the nearer claim's `required_ns` allows - it cannot speed up
  its response below that true physical floor no matter how promptly it
  answers. This exactly matches H3's `deadline` gate's original intent ("a
  farther prover cannot meet this") and is the direction the upper bound was
  added to catch. `tests/test_h7b_latency_gate.py`'s
  `test_two_sided_bound_catches_a_farther_prover_claiming_closer` demonstrates
  it.

- **Closer-than-claimed, claiming farther** (e.g. a prover genuinely
  co-located with the verifier claiming to be on Mars): NOT closed, and not
  closeable by any purely aggregate-round-trip-time check, one-sided or
  two-sided. A prover that could respond immediately is always free to
  *delay* its response until the round trip matches whatever farther
  distance it wants to claim - nothing about the timing alone distinguishes
  "genuinely at the claimed distance" from "closer, and waited." This is a
  structural limitation of round-trip-timing-only distance bounding generally
  (it appears in the classical distance-bounding literature, not just here),
  not an implementation gap this module can close. Rather than silently
  assume it solved, it is registered here explicitly and demonstrated as a
  deliberately PASSING test -
  `test_registered_limitation_claiming_farther_than_true_is_not_caught` -
  following the same H3-C discipline used for the classical
  position-verification collusion break: an honest, explicit witness beats a
  hidden assumption. Closing this direction would require binding the round
  trip to an unpredictable, per-round challenge the prover cannot precompute
  (a rapid-bit exchange, not modeled in this classical gate) or leaning on
  the quantum layer's own properties (BE(Q) / no-cloning) - out of scope
  here; see section 8, F7.

### 3c. Receipt authentication is a precondition, not the timing gate's job

*(Erratum: an earlier version of `deepspace_protocol.verify_telemetry_packet`
accepted a bare `{t0, p_src, t_recv, p_dst}` packet with no authentication:
`t_recv` and `p_dst` were whatever the caller asserted, not a value attested
by any registered station. An attacker could pick `t0 = t_recv - required_ns`
for any claimed `p_src`, wait out the claimed light-travel time, and pass -
"authentication" in name only, since nothing bound the claimed reception
event to a real observer.)*

Fixed: `t_recv` and `p_dst` (as `station_pos_nm`) now must come from a
receipt **signed by a `horizon.stations.Station`** present in a
caller-supplied, TRUSTED `registry` - exactly H1's cone-certificate model,
where the registry is trusted state the verifier already holds, never data
read out of the untrusted packet. The verifier runs the same gate sequence
`horizon.certificate.verify_certificate` uses - `known_station ->
receipt_mac -> payload_binding -> surveyed_position` - and only then hands
the now-authenticated `(t_recv, p_dst)` to `telemetry_consistent` (section 3).
A forged or unsigned receipt is REJECTED at the authentication stage and
never reaches the timing gate at all. `tests/test_h7d_protocol.py`'s
`test_unauthenticated_receipt_rejected` and `test_unknown_station_rejected`
cover this.

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
  arrival; trajectory attestation's two-sided bound REJECTS both an
  impossibly-fast response and an implausibly-slow one, each with the correct
  `reason` witness; a farther-than-claimed prover claiming closer is caught
  even responding at its own true physical minimum (section 3b); the
  registered farther-claim limitation is demonstrated, not hidden, as a
  passing test; the gate module imports only the geometry/distance kernel.
- **H7-C** BE(Q): exact-fraction adversary bound; exponential decay; meets target
  at sufficient k; CONDITIONAL(BE(Q)) label and citations present.
- **H7-D** protocol: a packet is rejected at authentication (unknown station,
  bad receipt MAC, payload/position mismatch) before any timing decision runs
  (section 3c); full pass = receipt authenticated AND timing ADMITTED AND
  qubits pass AND BE(Q) met -> CONDITIONAL_BE_Q; forged timing or bad qubits
  -> REJECTED even if the other factor is fine; verifier excludes simulator
  imports.
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
- F7: any claim that `trajectory_attested`'s two-sided bound closes the
  closer-than-claimed-claiming-farther direction (section 3b) → overclaim;
  this direction is a registered, structural limitation of round-trip-timing
  distance bounding, not solved by this or any purely aggregate-RTT check.
- F8: `deepspace_protocol.verify_telemetry_packet` reaching a non-REJECTED
  verdict on a packet whose receipt is unsigned, signed by an unregistered
  station, or bound to a different payload/position than the event claims
  (section 3c) → authentication bypass, gate defect.

## 9. Claim scope

H7 is GROUNDWORK. It certifies that the classical scaffolding (exact latency
gate + exact BE(Q) tracker) executes and satisfies its gates, and defines the
interface a future quantum layer plugs into. It is NOT a deployed system, NOT a
quantum-security proof, and NOT evidence about physics. Security is
CONDITIONAL(BE(Q)) and, for the quantum factor, conditional on assumptions
A1-A4 being met by a real channel.
