# H5 Engineering Specification — Real-Measurement Bridge

**Program:** HorizonProtocol · **Benchmark:** H5 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Produce cone certificates from **measured** arrival times instead of
computed ones - the point where the repo stops being a pure model. The
exact-integer light-cone gate itself is unchanged (`horizon.geometry` is
reused, never forked); only the *source of the timestamps* changes, and
the gate that classifies them is deliberately widened by a declared,
certificate-recorded uncertainty budget to avoid spuriously rejecting
honest measurements as often as it would catch forgeries.

**Core honesty principle (S3-EM discipline):** refuse the verdict when the
apparatus cannot resolve it. H5 emits `APPARATUS_LIMITED`, never a
silent `PASS`, whenever a measurement's margin against the budgeted gate
falls inside the declared resolve band.

## 2. Unit convention

Same lattice as H1-H4: positions int nm, times int ns,
`C_NM_PER_NS = 299,792,458` exactly. No floats in any classification
decision. (Node *geometry derivation* in `horizon/fixtures.py` uses floats
once, offline, to turn approximate lat/long/altitude into frozen integer
nm constants - see section 5. No float ever reaches a gate.)

## 3. Trusted path vs world model

Trusted path (SOUND): `horizon/measure.py` (`min_transit_time_ns_eff`,
`budget_witness`, `classify_measured_receipt`,
`verify_measured_certificate`) plus the H1 kernel it reuses
(`geometry.dist2`/`C_NM_PER_NS`, and `horizon.stations.Station` for
receipt signing/verification - no new signing mechanism was introduced).
World model (HEURISTIC, located warnings): `horizon/fixtures.py` (frozen
node geometry, deterministic synthetic captures) and `horizon/capture.py`
(optional live capture, quarantined - see section 3a). `measure.py` never
imports either; test H5-B asserts this by AST inspection of its actual
import statements (not a naive substring search, since the module's own
docstring names both files in prose).

### 3a. The `horizon/capture.py` quarantine

`capture.py` is a best-effort, stdlib-only (`socket` SNTP client-mode
query, `http.client` `Date`-header read) live measurement helper. It is:

- never imported by `horizon/measure.py`, `horizon/fixtures.py`, any
  `scripts/run_h*.py`, or anything under `tests/` - test H5-B walks every
  `.py` file's AST outside `capture.py` itself and asserts none of them
  import a module whose name contains `capture`;
- never run in CI or by `scripts/run_all.py`;
- read-only against public time/latency endpoints; it performs no
  side-effectful network writes and posts nothing.

It exists so a human can, manually and once, capture a candidate fixture
for review; nothing it produces is wired into any gate automatically.

## 4. Adversary model (explicit)

