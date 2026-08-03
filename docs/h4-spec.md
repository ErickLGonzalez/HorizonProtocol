# H4 Engineering Specification — Causal-Disjointness Independence Beacons

**Program:** HorizonProtocol · **Benchmark:** H4 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Certify *causal* independence of entropy sources: combine blocks only
when their emission events are pairwise spacelike separated (both causal
directions inadmissible, decided exactly), each block hash-bound to its
emission event, and each emission event carrying an H1 cone certificate
that independently verifies PASS. FIREWALL: H4 certifies **independence
by causal structure**, never statistical randomness quality.

## 2. Unit convention

Positions int nm, times int ns, c = 299,792,458 nm/ns exactly. Every
spacelike/binding decision is exact integer arithmetic; no floats.

## 3. Trusted path vs world model

Trusted path (SOUND): `horizon/beacon.py` (`pairwise_spacelike_witnesses`
via `CausalLedger.concurrent`, binding checks, XOR combination, and the
standalone `verify_beacon`) plus the H1 kernel (`geometry`, `events`,
`ledger`, `certificate`). World model (HEURISTIC, located warnings):
`horizon/beacon_sim.py` — deterministic pseudo-entropy blocks
`SHA-256(seed || emitter_id)`, computed arrival times for cone-certificate
receipts, and the `statistical_sanity` smoke test. `verify_beacon`
imports neither simulator; test H4-B asserts this by source inspection.

## 4. Adversary model (explicit)

IN SCOPE: a forger without station keys who injects a
timelike-correlated fourth emitter, tampers with a block after binding,
submits the same emitter twice, submits fewer sources than the frozen
construction requires (hoping the trivially-empty pairwise-spacelike set
of a single source passes by vacuous truth), or embeds a cone certificate
containing an FTL-forged receipt (H1-E's forgery reused).
OUT OF SCOPE: statistical adversaries, biased-source attacks, randomness
extraction quality, station key compromise, clock attacks (L0 assumed).

## 5. Frozen parameters

Emitters (nm): `E1=(0,0,0)`, `E2=(50e12,0,0)`, `E3=(0,50e12,0)` (50 km
separations), all emitting at `T_EMIT = 1_000_000` ns — simultaneous ⇒
pairwise spacelike *by construction, but verified, never assumed*.
Block length 32 bytes. Seed `"H4-FROZEN-SEED-v1"`. Station registry: 3
stations per emitter neighborhood (9 total), frozen offsets 0.1 km from
each emitter, reusing H1's `demo_registry`.

## 6. Gates

- **H4-A (SOUND):** for every unordered pair of emission events, both
  directed `admissibility_witness` results are computed and both must be
  inadmissible (`CausalLedger.concurrent` is the authoritative
  predicate, imported from the H1 kernel). All pairwise exact witnesses
  recorded in the certificate.
- **H4-B (SOUND):** a certificate combining fewer than `MIN_SOURCES`
  (= 3, the frozen emitter count) blocks is REJECTED at gate
  `min_sources` before any other check runs — a lone source has an empty
  pairwise-spacelike set and would otherwise clear every later gate
  vacuously; each block's SHA-256 is bound into its emission event's
  payload; each emission event carries a cone certificate that
  independently verifies PASS via `horizon.certificate`; combined beacon
  value = XOR of the three blocks; `verify_beacon(beacon_cert,
  registries)` recomputes everything standalone. Bit-for-bit
  deterministic rebuild.
- **H4-C (HEURISTIC — located warning):** popcount of the 256-bit XOR
  output lies in the frozen window `[96, 160]` (frozen value: 141).
  *This is a smoke test, not a randomness certification; causal
  independence ≠ statistical quality.*
- **H4-D (SOUND) negative controls:** (1) fourth emitter at
  `E1 + (1000,0,0)` nm emitting at `T_EMIT + 10_000_000` (timelike to
  E1) → REJECTED at gate `pairwise_spacelike` with the
  admissible-direction witness; (2) one byte flipped after binding →
  REJECTED at `block_binding`; (3) same emitter twice → REJECTED at
  `distinct_sources`; (4) embedded cone certificate carrying H1-E's FTL
  forgery → REJECTED at `cone_certificate`, propagating the inner
  `light_cone` witness; (5) only one (or zero) of the three emitters'
  blocks submitted → REJECTED at `min_sources` naming the required and
  actual counts.

## 7. Acceptance criteria

`python3 scripts/run_h4.py` exits 0; all four gates PASS; certificate
carries `emitters_nm, t_emit_ns, pairwise_spacelike_witnesses[],
per_block{emitter_id, block_sha256, cone_certificate_verdict},
beacon_value_hex, statistical_sanity{tag, popcount, window}` and the
seed; zero regressions in H1/H2/H3 suites.

## 8. Registered falsifiers

- F1: any combined beacon whose pairwise witness set contains an
  admissible direction → gate defect, file erratum.
- F2: `verify_beacon` importing a simulator module → trusted-path defect.
- F3: any claim in docs or certificate that H4 certifies statistical
  randomness → firewall breach; retract.
- F4: a beacon certificate combining fewer than `MIN_SOURCES` blocks that
  is not REJECTED at `min_sources` → gate defect, file erratum.

## 9. Claim-scope firewall (verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside this sprint's stated
  model.
- **No claim that H4 certifies statistical randomness.** It certifies
  that the declared emission events are pairwise spacelike separated and
  that each block is bound to a verified emission event — nothing more.
- No claim that passing benchmarks constitutes evidence about physics.
