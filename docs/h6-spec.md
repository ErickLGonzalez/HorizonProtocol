# H6 Engineering Specification — Multi-Node Cone Certificates over Real Geography

**Program:** HorizonProtocol · **Benchmark:** H6 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Extend H5's measured-cone-certificate gate from an abstract three-site rig
to **authentic geography**: real cloud-region coordinates, converted to
the exact nanometer lattice, with arrival times carrying the same
declared clock-uncertainty budget H5 already certifies. This is the point
at which the repository computes cone certificates over the actual
distances between real places - Virginia to Oregon (≈3,474 km), Ireland
(≈5,195 km), Singapore (≈11,976 km) - rather than an abstract frozen
triangle.

**H6 introduces no new gate math.** It reuses `horizon.measure`'s
dual-floor budgeted classifier and `horizon.stations`'s HMAC-authenticated
receipts exactly as H5 does, over a different (real-geography, four-node)
registry. The only genuinely new code is the geography -> lattice
quantization boundary (`horizon.geo_frame`) and the registry/fixture
wiring that feeds real positions into the unchanged H5 gate.

## 2. Why H6 reuses H5's gate instead of a new one

An earlier draft of this sprint shipped its own parallel budgeted-gate
module with two defects also found and fixed once already in H5 (see
`docs/h5-spec.md`, sections 6a/6b):

1. it used `c_eff` (a declared *lower* bound on real-medium speed) as if
   it were the fastest anything could travel, rejecting any receipt
   earlier than `dist/c_eff` - inverting the roles of the vacuum-c floor
   (the only correct REJECT threshold) and the conservative `c_eff` floor
   (which should only ever raise the bar for ADMIT);
2. it accepted bare `{node_id, t_recv_ns}` records with **no
   cryptographic authentication at all** - a regression relative to every
   other H-series sprint's signed-receipt discipline, since anyone could
   fabricate an arrival record for any node without needing that node's
   key.

Rather than reproduce a known bug class and a known rigor regression in a
second module, H6 is integrated as: real geography (`geo_frame`,
`geo_registry`) feeding the SAME `horizon.measure.verify_measured_certificate`
and `horizon.stations` machinery H5 already uses, reviewed, and
certificate-carries. There is exactly one budgeted-gate implementation in
the repository.

## 3. Geography -> exact lattice (the quantization boundary)

Real locations are given as WGS84 (lat, lon, alt) in `data/h6_nodes.json`.
`horizon/geo_frame.py` performs the ellipsoid -> ECEF -> local ENU
transform ONCE, in floating point, then **quantizes** every coordinate to
an integer nanometer lattice (`horizon/geo_registry.py` wraps each
quantized position as an ordinary HMAC-keyed `horizon.stations.Station`).
Everything after quantization is exact integer arithmetic on the
unmodified H1/H5 kernel. The quantization is the explicit boundary
between HEURISTIC geodesy and the SOUND causal gate, and it is recorded
(`geo_frame.quantization_nm`). Straight-line ECEF chord distance is used,
not great-circle path length: light goes through the earth, not around
it.

Reference frame origin: `aws-us-east-1` (N. Virginia). Node straight-line
distances from the origin (computed exactly on the quantized lattice):
`us-west-2` ≈ 3,474 km, `eu-west-1` ≈ 5,195 km, `ap-southeast-1` ≈
11,976 km, with vacuum light times ≈ 11.59 ms, 17.33 ms, 39.95 ms
respectively. All four declared nodes are NTP-grade (`U_ns = 5,000,000`).

## 4. The budgeted gate (unchanged from H5)

For a claimed emission `(t0, p0)` and a measured receipt `(t_recv,
node_pos)` with declared `U_ns`, `horizon.measure.budget_witness`
classifies against two exact-integer floors:

- `vacuum_floor_ns = min_light_time_ns(p0, node_pos)` - the absolute
  vacuum-c floor, reused unmodified from `horizon.geometry`. A receipt
  earlier than this, even with the full clock-uncertainty benefit of the
  doubt, is **REJECTED**: physically impossible, full stop.
- `typical_floor_ns = min_transit_time_ns_eff(p0, node_pos)` - the floor
  implied by the conservative in-medium speed bound `c_eff = 3/5 c`. At or
  above this floor is **ADMITTED**: consistent with ordinary real-medium
  performance.
- Between the two floors is **APPARATUS_LIMITED**: physically possible,
  but faster than the conservative bound accounts for; the gate refuses
  to vouch for it either way.

See `docs/h5-spec.md`, section 6, for the full derivation and the
erratum explaining why `c_eff` must only ever raise the ADMIT bar, never
supply a REJECT threshold.

## 5. Trust boundary (unchanged from H5)

`verify_measured_certificate(cert, registry, node_params)` takes the
per-node registry (positions/keys) and per-node clock uncertainty as
TRUSTED CALLER arguments - never read from `cert`. H6's certificates
carry no `node_params` field; `horizon.geo_registry.trusted_node_params`
is the trusted source, exactly mirroring
`horizon.fixtures.trusted_node_params` for H5.

## 6. Determinism and the fixtures

