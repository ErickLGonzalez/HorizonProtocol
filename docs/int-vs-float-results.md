# Exact-Integer vs Floating-Point Light-Cone Gate — Results

**Program:** HorizonProtocol · **Companion to:** C1 (`formal/kernel_proof.py`,
`docs/formal-kernel-spec.md`) · **Tier:** BENCHMARK, informational · **Claim
class:** ENGINEERING_REFERENCE · **Empirical claim:** NONE — nothing here is
a gate or a certificate. Harness: `benchmark/int_vs_float/`.

## 0. The claim (read before the numbers)

The exact-integer light-cone gate (`horizon.geometry.causally_admissible`) is
**not** a speed optimization over a floating-point implementation of the same
predicate. The actual claim, already **proven** (not sampled) by Z3 theorem
T1 in `formal/kernel_proof.py`, is that the integer gate is *exactly
equivalent to the real light-cone condition with zero rounding gap*, while
any float gate carries a tolerance that is an attack surface, a source of
cross-machine non-determinism, and capable of flipping a security verdict
near the cone. This document demonstrates that gap with numbers. It does
**not** pitch the integer gate as faster — see Test 3, reported exactly as
measured either way.

## 1. Method

Three independently-runnable pieces, none of which modify the frozen,
machine-checked kernel:

- `boundary_gen.py` — for a chosen magnitude and integer `dt` (ns) snapped to
  a multiple of 3, `radius = C_NM_PER_NS * dt` is an **exact** integer
  nanometer distance sitting exactly on the null cone (C and dt are both
  integers, so this is a genuine point on the cone, not an approximation of
  one). `(dx0, dy0, dz0) = (radius/3, 2·radius/3, 2·radius/3)` is an exact
  Pythagorean quadruple (1²+2²+2²=3²) — a genuine on-cone point with **all
  three coordinates nonzero**, not one. This matters: an earlier version of
  this harness placed the second event on a single axis, which a review
  caught (`float_gate.py`'s `_distance_m` reduces `dx²+dy²+dz²` to one
  nonzero term when only one axis is nonzero, so neither summation-order nor
  algorithm variation had anything to reorder — Test 2 could not have shown
  what it claimed to probe). Perturbing only the `dx0` axis by `k`
  nanometers (`k` ∈ {0, ±1, ±10, ±100, ±1,000, ±10,000, ±100,000,
  ±1,000,000}) sweeps straight through the boundary against this genuinely
  multi-axis baseline: `k=0` is exactly null (admissible — the closed future
  cone includes its own boundary), `k>0` is spacelike (must be
  **rejected**), `k<0` is timelike (must be **admitted**). Three magnitudes:
  metric (~1 m), continental (~3,000 km), interplanetary (~78,000,000 km,
  Earth–Mars opposition).
