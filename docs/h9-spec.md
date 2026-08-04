# H9 Engineering Specification — Independent Red-Team Harness (H8 surface)

**Program:** HorizonProtocol · **Benchmark:** H9 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none · **Empirical claim:** NONE

## 1. Objective

The engineering roadmap names an independent red-team harness "Sprint H9."
RT1 (`docs/redteam-spec.md`) already delivers exactly that adversary - an
independent attacker hitting only public gates, scoring bypasses, quantifying
residual attack surface - across H1-H6's surface. H9 is that same harness
extended to attack the surface H8 introduced (`horizon.signed_capture`,
`horizon.capture_verify`), which did not exist when RT1 was built.

## 2. One harness, not two

Rather than standing up a second, parallel `redteam/` package duplicating
RT1's timing-fuzz and ledger-cycle attacks against the same underlying
kernel, H9's genuinely new attacks (H9-B, H9-C) were added directly to the
shared `redteam/attacks.py` RT1 already uses, as RT-E and RT-F (plus RT-G, a
small complementary deterministic ledger check) - see docs/redteam-spec.md,
section 3. H9's own gates below (H9-A through H9-E) exercise that same
shared module; H9-A and H9-D deliberately REUSE RT1's existing, more
rigorous timing-fuzz (RT-A, multiple magnitude scales, `Decimal`-based
independent oracle) and ledger-cycle fuzz (RT-D) rather than standing up
weaker duplicates. This keeps exactly one attacker toolkit in the
repository, matching the "one kernel, reused everywhere" discipline this
program applies to trusted code - extended here to attacker code, where a
second, subtly-different copy of the same fuzz is drift risk with no
compensating benefit.

## 3. Attack classes

- **H9-A** (reuses RT-A): differential timing fuzz against
  `horizon.geometry.causally_admissible`.
- **H9-B** (RT-E): H8 signed-capture replay fuzz - a valid signed receipt
  reused for a different event, node, position, time, or tier; all rejected
  by `horizon.signed_capture.verify_receipt`.
- **H9-C** (RT-F): H8 capture-verify boundary and trust-boundary fuzz - the
  classes of bug found and fixed during H8 review (see
  `horizon/capture_verify.py`'s module docstring erratums 1 and 2), fuzzed
  here rather than only fixed-case tested. Requirement: no genuinely-impossible
  arrival is ever admitted, whether the adversary attacks `classify`'s own
  `c_eff` parameter, smuggles an adversarial `c_eff` inside an
  otherwise-untrusted `capture` blob, or re-pairs a legitimately-signed
  receipt with a self-chosen emission claim the original signature never
  covered (must be caught at `event_binding`).
- **H9-D** (reuses RT-D, plus RT-G): causal-ledger cycle fuzz and named
  backward/spacelike-edge scenarios.
- **H9-E**: hygiene - the H8-surface attacks exist, use only public
  `horizon.signed_capture`/`horizon.capture_verify` functions (never a
  node's derived key), and the timing-fuzz oracle they reuse is an
  independent re-derivation, not a call to the gate itself.

## 4. Result (this release)

All classes: no bypass. See `certificates/h9_certificate.json` for the exact
per-class trial counts and `certificates/redteam_certificate.json` for RT1's
combined run (which includes RT-E/RT-F/RT-G alongside RT-A through RT-D,
since they share one module).

## 5. Registered falsifiers

- F1: any attack admitted that the stated adversary model excludes.
- F2: `redteam/attacks.py` importing verifier internals to "cheat" a pass
  (must attack through public gates only; H9-E enforces).
- F3: a residual reported as zero where fuzzing finds nonzero.
- F4: a second, parallel red-team package reintroducing a duplicate
  timing-fuzz or ledger-cycle attack against the same kernel RT1/H9 already
  cover - the section 2 consolidation this spec documents.

## 6. Claim scope

Certifies that an independent adversary, attacking only public gates
(including H8's signed-capture and capture-verify surface), achieved no
security bypass. It is NOT a proof of security against all adversaries; it
is evidence from adversarial testing, and it explicitly leaves colluding
multi-node attacks (the classical PV limit) to the quantum layer. See
`docs/redteam-spec.md`, section 7, for the claim-scope language this
certificate shares with RT1.
