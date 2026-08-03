# H5 Engineering Specification — Real-Measurement Bridge

**Program:** HorizonProtocol · **Benchmark:** H5 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

Produce cone certificates from **measured** arrival times instead of
computed ones - the point where the repo stops being a pure model. The
exact-integer light-cone gate itself is unchanged (`horizon.geometry` is
reused, never forked, and its `min_light_time_ns` is the ONLY floor that
can ever justify a `REJECTED` verdict here); only the *source of the
timestamps* changes, and receipts are classified against a second,
conservative floor to avoid spuriously rejecting honest measurements as
often as it would catch forgeries.

**Core honesty principle (S3-EM discipline):** refuse the verdict when the
apparatus cannot resolve it. H5 emits `APPARATUS_LIMITED`, never a
silent `PASS`, whenever a measurement lands between the absolute
vacuum-c floor and a conservative real-medium floor - physically
possible, but faster than declared "ordinary" performance can vouch for.

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
is impossibly early even given the full uncertainty budget (a vacuum-c
violation), attempts to smuggle a forged uncertainty or speed-bound
through the certificate itself (`node_params` is TRUSTED CALLER INPUT,
never read from `cert` - see section 6a), tampers with a receipt's
`recv_time_ns` after it was signed, forges a station's own position
claim, submits an unknown station, or presents a certificate declaring
`fixture_origin: LIVE_CAPTURE` that fails its internal self-check (a
receipt timestamped before its own claimed emission by that node's raw
clock reading).
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
(`U_ns = 5,000,000`, 5 ms) - both conservative bounds, declared in
`horizon.fixtures.NODE_U_NS` and passed to the verifier as TRUSTED CALLER
INPUT (see section 6a), never assumed globally and never read from a
certificate.

Effective in-medium speed bound: `c_eff = C_NM_PER_NS * 3/5` (a
conservative fiber lower bound on how fast real signals travel; exact
rational `[3, 5]`, never a float).

Claimed emission event: `t0 = 0`, `p0 = NODE-USE1`'s position. Seed for
any synthetic augmentation: `"H5-FROZEN-SEED-v1"`.

## 6. The budgeted gate: two floors, not one margin

For a claimed emission `(t0, p0)` and a measured receipt `(t_recv,
station_pos)` with declared `U_ns`:

- `raw_dt_ns = t_recv - t0`; `dt_adjusted_ns = raw_dt_ns + U_ns` (the full
  declared clock uncertainty, applied once, always in the prover's
  favor).
- `vacuum_floor_ns = min_light_time_ns(p0, station_pos)` - reused from
  `horizon.geometry`, unmodified. **Nothing, in any medium, travels
  faster than this.** `dt_adjusted_ns < vacuum_floor_ns` → **REJECTED**:
  physically impossible even with the full clock-uncertainty benefit of
  the doubt.
- `typical_floor_ns = min_transit_time_ns_eff(p0, station_pos)` - the
  exact-integer ceiling of `dist(p0, station_pos) / c_eff`, computed with
  the same `math.isqrt` + boundary-correction technique as
  `geometry.min_light_time_ns` (never a float). Always `>= vacuum_floor_ns`
  since `c_eff <= vacuum c`. `dt_adjusted_ns >= typical_floor_ns` →
  **ADMITTED**: consistent with ordinary, conservative real-medium
  performance.
- Otherwise (`vacuum_floor_ns <= dt_adjusted_ns < typical_floor_ns`) →
  **APPARATUS_LIMITED**: physically possible, but faster than the
  declared conservative bound accounts for - this module cannot vouch for
  it as ordinary performance, and does not try to.

There is no separate arbitrary "resolve margin" constant. The gap between
a vacuum floor and a slower, conservative real-medium floor already IS
the band this module cannot resolve, by construction - introducing an
extra margin on top would either be redundant or would (as an earlier,
corrected version of this module did - see the erratum below) re-open the
exact bug this design fixes.

> This is deliberately a *looser* ADMIT criterion than H1's tight vacuum-c
> bound (an honest, ordinary-speed real receipt now clears cleanly instead
> of needing to hit the vacuum floor exactly), while the REJECT criterion
> remains exactly as strict as H1's: only a genuine vacuum-c violation
> ever produces REJECTED. H1's gate remains the idealized reference; H5
> does not replace or weaken it - `horizon/geometry.py` is untouched.

### 6a. Erratum: `c_eff` is a floor for ADMIT, never for REJECT

An earlier version of this module used `c_eff` (declared as a *lower*
bound on real-medium speed) as if it were the fastest anything could
travel, rejecting any receipt earlier than `dist(p0, station_pos) /
c_eff`. Because real signals can legitimately travel faster than that
conservative lower bound (anywhere up to vacuum c), that inverted the
roles of the two speed bounds: an honest receipt arriving faster than the
*conservative* estimate - but still slower than light - was misclassified
as impossibly early. Fixed as described above: vacuum c
(`min_light_time_ns`, unconditionally the fastest anything can travel) is
the only floor that can ever justify REJECTED; `c_eff` only ever raises
the bar for a clean ADMITTED. `certificates/h5_certificate.json`,
`data/h5_fixture_*.json`, and every H5 test were regenerated/rewritten
against the corrected model; the H1-H4 gates and certificates were
unaffected (H5's math never touched H1's kernel).

### 6b. Trust boundary: `node_params` is caller-supplied, never certificate-supplied