CI has no reliable external network and must be deterministic, so H6's
gates run against a **committed replay fixture**
(`data/h6_fixture_capture.json`, `fixture_origin: SYNTHETIC_CONSISTENT`)
generated once by `scripts/generate_h6_fixtures.py` from
`horizon/geo_fixtures.py`'s frozen seed and the real geometry. A second
fixture (`data/h6_fixture_marginal.json`) places one node (`us-west-2`) at
the midpoint between the vacuum and `c_eff` floors to exercise
APPARATUS_LIMITED. The honesty label on each fixture must survive
(falsifier F4): a synthetic-consistent fixture is a physically-consistent
stand-in, never a real measurement.

## 7. Live capture (quarantined)

`horizon/h6_capture.py` optionally queries public NTP servers (as a
real-world stand-in per declared node - it has no way to query the nodes
themselves) and writes a candidate marked `LIVE_CAPTURE`, reusing
`horizon.capture.query_ntp_offset_ns` (H5's already-reviewed SNTP query)
rather than re-implementing NTP parsing. It is HEURISTIC,
non-deterministic, unauthenticated, excluded from CI, and imported by no
verifier or test (test H6-B asserts the verifier imports neither
`geo_fixtures`, `h6_capture`, nor `capture`). It reads only public timing,
uses no credentials, and writes nothing but a local candidate file.

## 8. Gates

- **H6-A (HEURISTIC output SOUND):** frame correctness - the origin node
  maps to within 100 nm of `(0,0,0)`; every node position is an integer;
  the Virginia-Singapore chord is plausible (10,000-13,000 km);
  `load_geo_registry` is deterministic across reloads; the frame's
  quantization is recorded.
- **H6-B (SOUND):** replay PASS - over the committed
  `h6_fixture_capture`, every real-geography node is independently
  re-verified ADMITTED using TRUSTED caller-supplied `node_params`;
  aggregate PASS; bit-for-bit deterministic regeneration from the frozen
  seed; the certificate carries no `node_params` field; the verifier
  never imports a world-model module (checked by AST inspection).
- **H6-C (SOUND):** apparatus-limited control - over the committed
  `h6_fixture_marginal`, exactly one node (`us-west-2`) lands strictly
  between the vacuum and `c_eff` floors while the others remain
  individually ADMITTED; the aggregate verdict is APPARATUS_LIMITED,
  never PASS.
- **H6-D (SOUND) negative controls:** (1) the farthest node
  (`ap-southeast-1`, ≈40 ms vacuum floor) receiving an arrival 1 µs after
  emission → REJECTED at gate `budget`, below the vacuum floor; (2) a
  `recv_time_ns` tampered after signing → REJECTED at `receipt_mac`; (3) a
  node's own body forged with a false `station_pos_nm` (still validly
  MAC'd) → REJECTED at `surveyed_position`; (4) a certificate carrying a
  forged `node_params` block declaring an enormous uncertainty is
  REJECTED anyway, because the verifier uses only the TRUSTED
  caller-supplied `node_params`; (5) an unknown node id → REJECTED at
  `known_station`.

## 9. Certificate extras

`geo_frame` (origin name/LLH/quantization), `nodes{pos_nm,u_ns,llh}`,
`c_eff_rational`, `fixtures[]{name,origin,sha256}`,
`per_event{verdict,per_node_verdicts,budget_witnesses}`,
`apparatus_limited_events[]`, and the seed - the same schema family as H5.

## 10. Adversary model

IN SCOPE: a forger of arrival times without node keys who attempts a
vacuum-c violation, a post-signing tamper, a node position lie, a forged
`node_params` block, or an unknown node id.
OUT OF SCOPE: colluding multi-node adversaries (the classical PV
impossibility, demonstrated on purpose in H3-C); node key compromise;
sub-quantization positional lies below the nm lattice; curvature or
relativistic frame effects beyond the local-ENU Minkowski approximation.

## 11. Registered falsifiers

- F1: any ADMITTED verdict whose budget witness fails independent integer
  recomputation → gate defect, file erratum.
- F2: any event with `vacuum_floor_ns <= dt_adjusted_ns < typical_floor_ns`
  reported PASS instead of APPARATUS_LIMITED → gate defect, file erratum.
- F3: `horizon.h6_capture` or `horizon.capture` imported anywhere in
  `tests/`, `scripts/`, or any other `horizon/*.py` module (other than
  `h6_capture.py` importing `capture.py` itself) → trusted-path defect.
- F4: a `SYNTHETIC_CONSISTENT` fixture presented anywhere as evidence of a
  real measurement → firewall breach; retract.
- F5: nondeterminism in gate outcomes across reruns on the committed
  fixtures → defect.
- F6: a certificate-embedded `node_params` value of any kind affecting
  `verify_measured_certificate`'s verdict → trust boundary defect.

## 12. Claim scope

A passing H6 certificate means: the declared model, over real geographic
coordinates quantized to the exact lattice, executed and satisfied its
declared gates under a declared, TRUSTED clock budget using the same
gate H5 certifies. It is NOT a deployed positioning system, NOT a
security proof, and NOT evidence about physics. The `SYNTHETIC_CONSISTENT`
fixtures are a stand-in; a genuine multi-node capture (future work) would
replace them with authenticated live measurements and its own controls.

## 13. Prohibited claims (repository-wide, verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside each layer's stated
  model.
- No claim that H3's classical layer resists collusion (H3-C proves the
  opposite on purpose).
- No claim that H4 certifies statistical randomness.
- No claim that H5's or H6's synthetic-consistent fixtures are real
  measurements.
- No claim that any passing benchmark is evidence about physics.