IN SCOPE at H5: a forger without station keys who submits a receipt that
is impossibly early even given the full uncertainty budget
(FTL-in-medium), tampers with a receipt's `recv_time_ns` after it was
signed, forges a station's own position claim, submits an unknown
station, or presents a certificate declaring `fixture_origin:
LIVE_CAPTURE` that fails its internal self-check (a receipt timestamped
before its own claimed emission by that node's raw clock reading).
OUT OF SCOPE (deliberately): station key compromise; clock/network attacks
against a *legitimately* keyed and synchronized station; any claim that
`c_eff = 3/5 c` is a validated physical bound for a specific real deployed
network (it is a declared, conservative, frozen assumption); any claim
that a `SYNTHETIC_CONSISTENT` fixture is a real measurement; security
against colluding multi-site adversaries (H3-C's scope, unchanged here).

## 5. Frozen parameters

Three surveyed nodes, real-world-plausible coordinates, derived once via
a flat-earth (equirectangular) projection from approximate public
lat/long/altitude values, frame origin at `NODE-USE1`:

| node | approx. location | lat | lon | alt (m) | pos_nm (E, N, U) |
|---|---|---|---|---|---|
| `NODE-USE1` | N. Virginia | 38.9072 | -77.0369 | 30 | `(0, 0, 0)` |
| `NODE-USW2` | Oregon | 45.5946 | -121.1787 | 50 | `(-3819497896113808, 743604952442822, 20000000000)` |
| `NODE-EUW1` | Ireland | 53.3498 | -6.2603 | 20 | `(6124151593140482, 1605943847556704, -10000000000)` |

Pairwise separations: USE1-USW2 ≈ 3,891 km; USE1-EUW1 ≈ 6,331 km;
USW2-EUW1 ≈ 9,981 km - within the declared tens-to-thousands-of-km range.
`llh_to_enu_nm` (the conversion function) is float-based and is called
exactly once, offline, to derive the table above; it is never called
again - the frozen integers are what every gate operates on.

Declared per-node clock uncertainty: `NODE-USE1` is PTP-grade
(`U_ns = 50,000`, 50 µs); `NODE-USW2` and `NODE-EUW1` are NTP-grade
(`U_ns = 5,000,000`, 5 ms) - both conservative bounds, declared and
recorded per node, never assumed globally.

Effective in-medium speed bound: `c_eff = C_NM_PER_NS * 3/5` (a
conservative fiber lower bound; exact rational `[3, 5]`, never a float).
`RESOLVE_MARGIN_NS = 20,000` (20 µs) - chosen well below both declared
`U_ns` values so an honest, comfortably-measured receipt (offset near
zero relative to the `c_eff` floor) still clears the margin cleanly, per
gate H5-A.

Claimed emission event: `t0 = 0`, `p0 = NODE-USE1`'s position. Seed for
any synthetic augmentation: `"H5-FROZEN-SEED-v1"`.

## 6. The budgeted gate

For a claimed emission `(t0, p0)` and a measured receipt `(t_recv,
station_pos)` with declared `U_ns`:

- `raw_dt_ns = t_recv - t0`; `dt_adjusted_ns = raw_dt_ns + U_ns` (the full
  declared clock uncertainty, applied once, always in the prover's
  favor).
- `required_dt_eff_ns = min_transit_time_ns_eff(p0, station_pos)`: the
  exact-integer ceiling of `dist(p0, station_pos) / c_eff`, computed with
  the same `math.isqrt` + boundary-correction technique as
  `geometry.min_light_time_ns` (never a float).
- `margin_ns = dt_adjusted_ns - required_dt_eff_ns`.
- `margin_ns > RESOLVE_MARGIN_NS` → **ADMITTED**.
- `margin_ns < -RESOLVE_MARGIN_NS` → **REJECTED** (impossibly early even
  at the slow in-medium bound, with the full clock-uncertainty benefit of
  the doubt).
- otherwise → **APPARATUS_LIMITED** (cannot resolve given the declared
  uncertainty; never silently PASS).

`consistent` (the boolean form of the same inequality,
`((t_recv - t0 + U_ns) * C_NM_PER_NS * 3)^2 >= 5^2 * dist2(p0,
station_pos)`) is recorded alongside `margin_ns` and is exactly consistent
with it by construction - both reduce to the same integer inequality, so
there is no float-vs-integer boundary drift between the two
representations recorded in the witness.

> This is deliberately a *looser, existence/consistency* gate ("consistent
> with a real signal path"), not H1's tight vacuum-c bound. H1's gate
> remains the idealized reference; H5 does not replace or weaken it -
> `horizon/geometry.py` is untouched.

`PATH_EXCESS_PPM` (real paths are longer than straight-line and slower
than `c_eff` would suggest) is declared only as a documentary
`path_excess_note` in the certificate; this reference implementation does
not fold it numerically into the gate, since doing so would only ever be
justified as a further *loosening* (recording that a legitimately longer
real path took even more time than the `c_eff` floor requires), never a
tightening, and no such correction is needed for the frozen fixtures here.

## 7. The committed fixtures

`data/h5_fixture_capture.json` (honest) and `data/h5_fixture_marginal.json`
(one node engineered into the resolve margin) are generated once by
`scripts/generate_h5_fixtures.py` from `horizon/fixtures.py`'s frozen
seed and geometry, then committed. All H5 gates **replay** these files
(load and re-verify) rather than regenerating them at test or CI time, so
outcomes are deterministic regardless of when or where the suite runs.
Both fixtures are labelled `"origin": "SYNTHETIC_CONSISTENT"` - neither is
a real capture. Should a human ever run `horizon/capture.py` and hand-adapt
its output into a new fixture, that fixture must be labelled
`"origin": "LIVE_CAPTURE"` with the capture's ISO timestamp, and is
subject to the additional live-capture self-check in section 8.

## 8. Gates

- **H5-A (SOUND):** budget-gate boundary correctness - a receipt exactly
  at the `c_eff` limit with zero raw offset is ADMITTED (since `U_ns`
  alone, chosen `> RESOLVE_MARGIN_NS`, clears the margin); one impossibly
  early beyond `U_ns + RESOLVE_MARGIN_NS` is REJECTED with the exact
  integer witness; one exactly inside `RESOLVE_MARGIN_NS` (margin = 0) is
  APPARATUS_LIMITED; the margin boundary at exactly `±RESOLVE_MARGIN_NS`
  is exercised on both sides.
- **H5-B (SOUND):** replay PASS - over the committed `h5_fixture_capture`,
  every node's receipt is independently re-verified ADMITTED; aggregate
  PASS; bit-for-bit deterministic regeneration from the frozen seed;
  `verify_measured_certificate` never imports a world-model module
  (checked by AST, not substring search); `horizon.capture` is never
  imported anywhere outside itself (checked across `horizon/`, `scripts/`,
  `tests/`).
- **H5-C (SOUND):** apparatus-limited control - over the committed
  `h5_fixture_marginal`, exactly one node lands with `margin_ns == 0`
  (inside the resolve band) while the others remain individually
  ADMITTED; the runner's aggregate verdict for that event is
  APPARATUS_LIMITED, never PASS, naming the marginal node.
- **H5-D (SOUND) negative controls:** (1) a receipt claiming instantaneous
  arrival (impossibly early even accounting for the full budget) →
  REJECTED at gate `budget` with an inconsistent, negative-margin exact
  witness; (2) a `recv_time_ns` tampered after signing → REJECTED at
  `receipt_mac`; (3) a station's own body forged with a false
  `station_pos_nm` (still validly MAC'd, since the false claim originates
  from the station itself) → REJECTED at `surveyed_position`; (4) an
  unknown `station_id` → REJECTED at `known_station`; (5) a certificate
  declaring `fixture_origin: LIVE_CAPTURE` with one receipt's raw elapsed
  time negative (even though that receipt individually clears the
  ordinary budget gate) → APPARATUS_LIMITED at
  `live_capture_self_check`, never silently PASS.

## 9. Acceptance criteria

`python3 scripts/run_h5.py` exits 0; all four gates PASS; certificate
written with `frame_origin_llh, nodes[]{id,pos_nm,u_ns}, c_eff_rational,
resolve_margin_ns, path_excess_note, fixtures[]{name,origin,sha256},
per_event{verdict,per_node_verdicts,budget_witnesses},
apparatus_limited_events[]` and the seed recorded; zero regressions in
the 82 existing H1-H4 tests.

## 10. Registered falsifiers

- F1: any measured receipt classified ADMITTED whose budget witness fails
  on independent integer recomputation → gate defect, file erratum.
- F2: any event with `|margin_ns| <= RESOLVE_MARGIN_NS` reported as PASS
  instead of APPARATUS_LIMITED → gate defect, file erratum.
- F3: `horizon.capture` imported anywhere in `tests/`, `scripts/`, or any
  other `horizon/*.py` module → trusted-path defect.
- F4: a `SYNTHETIC_CONSISTENT` fixture presented anywhere (docs,
  certificate, commit message) as evidence of a real measurement →
  firewall breach; retract.
- F5: nondeterminism in gate outcomes across reruns on the committed
  fixtures → defect.

## 11. Claim-scope firewall (verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside this sprint's stated
  model.
- No claim that `c_eff = 3/5 c` is a validated bound for any specific
  real network; it is a declared, conservative, frozen assumption.
- **No claim that a `SYNTHETIC_CONSISTENT` fixture is a real measurement.**
  It is a deterministic stand-in, always labelled as such.
- No claim that passing benchmarks constitutes evidence about physics.

## 12. Prohibited claims (repository-wide, verbatim)

- No claim that any H-series artifact is a deployed or deployable
  cryptosystem.
- No claim of security against adversaries outside each layer's stated
  model.
- No claim that H3's classical layer resists collusion (H3-C proves the
  opposite on purpose).
- No claim that H4 certifies statistical randomness.
- No claim that H5's synthetic-consistent fixtures are real measurements.
- No claim that any passing benchmark is evidence about physics.