`verify_measured_certificate(cert, registry, node_params)` takes
per-station uncertainty (and, if overridden, `c_eff`) as a **third
TRUSTED argument**, exactly as `registry` (station positions/keys) is
trusted caller input rather than something read from `cert`. An earlier
version read `u_ns`/`c_eff_num`/`c_eff_den` from an untrusted
`cert["node_params"]` field whose values the receipt MAC does not cover -
a forger could declare an enormous uncertainty or a superluminal `c_eff`
and turn an otherwise impossibly-early, validly-signed receipt into
ADMITTED. Fixed: the certificate schema no longer has a `node_params` (or
`resolve_margin_ns`) field at all; every caller (`scripts/run_h5.py`,
every H5 test) obtains the trusted values from
`horizon.fixtures.trusted_node_params()`, sourced from the frozen
`NODE_U_NS` declared in section 5.

`PATH_EXCESS_PPM` (real paths are longer than straight-line and slower
than `c_eff` would suggest) is declared only as a documentary
`path_excess_note` in the certificate; this reference implementation does
not fold it numerically into the gate, since doing so would only ever be
justified as a further *loosening* of the ADMIT floor (recording that a
legitimately longer real path took even more time than the `c_eff` floor
requires), never a tightening, and no such correction is needed for the
frozen fixtures here.

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

- **H5-A (SOUND):** dual-floor boundary correctness - a receipt exactly at
  the `typical_floor_ns` (`c_eff`) limit with zero clock-uncertainty
  benefit is ADMITTED; one 1 ns below the `vacuum_floor_ns` is REJECTED;
  exactly at the vacuum floor is NOT rejected; a receipt at the midpoint
  between the two floors is APPARATUS_LIMITED; declared clock uncertainty
  can move a receipt out of REJECTED (by construction, since it is always
  applied in the prover's favor); `c_eff`'s floor is confirmed strictly
  larger than the vacuum floor for any nonzero separation.
- **H5-B (SOUND):** replay PASS - over the committed `h5_fixture_capture`,
  every node's receipt is independently re-verified ADMITTED using
  TRUSTED caller-supplied `node_params` (never read from the
  certificate - the certificate is asserted to carry no `node_params` or
  `resolve_margin_ns` field at all); aggregate PASS; bit-for-bit
  deterministic regeneration from the frozen seed;
  `verify_measured_certificate` never imports a world-model module
  (checked by AST, not substring search); `horizon.capture` is never
  imported anywhere outside itself (checked across `horizon/`, `scripts/`,
  `tests/`).
- **H5-C (SOUND):** apparatus-limited control - over the committed
  `h5_fixture_marginal`, exactly one node lands strictly between
  `vacuum_floor_ns` and `typical_floor_ns` while the others remain
  individually ADMITTED; the runner's aggregate verdict for that event is
  APPARATUS_LIMITED, never PASS, naming the marginal node.
- **H5-D (SOUND) negative controls:** (1) a receipt claiming instantaneous
  arrival (below the vacuum floor even accounting for the full budget) →
  REJECTED at gate `budget`; (2) a `recv_time_ns` tampered after signing →
  REJECTED at `receipt_mac`; (3) a station's own body forged with a false
  `station_pos_nm` (still validly MAC'd, since the false claim originates
  from the station itself) → REJECTED at `surveyed_position`; (4) a
  certificate carrying a forged `node_params` block declaring an enormous
  uncertainty is REJECTED anyway, because the verifier uses only the
  TRUSTED caller-supplied `node_params` and never the certificate's;
  (5) an unknown `station_id` → REJECTED at `known_station`; (6) a
  certificate declaring `fixture_origin: LIVE_CAPTURE` with one receipt's
  raw elapsed time negative (even though that receipt individually clears
  the ordinary budget gate) → APPARATUS_LIMITED at
  `live_capture_self_check`, never silently PASS.

## 9. Acceptance criteria

`python3 scripts/run_h5.py` exits 0; all four gates PASS; certificate
written with `frame_origin_llh, nodes[]{id,pos_nm,u_ns}, c_eff_rational,
path_excess_note, fixtures[]{name,origin,sha256},
per_event{verdict,per_node_verdicts,budget_witnesses},
apparatus_limited_events[]` and the seed recorded; zero regressions in
the 82 existing H1-H4 tests. Note the certificate itself carries no
`node_params`/`resolve_margin_ns` field - those are supplied to the
verifier as trusted arguments, never read from certificate content.

## 10. Registered falsifiers

- F1: any measured receipt classified ADMITTED whose budget witness fails
  on independent integer recomputation → gate defect, file erratum.
- F2: any event with `vacuum_floor_ns <= dt_adjusted_ns < typical_floor_ns`
  reported as PASS instead of APPARATUS_LIMITED → gate defect, file
  erratum.
- F2b: any event with `dt_adjusted_ns < vacuum_floor_ns` reported as
  anything other than REJECTED → gate defect, file erratum (this is the
  absolute physical floor; there is no discretion here).
- F3: `horizon.capture` imported anywhere in `tests/`, `scripts/`, or any
  other `horizon/*.py` module → trusted-path defect.
- F4: a `SYNTHETIC_CONSISTENT` fixture presented anywhere (docs,
  certificate, commit message) as evidence of a real measurement →
  firewall breach; retract.
- F5: nondeterminism in gate outcomes across reruns on the committed
  fixtures → defect.
- F6: a certificate-embedded `node_params`, `u_ns`, or `c_eff` value of
  any kind affecting `verify_measured_certificate`'s verdict → trust
  boundary defect (see section 6b); the verifier must use ONLY its
  caller-supplied `node_params` argument.

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
