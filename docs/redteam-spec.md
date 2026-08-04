# RT1 Engineering Specification — Independent Red-Team Harness

**Program:** HorizonProtocol Red-Team Harness · **Benchmark:** RT1 ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Every negative-control test elsewhere in this repository rejects an input
the test itself constructed - a cooperative forgery. H3-C is the only
genuine adversary demonstrated so far, and it is one the repository invited
on purpose. RT1 is different: it is an **independent attacker** module that
tries to make gates ADMIT/PASS without authorization, hitting each gate
through **only its public API**, never by importing verifier internals or
reading private state (station keys, etc.) to "cheat" its way to a pass.

Zero successful bypasses is the pass condition for every attack class. A
residual attack surface, where a tier genuinely cannot resolve an attack
(this has not occurred so far, but is registered as a possible honest
outcome), would be reported as an explicit, quantified count - never
silently treated as zero.

## 2. Trust boundary

`redteam/attacks.py` imports only the same public functions any external
caller would use: `horizon.geometry.causally_admissible`,
`horizon.certificate.verify_certificate`,
`horizon.measure.verify_measured_certificate`,
`horizon.ledger.CausalLedger`, `horizon.capture_verify.classify` /
`verify_capture`, `horizon.signed_capture.sign_receipt` / `verify_receipt`,
and the world-model builders needed to produce an honest baseline to mutate
(`horizon.simulate.broadcast`, `horizon.geo_fixtures.build_synthetic_consistent_capture`,
`horizon.stations.demo_registry`). It never reads a `Station`'s private
key or an H8 node's derived key (`test_attacks_module_never_reaches_into_private_station_state`
asserts this by source inspection) - every forgery is constructed by
mutating the on-the-wire JSON representation (receipt bodies, hex-encoded
MACs) or passing adversarial parameters through each function's own public
signature, exactly as an external attacker without station keys would have
to.

## 3. Attack classes

- **RT-A, differential timing fuzz:** cross-checks
  `horizon.geometry.causally_admissible` against a DELIBERATELY DIFFERENT
  algorithm - `decimal.Decimal`-based real-number square-root comparison
  (60 significant digits, far exceeding what interplanetary nm/ns
  distances need) - over thousands of random points concentrated near
  each sampled pair's exact light-cone boundary, at scales from terrestrial
  to interplanetary. Any disagreement between the exact-integer kernel and
  the independent reference is a bypass.
- **RT-B, budgeted-gate boundary/margin fuzz:** searches near
  `horizon.measure`'s two floors (vacuum, `c_eff`) for any point where the
  three-way ADMITTED/APPARATUS_LIMITED/REJECTED classification disagrees
  with the documented partition, and separately checks that nudging a
  receive time later never moves a verdict "backwards"
  (ADMITTED -> APPARATUS_LIMITED -> REJECTED is not a legal transition as
  time increases).
- **RT-C, cone-certificate forgery fuzz:** mutates an honest H1 cone
  certificate (tampered receive time, tampered station position, swapped
  station id, a flipped MAC bit, a forged payload hash) and asserts
  `verify_certificate` never returns PASS on a genuine mutation.
- **RT-C', measured-certificate forgery fuzz:** the same idea against
  H5/H6's `verify_measured_certificate`, with a dedicated sweep attempting
  to smuggle a forged `node_params` block (declaring an enormous
  uncertainty or superluminal `c_eff`) into the certificate alongside an
  otherwise-impossible receipt - the class of bug found and fixed once
  already during H5/H6 review, now fuzzed rather than only fixed-case
  tested.
- **RT-D, causal-ledger cycle fuzz:** attempts to force a 2-cycle
  (`a->b` and `b->a` both ADMITTED) or a 3-cycle
  (`a->b->c->a` all ADMITTED) into `CausalLedger`. Neither should ever be
  possible - an admitted edge requires strictly-later time by
  construction, making a directed cycle in admitted edges impossible - and
  this fuzzes that invariant rather than only asserting it holds by
  inspection.
- **RT-E, H8 signed-capture replay fuzz:** signs one legitimate H8 receipt
  and repeatedly tries to reuse it for a different event, node, position,
  time, or tier while keeping the original MAC - the on-the-wire replay an
  attacker without a node key would have to attempt. Every mutation must
  fail `horizon.signed_capture.verify_receipt`.
- **RT-F, H8 capture-verify boundary/trust-boundary fuzz:** attacks
  `horizon.capture_verify` two ways at once - trying to force ADMITTED on a
  genuinely-impossible (more than `u_ns` below the absolute vacuum floor)
  arrival by (1) passing an adversarial `c_eff` directly to `classify`, and
  (2) declaring an adversarial `c_eff` INSIDE an otherwise-untrusted
  `capture` blob handed to `verify_capture`, which must ignore it. This is
  the exact class of bug found and fixed once already during H8 review (see
  `horizon/capture_verify.py`'s module docstring erratum) - fuzzed here
  rather than only fixed-case tested, the same discipline RT-C' already
  applies to `horizon.measure`'s equivalent trust boundary.
- **RT-G, named ledger-integrity scenarios:** a handful of fixed,
  human-readable `CausalLedger` attempts (a plain backward-time edge, a
  2-cycle via a second backward edge, a spacelike edge) complementing RT-D's
  randomized fuzz with scenarios a reviewer can check by inspection.

## 4. Determinism

Every attack class draws from a single `random.Random` seeded by the
frozen constant `redteam.SEED`, so a full red-team run (13,000+ trials
across all classes as of this writing) is bit-reproducible;
`test_deterministic_across_reruns` asserts this for one attack class as a
representative check.

## 5. Registered falsifiers

- F1: any attack class reporting a nonzero `bypasses` list → genuine
  security finding; freeze further sprint work until fixed (per the
  program roadmap's own decision rule: "a known bypass outranks new
  features").
- F2: `redteam/attacks.py` importing any verifier-internal helper not
  exposed as public API, or reading a station's private key → harness
  integrity defect (it would no longer be attacking honestly).
- F3: nondeterminism in `attack_reports` across reruns with the same seed.
- F4: a residual (nonzero-bypass) attack surface silently reported as
  zero, or omitted from the emitted certificate.

## 6. Certificate extras

`attack_reports[]{attack,trials,bypass_count,bypasses}`, `total_trials`,
`total_bypasses`, and the seed.

## 7. Claim scope

RT1 certifies that, under the attack classes and trial counts declared
here, the public gates were not observed to admit an unauthorized input.
It is NOT a formal security proof, NOT exhaustive (only the declared
attack classes and RNG seed are covered - a different seed or a
qualitatively different attack class could in principle find something
this run did not), and NOT evidence that no bypass exists. It raises
confidence; it does not eliminate the need for the formally verified
kernel program (see the engineering roadmap's Phase C) for a stronger
claim about the one load-bearing predicate.

## 8. Prohibited claims (repository-wide, verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside each layer's stated
  model.
- No claim that H3's classical layer resists collusion (H3-C proves the
  opposite on purpose).
- No claim that H4 certifies statistical randomness.
- No claim that H5's, H6's, or H7's synthetic-consistent fixtures/stand-ins
  are real measurements or a real quantum device.
- No claim that any passing benchmark is evidence about physics.
- No claim that RT1's zero-bypass result is a proof of security; see
  section 7.