- `float_gate.py` — a faithful float control: positions/times cast to
  float64 or float32, `c` as a float, `c·dt` and `sqrt(dx²+dy²+dz²)` via
  `math.sqrt`, compared with a conventional relative tolerance `eps`. Every
  elementary operation — including the tolerance multiplication and the
  final `lhs + tol` comparison sum, not just the distance computation — is
  routed through the same per-operation precision cast (a review caught an
  earlier version that skipped casting the tolerance arithmetic, which
  silently computed it in double precision even under `precision="float32"`
  and made float32 look more sound than genuine float32 rounding actually
  is). Float32 has no native Python arithmetic, so each cast round-trips the
  value through IEEE-754 binary32 via `struct` (stdlib only — this stays
  inside the repository's stdlib-only discipline). Four variants are
  compared: `float64_strict` (eps=0), `float64_toleranced` (eps=1e-9, ~1e7×
  float64's machine epsilon), `float32_strict` (eps=0), `float32_toleranced`
  (eps=1e-6, ~10× float32's machine epsilon). Neither eps was tuned to
  produce a particular result — see section 6.
- `run_int_vs_float.py` — runs the three tests below over every
  (magnitude, offset) pair and writes `benchmark/int_vs_float/report.json`.

Ground truth for every comparison is `horizon.geometry.causally_admissible`
itself (the frozen kernel), which T1 proves is exactly the real light-cone
condition on every integer input — so "integer disagrees with ground truth"
is impossible by construction, and every mismatch counted below is the float
gate disagreeing with the integer one.

## 2. Test 1 — verdict-mismatch rate (the headline)

`verdict_mismatch_rate` = fraction of the 15 boundary offsets at a magnitude
where a float variant's verdict differs from the exact integer gate.

| magnitude | float64_strict | float64_toleranced | float32_strict | float32_toleranced |
|---|---|---|---|---|
| metric (~1 m) | 0.000 (0/15) | 0.067 (1/15) | 0.200 (3/15) | 0.267 (4/15) |
| continental (~3,000 km) | 0.000 (0/15) | 0.467 (7/15) | 0.467 (7/15) | 0.467 (7/15) |
| interplanetary (~78,000,000 km) | 0.333 (5/15) | 0.467 (7/15) | 0.467 (7/15) | 0.467 (7/15) |

**Integer mismatch vs. its own ground truth: 0/45, every magnitude** — not
because it happened to get every case right on this run, but because it *is*
the ground truth (T1). 55 individual float verdict flips were recorded
across all variants/magnitudes (`report.json`'s `test1_example_flips`, full
list).

### 2.1 Every recorded flip in this run is the dangerous direction

Every one of the 55 recorded flips is a **spacelike pair wrongly ADMITTED**
(the integer gate says `False`, the float gate says `True`) — none is a
timelike pair wrongly rejected. We do not claim this as a general law: a
toleranced variant (`eps>0`) can *only* ever push a verdict from reject
toward admit, never the reverse (adding a non-negative tolerance to `lhs`
cannot make `lhs+tol` smaller), so that half of the asymmetry is structural.
But the two `_strict` (`eps=0`) variants show the same one-sided pattern in
this run too, which is a property of this specific vector family's rounding
behavior, not a proven direction — a differently-shaped near-boundary vector
could plausibly round the other way (an earlier construction of this same
harness did produce reject-direction flips before the section-1 fix changed
the vector geometry; that direction is not reproduced by the current,
non-degenerate vectors, and this document reports what the current data
shows rather than the prior draft's numbers). Either direction is a real
soundness failure; the observed direction here happens to be the one that
matters most for an attacker — a forged or genuinely spacelike claim gets
**admitted** as causally valid, not merely dropped.

### 2.2 Spacelike pair ADMITTED — concrete examples

At continental scale, `float64_toleranced` (the "reasonable eps" variant)
admits a spacelike offset 0.1 mm past the boundary:

```
continental (~3,000 km), dt = 10,006,923 ns
offset k = +100,000 nm (0.1 mm past the light cone → spacelike → must REJECT)
  exact (integer):      admissible = False
  float64, eps=0:        lhs=3000000.043186734 m  dist=3000000.0432200674 m  → False (correct)
  float64, eps=1e-9:     tol = 1e-9 * 3,000,000 m ≈ 3 mm of slack           → True  (WRONG: admits a spacelike pair)
```

The "reasonable" relative tolerance (1e-9, about 1e7× float64's machine
epsilon) becomes ~3 mm of absolute slack at 3,000 km — far larger than the
0.1 mm the attacker moved. This is not a bug in a particular eps value; it
is what a *relative* tolerance does at scale, which is exactly why the
integer gate uses none.

At interplanetary scale the effect is far more severe: `eps=1e-9` scaled to
`lhs ≈ 78,000,000 km` is about **78 meters** of slack —

```
interplanetary, dt = 260,179,994,253 ns
offset k = +100,000 nm (0.1 mm past the light cone → spacelike → must REJECT)
  exact (integer):      admissible = False
  float64, eps=1e-9:     lhs=77999999999.53275 m  dist=77999999999.53278 m
                          tol ≈ 78.0 m of slack → True (WRONG: admits a spacelike pair)
```

any two spacelike events within roughly 78 m of the light cone are silently
admitted by `float64_toleranced` at this magnitude.

`float64_strict` (eps=0, no tolerance to second-guess) still fails at
interplanetary scale — 5/15 offsets — once the offset is small enough
relative to the ~7.8×10¹⁰ m radius that float64's ~2.22×10⁻¹⁶ relative
machine epsilon can't separate `lhs` from `dist` (below roughly the
1,000–10,000 nm offsets in this sweep; the 100,000 nm and 1,000,000 nm
offsets are large enough that float64 resolves them correctly even at this
magnitude — the failure is bounded to the near-boundary region, not
"everything at this magnitude is wrong").

### 2.3 Metric scale: float32 fails where float64 mostly doesn't

At metric scale float64_strict is exact on every tested offset; float32
already isn't. `C_M_PER_S` itself is not exactly representable in float32
(299,792,458 exceeds float32's 24-bit mantissa; it rounds to
299,792,448.0 — visible directly in `report.json`'s witness dumps), and at
`k=1` nm:

```
metric, dt = 3 ns
offset k = +1 nm (1 nm past the light cone → spacelike → must REJECT)
  exact (integer):  admissible = False
  float32, eps=0:    lhs=0.8993773460388184 m  dist=0.8993772864341736 m  → True (WRONG)
```

A 1-nanometer, genuinely spacelike offset is invisible to float32 even at
human scale. `float64_toleranced` also picks up one mismatch at metric scale
(`k=+1`, tol ≈ 0.9 nm — just barely enough slack to swallow a 1 nm
violation), the smallest-magnitude failure recorded in this run.

## 3. Test 2 — cross-platform / cross-setting reproducibility

Same boundary-vector set, four settings that change float rounding but must
never change a *sound* verdict: `float64_xyz_sumsq` (baseline: sum
`dx²+dy²+dz²` in that order, `math.sqrt`), `float64_zyx_sumsq` (reordered
summation — IEEE-754 addition is not associative, so this stands in for a
different compiler/instruction-scheduling/SIMD-lane choice), `float64_xyz_hypot`
(`math.hypot`, a different, more accurate internal algorithm — stands in for
a different libm), `float32_xyz_sumsq` (a different precision setting
entirely). `reproducibility_divergence` = fraction of the 15 offsets at a
magnitude where these settings disagree with **each other**.

| magnitude | float_reproducibility_divergence | integer_reproducibility_divergence |
|---|---|---|
| metric (~1 m) | 0.200 (3/15) | **0.000** |
| continental (~3,000 km) | 0.000 (0/15) | **0.000** |
| interplanetary (~78,000,000 km) | 0.000 (0/15) | **0.000** |

`integer_reproducibility_divergence` is not asserted to be zero — it is
*measured* to be zero, by literally computing `dx²+dy²+dz²` and
`dz²+dy²+dx²` in integer arithmetic and confirming bit-identical results at
every offset and magnitude (integer addition is associative; this is what
that guarantees empirically, not just in principle). `tests/
test_int_vs_float_benchmark.py::test_integer_reproducibility_divergence_is_always_zero`
regression-tests this.

### 3.1 An honest gap between what this run set out to show and what it found

The vectors are now genuinely multi-axis (section 1), which makes
order-of-summation and algorithm divergence *structurally possible* in a way
a single-nonzero-axis vector never could be. In this run, that possibility
is not what fired: all three recorded divergent offsets (metric, k=10/100/
1,000) come from `float32_xyz_sumsq` disagreeing with the float64 settings
— `float64_xyz_sumsq`, `float64_zyx_sumsq`, and `float64_xyz_hypot` agree
with each other on every single offset tested:

```
offset k = +10 nm:   float32_xyz_sumsq=True   float64_xyz_sumsq=False  float64_zyx_sumsq=False  float64_xyz_hypot=False
offset k = +100 nm:  float32_xyz_sumsq=True   float64_xyz_sumsq=False  float64_zyx_sumsq=False  float64_xyz_hypot=False
offset k = +1000 nm: float32_xyz_sumsq=True   float64_xyz_sumsq=False  float64_zyx_sumsq=False  float64_xyz_hypot=False
```

So the honest reading of this run is narrower than "order and algorithm
diverge": at these specific magnitudes and offsets, reordering
`dx²+dy²+dz²` and swapping to `math.hypot` happen not to change the rounded
float64 result, while switching precision (float32) does. IEEE-754
non-associativity of addition is a real, well-documented effect (it is what
makes FMA availability and instruction scheduling observably change results
on real hardware); it simply wasn't triggered by this particular sample.
This is disclosed rather than glossed over — a `0.000` divergence between
`xyz`/`zyx`/`hypot` in this run is a fact about this sample, not a proof
that summation order can't matter for this predicate.

**Honest nuance on the magnitude trend:** float divergence is *not*
monotonically increasing with magnitude — it appears only at metric scale
and drops to zero at continental/interplanetary scale. That drop is **not**
float becoming more reproducible; Test 1 shows all four settings converge on
the *same wrong answer* at those scales (all four say "admissible" for every
spacelike offset once none of them can resolve the perturbation). Cross-check
against Test 1's mismatch table before reading a `0.000` divergence figure
as "safe" — uniform, cross-platform agreement on an incorrect verdict is a
worse property than platforms disagreeing with each other, not a better one.

**Limitation, stated plainly:** no multi-architecture (x86/ARM) rig was
available in this environment. Evaluation order and algorithm choice are
real, standard-library-observable proxies for the same underlying cause, but
this is a documented simulation of that effect, not a live cross-architecture
measurement, and — per the finding above — this particular sample didn't
exercise it. The integer gate needs no such proxy: its associativity is a
property of integer arithmetic itself, true on every architecture that
implements two's-complement integers correctly.

## 4. Test 3 — the honest speed line

Reported plainly, as measured, `time.perf_counter_ns`, 20,000 iterations per
number (`scripts/bench.py`'s methodology).

| magnitude | integer | float64 (naive) | float32 (emulated) | integer / float64 |
|---|---|---|---|---|
| metric (~1 m) | 469 ns | 640 ns | 8,463 ns | 0.73× |
| continental (~3,000 km) | 470 ns | 669 ns | 10,353 ns | 0.70× |
| interplanetary (~78,000,000 km) | 812 ns | 1,123 ns | 8,968 ns | 0.72× |

**This is not spun.** In this environment (CPython 3.11), the integer gate
is *faster* than a naive float64 implementation at every tested magnitude —
CPython's arbitrary-precision integers are efficient enough, and the
~70–80-bit products involved even at interplanetary scale small enough, that
bignum growth hasn't overtaken float64's cost here. (An earlier draft of
this document contained an editorial sentence claiming the integer gate
"can be, and in this environment is, slower" than float64 — that was wrong
and contradicted this table; a review caught the inconsistency and it is
corrected here.) **float64 timing uses `causally_admissible_float64_naive`**,
a minimal, uninstrumented implementation with no per-operation wrapper
calls — the parameterized `causally_admissible_float` used in Tests 1–2
(needed to probe precision/order/algorithm) carries Python-level
instrumentation overhead that would otherwise unfairly inflate float's
measured cost with something that isn't part of the real algorithm.

**float32's number is not representative of float32 hardware speed.**
Python has no native float32 arithmetic; ~9–10 µs/call is the cost of this
harness's `struct.pack`/`struct.unpack` per-operation emulation
(`float_gate.py`), which exists to make float32 *rounding* faithful for
Tests 1–2 (including, after the section-1 fix, the tolerance and final
comparison arithmetic — three more emulated operations than before, which is
why this number rose from an earlier draft's ~7.3–7.6 µs), not to measure
real float32 hardware cost. In C, Rust, or a SIMD-vectorized numeric
library, float32 is typically *faster* than float64, the opposite of what
this table shows — the table is honestly reporting what this environment's
Python-level emulation costs, not making a claim about native float32
performance. This caveat is also recorded per-magnitude in `report.json`.

## 5. Hypotheses — outcome

- **IF-H1** (float mismatch > 0, grows with magnitude; integer mismatch = 0):
  **supported.** Integer mismatch vs. its own ground truth is 0/45 by
  construction (T1). Every float variant mismatches at every magnitude
  except float64_strict at metric/continental; float64_strict's mismatch
  rate rises from 0.000 (metric, continental) to 0.333 (interplanetary) as
  its resolution runs out.
- **IF-H2** (float reproducibility_divergence > 0; integer = 0):
  **supported for precision (float32 vs float64)**, with an honest gap on
  the order/algorithm claim specifically — see section 3.1. Integer
  divergence is measured, not assumed, to be 0.000 at every magnitude;
  float divergence is > 0 only at metric scale in this run, and driven by
  precision, not summation order or sqrt algorithm.
- **IF-H3** (integer may be slower at large magnitude; report the real ratio
  without spin): **the ratio is reported honestly in section 4.** Integer is
  faster than naive float64 at every magnitude tested *in this environment*.
  This is stated as measured, not adjusted to fit the original prediction —
  see the correction note in section 4.

## 6. Honest limits (what this does and does not claim)

- Two eps values were used (0 and one "reasonable" nonzero value per
  precision) — neither tuned toward producing mismatches; section 2 shows
  the range of failure this produces rather than cherry-picking one case.
- Every recorded flip in this run over-admits (never falsely rejects) — see
  section 2.1 for exactly what is and isn't claimed about that asymmetry.
- Section 3.1: the multi-axis vector construction makes order/algorithm
  divergence possible but this run's specific magnitudes/offsets did not
  trigger it; only precision (float32) diverged empirically. Do not read
  this as evidence that summation order is safe in general.
- The float32 emulation (per-operation `struct` round-trip) is a faithful
  model of IEEE-754 binary32 *rounding* semantics, not of hardware float32
  *speed* — see section 4's caveat.
- No live multi-architecture (x86/ARM) or FMA on/off measurement was
  available in this environment; Test 2's evaluation-order/algorithm
  variation is a documented, standard-library-observable proxy for that
  class of divergence, not a substitute for it.
- This benchmark does not modify `horizon/geometry.py` (frozen) or
  `formal/kernel_proof.py`; T1's proof is cited, not re-run, in this
  document (this environment does not have `z3-solver` installed —
  `scripts/run_formal.py` reports it as SKIPPED, matching the repository's
  documented optional-dependency behavior).
- This is not a claim that any deployed system currently uses a floating-point
  light-cone gate — it is a demonstration of what one would cost, built as a
  faithful control, not a strawman.
- This document's numbers were regenerated after a PR review caught two
  correctness issues in the harness itself (float32 tolerance arithmetic not
  routed through the float32 cast; single-axis vectors making Test 2's
  order/algorithm probes vacuous) — see git history for the prior,
  since-corrected numbers if comparing.

## 7. Reproduction

```bash
python3 benchmark/int_vs_float/run_int_vs_float.py
python3 -m unittest tests.test_int_vs_float_benchmark -v
cat benchmark/int_vs_float/report.json   # full per-offset data, all flip examples
```
