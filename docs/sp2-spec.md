# SP-2 Engineering Specification — Trajectory Uncertainty → APPARATUS_LIMITED

**Program:** HorizonProtocol · **Sprint:** SP-2 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE · **Builds on:** SP-0 (`Worldline`, #11, merged)
and SP-1 (occultation + light-delay, #12, merged).

## 0. Positioning record (repo history)

*(Per SP-0 §0 convention.)*

- **Theory framing is prior art.** "No shared now; ordering resolves only
  when the gap exceeds clock uncertainty" is formalized in Light Cone
  Consistency (Landers & Kramer 2026, Theorem 60: timestamp order refines
  causality iff `2ε ≤ dmin`) and the causal-consistency literature
  generally. SP-2 does not claim that framing as novel. Its
  `APPARATUS_LIMITED` verdict is the *physical-position* analogue of LCC's
  clock-uncertainty bound: LCC bounds ordering by *clock* error `ε`; SP-2
  bounds it by *trajectory-position* uncertainty derived from light-delay +
  maneuver limits.
- **Applied space-domain gap is (as far as published work shows) open.**
  NASA Starling/DSA and FAME solve multi-asset consistency with
  purpose-built protocols; CCSDS solves timing by master-clock correlation
  with an advertised uncertainty. No published spacecraft system was found
  applying a physical light-cone causal gate with a calibrated
  cannot-resolve verdict. SP-2's contribution is the physical + applied
  instantiation, interoperable-in-spirit with the CCSDS uncertainty model.
- **This repo's own precedent.** `horizon.measure.classify_measured_receipt`
  / `horizon.capture_verify` (H5/H8) already implement a two-floor,
  three-verdict pattern for MEASURED-TIME uncertainty: `REJECTED` only
  below the absolute vacuum-`c` floor, `APPARATUS_LIMITED` between that
  floor and a more conservative one, `ADMITTED` only once the conservative
  floor clears too. SP-2 is the same pattern applied to POSITION
  uncertainty instead of clock uncertainty — see `horizon/two_floor.py`'s
  module docstring for the direct mapping.
- **Honest limit:** "not found" ≠ "does not exist" (CCSDS working groups,
  defense programs, unpublished industry work are unsearched). The claim
  is "no published precedent found," not "first."

## 1. What was built (additive, on top of SP-0/SP-1)

### 1.1 Position uncertainty envelope (`horizon/uncertainty.py`)
`TrajectoryEnvelope(nominal, t_c, v_unc_nm_per_ns, a_max_nm_per_ns2,
u_measured_nm=0)` models a ship's knowable position as an exact-integer
ball: `center_at(t)` is the best-estimate `nominal` `Worldline` evaluated
at `t`; `radius_at(t)` is the kinematic growth bound

```
u(t) = v_unc * (t - t_c) + ceil(a_max * (t - t_c)**2 / 2)
```

computed with `_ceil_div`, exact integer ceiling division — the `/2` never
becomes a float, and rounding UP means the envelope is never smaller than
the true kinematic bound (only ever equal, or larger by at most 1 nm).
Growing the envelope only ever pushes a verdict toward
`APPARATUS_LIMITED`, never toward a false `ADMITTED`/`REJECTED` (see
`horizon/two_floor.py`), so this rounding choice costs nothing on the
sound side.

`collapse(t_new, nominal_after, u_measured_nm, ...)` returns a NEW envelope
(no mutable state) anchored at a fresh contact: the accumulated growth is
discarded, replaced by `u_measured_nm` — the cone-of-possibility
collapsing back down when a new signal arrives.

### 1.2 Two-floor three-verdict gate (`horizon/two_floor.py`)
`two_floor_verdict(t1, p1, t2, envelope)` classifies `(t1, p1) -> (t2,
<somewhere in envelope>)` against the frozen `causally_admissible`
(imported, never redefined), evaluated only at the envelope's two extremal
distances from `p1`:

- **ADMITTED** — the WORST case (farthest point, distance `d + r`) still
  satisfies admissibility: true for every position the envelope allows.
- **REJECTED** — the BEST case (closest point, distance `max(0, d - r)`)
  still fails: physically impossible for every position the envelope
  allows. `t2 < t1` is the degenerate instance (every position fails
  regardless of distance, matching the kernel's own `dt < 0` short-circuit).
- **APPARATUS_LIMITED** — neither: the envelope straddles the light cone.

Both extremal distances involve `d = sqrt(dist2(p1, center))`, irrational
in general, but the comparison against `L = C_NM_PER_NS * dt` is done by
moving `r` to `L`'s side FIRST (making both sides non-negative) and only
THEN squaring — no `sqrt` is ever computed:

```
ADMITTED   iff  L >= r   and  (L - r)**2 >= D
REJECTED   iff  D > r*r  and  (L + r)**2 < D      (or dt < 0, unconditionally)
else            APPARATUS_LIMITED
```

`tests/test_sp2_uncertainty.py` cross-checks this closed form against
direct `causally_admissible` calls at the literal extremal points (using a
colinear axis fixture so those points are exact integers, not merely
trusted algebra).

## 2. Tests (`tests/test_sp2_uncertainty.py`)

- **SP2-A:** `radius_at` matches a hand-computed reference exactly at
  every tested `t`, is `0` at `t_c`, is strictly monotone increasing,
  raises on a query before `t_c`, and the ceiling rounding is verified to
  round UP (never truncate) on an odd `a_max*dt²`. Runtime float inputs at
  every public boundary raise `TypeError` (F1), the same discipline as
  SP-0/SP-1's `_require_int` guards.
- **SP2-B:** `collapse` discards the old envelope's accumulated growth —
  the fresh envelope's radius at the collapse instant is the measured
  residual, not the old envelope's grown radius — and growth resumes
  correctly from the new contact time.
- **SP2-C:** three concrete cases (envelope fully outside even in vacuum →
  `REJECTED`; straddling → `APPARATUS_LIMITED`; fully inside → `ADMITTED`)
  on a colinear fixture, each cross-checked against `causally_admissible`
  called directly at the exact far/near extremal points — not just the
  closed-form comparison.
- **SP2-D (the two-floor discipline):** at `t2 = 999`, the nominal CENTER
  point alone already fails `causally_admissible`, but the envelope's near
  edge (best case) still passes — a naive point-estimate gate would
  wrongly `REJECT` here; the honest verdict is `APPARATUS_LIMITED` (F2). A
  second case confirms `REJECTED` only fires once even the near edge
  itself fails.
- **SP2-E:** tighter rate bounds (`v_unc`/`a_max`) AND a fresher contact
  (via `collapse`) both narrow the envelope and resolve `t2` values that
  were `APPARATUS_LIMITED` under looser/staler parameters into a definite
  `ADMITTED` or `REJECTED` — the physical analogue of LCC's `2ε ≤ dmin`.

## 3. Deliverables

1. `horizon/uncertainty.py` — `TrajectoryEnvelope` (exact-integer
   growing/collapsing envelope).
2. `horizon/two_floor.py` — `two_floor_verdict` (three-verdict gate
   composing the frozen kernel at envelope extrema).
3. `tests/test_sp2_uncertainty.py` — SP2-A..E.
4. `docs/sp2-spec.md` — this document.
5. `tests/test_float_guard.py` — both new modules added to
   `TRUSTED_MODULES`.
6. `horizon/geometry.py`, `horizon/worldline.py`, `horizon/occultation.py`,
   `horizon/light_delay.py` — UNCHANGED (`git diff --stat` shows zero
   changes to any of them).

## 4. Registered falsifiers

- **F1:** any float in the envelope or two-floor path → exactness defect.
  Checked by `tests/test_float_guard.py` (both modules in
  `TRUSTED_MODULES`) and SP2-A's runtime `TypeError` tests (the same
  runtime-boundary discipline the SP-0/SP-1 reviews established: a
  caller-supplied float at a public boundary must be rejected, not
  silently widened).
- **F2:** `REJECTED` returned when some in-envelope trajectory would be
  vacuum-admissible → two-floor violation. Checked by SP2-D directly.
- **F3:** `ADMITTED` returned when some in-envelope position fails the
  cone → false-admit. Checked by SP2-C's worst-case cross-check against
  `causally_admissible`.
- **F4:** envelope not collapsing to measured uncertainty on new contact →
  model defect. Checked by SP2-B.
- **F5:** claiming `APPARATUS_LIMITED` is a novel concept rather than the
  physical instantiation of a known uncertainty-bounded-ordering result →
  scope/honesty violation. Addressed in section 0 above (cites LCC
  Theorem 60 and this repo's own H5/H8 two-floor precedent).
- **F6:** frozen kernel or prior SP modules modified → scope violation.
  Checked by `git diff --stat` on `horizon/geometry.py`,
  `horizon/worldline.py`, `horizon/occultation.py`, `horizon/light_delay.py`
  showing zero changes.

## 5. What SP-2 does NOT do (deferred to SP-3)

Proper-time divergence: SP-2 still assumes a single time coordinate
(light-delay-corrected) shared enough to compute `t - t_c`. SP-3 removes
that — ship and ground clocks physically diverge (relativistic proper
time), so even the time axis is per-node, and ordering must come from
substrate lineage, not a shared clock.

## 6. Reproduction

```bash
python3 -m unittest tests.test_sp2_uncertainty -v
python3 -m unittest discover -s tests   # full suite
git diff --stat horizon/geometry.py horizon/worldline.py horizon/occultation.py horizon/light_delay.py   # all empty
```
