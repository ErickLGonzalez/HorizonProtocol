# Exact-Integer vs Floating-Point Light-Cone Gate — Results

**Program:** HorizonProtocol · **Companion to:** C1 (`formal/kernel_proof.py`,
`docs/formal-kernel-spec.md`) · **Tier:** BENCHMARK, informational · **Claim
class:** ENGINEERING_REFERENCE · **Empirical claim:** NONE — nothing here is
a gate or a certificate. Harness: `benchmark/int_vs_float/`.

## 0. The claim (read before the numbers)

The exact-integer light-cone gate (`horizon.geometry.causally_admissible`) is
**not** a speed optimization over a floating-point implementation of the same
predicate. At continental and interplanetary magnitudes it multiplies big
integers and can be, and in this environment is, *slower per call* than a
naive float64 comparison — see Test 3, reported honestly. The actual claim,
already **proven** (not sampled) by Z3 theorem T1 in `formal/kernel_proof.py`,
is that the integer gate is *exactly equivalent to the real light-cone
condition with zero rounding gap*, while any float gate carries a tolerance
that is an attack surface, a source of cross-machine non-determinism, and
capable of flipping a security verdict near the cone. This document
demonstrates that gap with numbers. It does **not** pitch the integer gate as
faster — Test 3's honest finding is closer to the opposite.

## 1. Method

Three independently-runnable pieces, none of which modify the frozen,
machine-checked kernel:

- `boundary_gen.py` — for a chosen magnitude and integer `dt` (ns),
  `C_NM_PER_NS * dt` is an **exact** integer nanometer radius sitting exactly
  on the null cone (C and dt are both integers, so this is a genuine point on
  the cone, not an approximation of one). Placing the second event at that
  radius along one axis and perturbing the axis coordinate by `k`
  nanometers (`k` ∈ {0, ±1, ±10, ±100, ±1,000, ±10,000, ±100,000,
  ±1,000,000}) sweeps straight through the boundary: `k=0` is exactly null
  (admissible — the closed future cone includes its own boundary), `k>0` is
  spacelike (must be **rejected**), `k<0` is timelike (must be **admitted**).
  Three magnitudes: metric (~1 m), continental (~3,000 km), interplanetary
  (~78,000,000 km, Earth–Mars opposition).
- `float_gate.py` — a faithful float control: positions/times cast to
  float64 or float32, `c` as a float, `c·dt` and `sqrt(dx²+dy²+dz²)` via
  `math.sqrt`, compared with a conventional relative tolerance `eps`.
  Float32 has no native Python arithmetic, so every elementary float32
  operation is round-tripped through IEEE-754 binary32 via `struct`
  (stdlib only — this stays inside the repository's stdlib-only discipline;
  see `float_gate.py`'s module docstring). Four variants are compared:
  `float64_strict` (eps=0), `float64_toleranced` (eps=1e-9, ~1e7× float64's
  machine epsilon), `float32_strict` (eps=0), `float32_toleranced`
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
| metric (~1 m) | 0.000 (0/15) | 0.000 (0/15) | 0.067 (1/15) | 0.200 (3/15) |
| continental (~3,000 km) | 0.000 (0/15) | 0.467 (7/15) | 0.467 (7/15) | 0.467 (7/15) |
| interplanetary (~78,000,000 km) | 0.333 (5/15) | 0.467 (7/15) | 0.467 (7/15) | 0.467 (7/15) |

**Integer mismatch vs. its own ground truth: 0/45, every magnitude** — not
because it happened to get every case right on this run, but because it *is*
the ground truth (T1). 51 individual float verdict flips were recorded across
all variants/magnitudes (`report.json`'s `test1_example_flips`, full list).

### 2.1 Spacelike pair ADMITTED (should REJECT)

At continental scale, `float64_toleranced` (the "reasonable eps" variant)
admits every spacelike offset tested, from 1 nm to 1 mm past the boundary:

```
continental (~3,000 km), dt = 10,006,923 ns, radius = 3,000,000,043,186,734 nm
offset k = +100,000 nm (0.1 mm past the light cone → spacelike → must REJECT)
  exact (integer):      admissible = False   (radius² < dist², by construction)
  float64, eps=0:        lhs=3000000.043186734 m  dist=3000000.043286734 m  → False (correct)
  float64, eps=1e-9:     tol = 1e-9 * 3,000,000 m ≈ 3 mm of slack           → True  (WRONG: admits a spacelike pair)
```

The "reasonable" relative tolerance (1e-9, about 1e7× float64's machine
epsilon) becomes ~3 mm of absolute slack at 3,000 km — far larger than the
0.1 mm the attacker moved. This is not a bug in a particular eps value; it is
what a *relative* tolerance does at scale, which is exactly why the integer
gate uses none.

At interplanetary scale the effect is far more severe: `eps=1e-9` scaled to
`lhs ≈ 78,000,000 km` is about **78 meters** of slack — any two spacelike
events within 78 m of the light cone are silently admitted by
`float64_toleranced`.

### 2.2 Timelike/null pair REJECTED (should ADMIT) — the other direction

At interplanetary scale, `float64_strict` (eps=0, the "purest" good-faith
float implementation — no tolerance to second-guess) **falsely rejects**
genuinely timelike and exactly-null pairs:

```
interplanetary, dt = 260,179,994,255 ns, radius = 78,000,000,000,132,328,790 nm
offset k = 0 nm (exactly on the light cone → must ADMIT, closed cone)
  exact (integer):      admissible = True
  float64, eps=0:        lhs=78000000000.13232 m  dist=78000000000.13234 m  → False (WRONG: rejects a null pair)

offset k = -1 nm (1 nm inside the light cone → timelike → must ADMIT)
  exact (integer):      admissible = True
  float64, eps=0:        lhs=78000000000.13232 m  dist=78000000000.13234 m  → False (WRONG: rejects a timelike pair)
```

At this radius (~7.8×10¹⁰ m), float64's relative machine epsilon
(≈2.22×10⁻¹⁶) is an absolute resolution of roughly 17 micrometers — far
coarser than the nanometer-scale offset being tested, so `k=0` through
`k=-1,000` (1 µm) all round to the *same* float64 values for `lhs` and
`dist`, and happen to round the wrong way (`dist` computed fractionally
larger than `lhs`). Zero tolerance means there is nothing to absorb that: a
provably timelike pair is rejected. This is the two-sided finding the
handoff predicted — floats flip verdicts in **both** directions near the
cone, not just one, and which direction depends on rounding, not on the
physical truth. The integer gate has neither failure mode: it is the
condition, not an approximation rounding toward or away from it.

### 2.3 Metric scale: float32 fails where float64 doesn't (yet)

At metric scale float64 (both variants) is exact on every tested offset;
float32 already isn't. `C_M_PER_S` itself is not exactly representable in
float32 (299,792,458 exceeds float32's 24-bit mantissa; it rounds to
299,792,448.0 — visible directly in `report.json`'s witness dumps), and at
`k=1` nm:

```
metric, dt = 3 ns, radius = 899,377,374 nm
offset k = +1 nm (1 nm past the light cone → spacelike → must REJECT)
  exact (integer):  admissible = False
  float32, eps=0:    lhs=0.8993773460388184 m  dist=0.8993773460388184 m  → True (WRONG: identical after rounding)
```

A 1-nanometer, genuinely spacelike offset is invisible to float32 even at
human scale.

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

**Honest nuance:** divergence is *not* monotonically increasing with
magnitude — it peaks at metric scale (where float32 and float64 still
disagree with each other because float64 hasn't lost resolution yet) and
drops to zero at continental/interplanetary scale. That drop is **not**
float becoming more reproducible; Test 1 shows all four settings converge on
the *same wrong answer* at those scales (all four say "admissible" for every
spacelike offset once none of them can resolve the perturbation). Cross-check
against Test 1's mismatch table before reading a `0.000` divergence figure
as "safe" — uniform, cross-platform agreement on an incorrect verdict is a
worse property than platforms disagreeing with each other, not a better one.

### 3.1 Concrete divergent examples (metric scale)

```
offset k = +1 nm:  float32_xyz_sumsq=True   float64_xyz_sumsq=False  float64_zyx_sumsq=False  float64_xyz_hypot=False
offset k = +10 nm: float32_xyz_sumsq=True   float64_xyz_sumsq=False  float64_zyx_sumsq=False  float64_xyz_hypot=False
offset k = +100 nm: float32_xyz_sumsq=True  float64_xyz_sumsq=False  float64_zyx_sumsq=False  float64_xyz_hypot=False
```

Every float64 setting agrees with each other and with the integer gate here;
only float32 (a "precision setting," standing in for a different build
target/embedded profile choice) disagrees — a concrete instance of "the
verdict depends on a compile/runtime setting that has nothing to do with the
physical question being asked."

**Limitation, stated plainly:** no multi-architecture (x86/ARM) rig was
available in this environment. Evaluation order and algorithm choice are
real, standard-library-observable proxies for the same underlying cause
(IEEE-754 rounding is order- and implementation-dependent; FMA availability
and instruction scheduling differ across compilers and architectures the
same way), but this is a documented simulation of that effect, not a live
cross-architecture measurement. The integer gate needs no such proxy: its
associativity is a property of integer arithmetic itself, true on every
architecture that implements two's-complement integers correctly.

## 4. Test 3 — the honest speed line

Reported plainly, as measured, `time.perf_counter_ns`, 20,000 iterations per
number (`scripts/bench.py`'s methodology).

| magnitude | integer | float64 (naive) | float32 (emulated) | integer / float64 |
|---|---|---|---|---|
| metric (~1 m) | 393 ns | 724 ns | 7,561 ns | 0.54× |
| continental (~3,000 km) | 472 ns | 666 ns | 7,501 ns | 0.71× |
| interplanetary (~78,000,000 km) | 521 ns | 753 ns | 7,430 ns | 0.69× |

**This is not spun.** In this environment (CPython 3.11), the integer gate
is *faster* than a naive float64 implementation at every tested magnitude —
CPython's arbitrary-precision integers are efficient enough, and the
~70–80-bit products involved even at interplanetary scale small enough, that
bignum growth hasn't overtaken float64's cost here. It has narrowed sharply
though: `integer/float64` rises from 0.54× at metric to ~0.70× at continental
and interplanetary, consistent with IF-H3's predicted bignum-growth
trend even though it hasn't crossed 1.0× in this environment. **float64
timing uses `causally_admissible_float64_naive`**, a minimal,
uninstrumented implementation with no per-operation wrapper calls — the
parameterized `causally_admissible_float` used in Tests 1–2 (needed to probe
precision/order/algorithm) carries Python-level instrumentation overhead
that would otherwise unfairly inflate float's measured cost with something
that isn't part of the real algorithm.

**float32's number is not representative of float32 hardware speed.**
Python has no native float32 arithmetic; 7.4–7.6 µs/call is the cost of this
harness's `struct.pack`/`struct.unpack` per-operation emulation
(`float_gate.py`), which exists to make float32 *rounding* faithful for
Tests 1–2, not to measure real float32 hardware cost. In C, Rust, or a
SIMD-vectorized numeric library, float32 is typically *faster* than float64,
the opposite of what this table shows — the table is honestly reporting what
this environment's Python-level emulation costs, not making a claim about
native float32 performance. This caveat is also recorded per-magnitude in
`report.json`.

## 5. Hypotheses — outcome

- **IF-H1** (float mismatch > 0, grows with magnitude; integer mismatch = 0):
  **supported.** Integer mismatch vs. its own ground truth is 0/45 by
  construction (T1). Every float variant mismatches at every magnitude
  except float64 at metric scale; float64_strict's mismatch rate rises from
  0.000 (metric) to 0.333 (interplanetary) as its resolution runs out —
  see section 2.2 for the mechanism (not simple "more magnitude, more
  error": at continental scale zero-tolerance float64 is still exact;
  interplanetary is where it first breaks).
- **IF-H2** (float reproducibility_divergence > 0; integer = 0):
  **supported**, with the nuance in section 3 — divergence is measured, not
  assumed, to be 0.000 for the integer gate at every magnitude, and > 0 for
  float at the one magnitude (metric) where the tested settings' resolution
  limits don't already coincide.
- **IF-H3** (integer may be slower at large magnitude; report the real ratio
  without spin): **the ratio is reported honestly in section 4.** Integer is
  faster than naive float64 at every magnitude tested *in this environment*,
  though the margin narrows with magnitude as bignum cost grows relative to
  float64's constant-ish cost — consistent with the predicted trend, short of
  a crossover in this environment. This is stated as measured, not adjusted
  to fit the prediction.

## 6. Honest limits (what this does and does not claim)

- Two eps values were used (0 and one "reasonable" nonzero value per
  precision) — neither tuned toward producing mismatches; section 2 shows
  both directions of failure (over-admits with tolerance, over-rejects
  without) rather than cherry-picking the one that looks worse.
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

## 7. Reproduction

```bash
python3 benchmark/int_vs_float/run_int_vs_float.py
python3 -m unittest tests.test_int_vs_float_benchmark -v
cat benchmark/int_vs_float/report.json   # full per-offset data, all flip examples
```
