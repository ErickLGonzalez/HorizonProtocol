#!/usr/bin/env python3
"""Exact-integer vs floating-point light-cone gate: three tests + report.
[D2-style benchmark, informational - NOT a security gate, NOT a certificate]

The claim under test is soundness and cross-platform reproducibility, NOT
speed - see the module docstrings in this package and
docs/int-vs-float-results.md for the full framing. In one sentence: T1
(`formal/kernel_proof.py`) already PROVES the integer gate has zero
rounding gap against the real light-cone condition over every integer
input; this script demonstrates, with numbers, what that proof guarantees
and what its absence costs a floating-point implementation of the same
predicate.

  Test 1 - verdict-mismatch rate: does the float gate ever disagree with
           the integer gate (ground truth, per T1) near the boundary?
  Test 2 - reproducibility divergence: does the float gate's verdict change
           under settings that must not change a sound one (precision,
           summation order, sqrt algorithm)? The integer gate is checked
           for the analogous property (reordered summation) and must be 0.
  Test 3 - the honest speed line: ns/call for both gates, reported as
           measured, whichever way it falls.

Always exits 0 - this is a report, like scripts/bench.py, not a gate.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from horizon.geometry import causally_admissible, dist2  # noqa: E402
from benchmark.int_vs_float.boundary_gen import (  # noqa: E402
    MAGNITUDES_NM, boundary_dt_ns, boundary_pairs,
)
from benchmark.int_vs_float.float_gate import (  # noqa: E402
    DEFAULT_EPS, causally_admissible_float, causally_admissible_float64_naive,
)

FLOAT_VARIANTS = [
    ("float64_strict", "float64", 0.0),
    ("float64_toleranced", "float64", DEFAULT_EPS["float64"]),
    ("float32_strict", "float32", 0.0),
    ("float32_toleranced", "float32", DEFAULT_EPS["float32"]),
]

REPRO_SETTINGS = [
    ("float64_xyz_sumsq", "float64", "xyz", "sumsq"),
    ("float64_zyx_sumsq", "float64", "zyx", "sumsq"),
    ("float64_xyz_hypot", "float64", "xyz", "hypot"),
    ("float32_xyz_sumsq", "float32", "xyz", "sumsq"),
]


def timeit_ns(fn, iterations):
    start = time.perf_counter_ns()
    for _ in range(iterations):
        fn()
    end = time.perf_counter_ns()
    return (end - start) / iterations


def test1_verdict_mismatch():
    """For every (magnitude, offset) boundary vector, compare each float
    variant's verdict against the exact integer gate (ground truth per
    T1). Returns per-magnitude mismatch rates/rows and a bounded list of
    concrete flipped examples (spacelike-admitted or timelike-rejected)."""
    by_magnitude = {}
    examples = []
    for label in MAGNITUDES_NM:
        rows = []
        counts = {name: 0 for name, _, _ in FLOAT_VARIANTS}
        n = 0
        for bv in boundary_pairs(label):
            n += 1
            row = {"offset_nm": bv["offset_nm"], "exact_admissible": bv["exact_admissible"]}
            for name, precision, eps in FLOAT_VARIANTS:
                fv = causally_admissible_float(bv["t1"], bv["p1"], bv["t2"], bv["p2"],
                                                precision=precision, eps=eps)
                row[name] = fv
                if fv != bv["exact_admissible"]:
                    counts[name] += 1
                    kind = ("spacelike pair ADMITTED (should REJECT)"
                            if fv and not bv["exact_admissible"]
                            else "timelike/null pair REJECTED (should ADMIT)")
                    examples.append({
                        "magnitude": label, "variant": name, "offset_nm": bv["offset_nm"],
                        "t1": bv["t1"], "p1": bv["p1"], "t2": bv["t2"], "p2": bv["p2"],
                        "exact_admissible": bv["exact_admissible"], "float_admissible": fv,
                        "flip": kind,
                    })
            rows.append(row)
        by_magnitude[label] = {
            "n_pairs": n,
            "mismatch_counts": counts,
            "mismatch_rate": {k: v / n for k, v in counts.items()},
            "rows": rows,
        }
    return by_magnitude, examples


def test2_reproducibility():
    """For the same boundary-vector set, does the float verdict change
    across settings (precision / summation order / sqrt algorithm) that
    must never change a sound one? Cross-checks the integer gate's
    analogous property (reordered summation) - must be 0.0, by integer
    associativity, and is measured here rather than merely assumed."""
    by_magnitude = {}
    divergent_examples = []
    for label in MAGNITUDES_NM:
        n = 0
        n_float_divergent = 0
        n_int_divergent = 0
        for bv in boundary_pairs(label):
            n += 1
            verdicts = {}
            for name, precision, order, algorithm in REPRO_SETTINGS:
                eps = DEFAULT_EPS[precision]
                verdicts[name] = causally_admissible_float(
                    bv["t1"], bv["p1"], bv["t2"], bv["p2"],
                    precision=precision, eps=eps, order=order, algorithm=algorithm)
            if len(set(verdicts.values())) > 1:
                n_float_divergent += 1
                if len(divergent_examples) < 8:
                    divergent_examples.append({
                        "magnitude": label, "offset_nm": bv["offset_nm"], "verdicts": verdicts,
                    })
            dx = bv["p2"][0] - bv["p1"][0]
            dy = bv["p2"][1] - bv["p1"][1]
            dz = bv["p2"][2] - bv["p1"][2]
            d_xyz = dist2(bv["p1"], bv["p2"])
            d_zyx = dz * dz + dy * dy + dx * dx
            if d_xyz != d_zyx:
                n_int_divergent += 1
        by_magnitude[label] = {
            "n_pairs": n,
            "settings_compared": [s[0] for s in REPRO_SETTINGS],
            "float_reproducibility_divergence": n_float_divergent / n,
            "integer_reproducibility_divergence": n_int_divergent / n,
        }
    return by_magnitude, divergent_examples


def test3_speed():
    """ns/call for both gates at each magnitude, reported plainly - see
    module docstring: the thesis is soundness, not speed, and a speed loss
    for the integer gate (bignum growth) is reported exactly as measured.

    float64 timing uses `causally_admissible_float64_naive` (minimal,
    uninstrumented - see its docstring), NOT the parameterized
    `causally_admissible_float` used in Test 1/2, because the latter's
    per-operation instrumentation (needed to probe precision/order/
    algorithm) is Python-level overhead unrelated to floating-point
    arithmetic itself and would unfairly inflate float's measured cost.
    float32 has no native Python arithmetic at all - the number reported
    is the cost of this repo's struct-based per-op emulation, not of real
    float32 hardware; this is stated in the report, not just the docs."""
    results = {}
    for label, target_radius_nm in MAGNITUDES_NM.items():
        dt_ns = boundary_dt_ns(target_radius_nm)
        from horizon.geometry import C_NM_PER_NS
        radius_nm = C_NM_PER_NS * dt_ns
        t1, t2 = 0, dt_ns
        p1, p2 = (0, 0, 0), (radius_nm, 0, 0)

        def call_int():
            causally_admissible(t1, p1, t2, p2)

        def call_f64():
            causally_admissible_float64_naive(t1, p1, t2, p2)

        def call_f32():
            causally_admissible_float(t1, p1, t2, p2, precision="float32",
                                       eps=DEFAULT_EPS["float32"])

        int_ns = timeit_ns(call_int, 20_000)
        f64_ns = timeit_ns(call_f64, 20_000)
        f32_ns = timeit_ns(call_f32, 20_000)
        results[label] = {
            "integer_ns_per_call": int_ns,
            "float64_ns_per_call": f64_ns,
            "float32_ns_per_call": f32_ns,
            "float32_caveat": ("Python has no native float32 arithmetic; this "
                                "number is the cost of struct-based per-operation "
                                "emulation (see float_gate.py), NOT representative "
                                "of real float32 hardware speed"),
            "integer_vs_float64_ratio": int_ns / f64_ns,
        }
    return results


def evaluate_hypotheses(t1_by_magnitude, t2_by_magnitude, speed):
    """Falsifiable checks from the handoff (IF-H1..IF-H3), evaluated against
    this run's own numbers - descriptive, not a pass/fail gate."""
    any_float_mismatch = any(
        any(v > 0 for v in m["mismatch_rate"].values())
        for m in t1_by_magnitude.values()
    )
    integer_mismatch_vs_exact = 0  # by construction: the integer gate IS ground truth
    mismatch_grows_with_magnitude = None
    labels = list(t1_by_magnitude)
    if len(labels) >= 2:
        first_rate = max(t1_by_magnitude[labels[0]]["mismatch_rate"].values())
        last_rate = max(t1_by_magnitude[labels[-1]]["mismatch_rate"].values())
        mismatch_grows_with_magnitude = last_rate >= first_rate

    any_float_divergence = any(
        m["float_reproducibility_divergence"] > 0 for m in t2_by_magnitude.values()
    )
    integer_divergence_is_zero = all(
        m["integer_reproducibility_divergence"] == 0.0 for m in t2_by_magnitude.values()
    )

    integer_ever_slower = any(r["integer_vs_float64_ratio"] > 1.0 for r in speed.values())

    return {
        "IF_H1_float_mismatch_gt_zero_and_grows": {
            "float_ever_mismatches": any_float_mismatch,
            "integer_mismatch_vs_exact": integer_mismatch_vs_exact,
            "mismatch_grows_with_magnitude": mismatch_grows_with_magnitude,
            "verdict": "supported" if any_float_mismatch else "falsified (push to larger magnitude)",
        },
        "IF_H2_float_reproducibility_divergence_gt_zero": {
            "float_ever_diverges_across_settings": any_float_divergence,
            "integer_divergence_is_zero": integer_divergence_is_zero,
            "verdict": "supported" if (any_float_divergence and integer_divergence_is_zero) else "falsified",
        },
        "IF_H3_honest_speed_reported_without_spin": {
            "integer_ever_slower_than_float64": integer_ever_slower,
            "note": ("reported as measured in both directions; a speed loss for the "
                     "integer gate is expected at large magnitude (bignum growth) and "
                     "is not evidence against the soundness thesis"),
        },
    }


def main():
    t1_by_magnitude, examples = test1_verdict_mismatch()
    t2_by_magnitude, divergent_examples = test2_reproducibility()
    speed = test3_speed()
    hypotheses = evaluate_hypotheses(t1_by_magnitude, t2_by_magnitude, speed)

    report = {
        "type": "int_vs_float_benchmark_report",
        "note": ("informational only - not a security gate, not a certificate; "
                 "always exits 0. The claim is soundness and cross-platform "
                 "reproducibility, proven for the integer gate by T1 "
                 "(formal/kernel_proof.py), NOT speed - see docs/int-vs-float-results.md"),
        "float_variants": [name for name, _, _ in FLOAT_VARIANTS],
        "reproducibility_settings": [name for name, _, _, _ in REPRO_SETTINGS],
        "offsets_nm": None,  # filled below to avoid importing OFFSETS_NM twice
        "test1_verdict_mismatch_by_magnitude": {
            label: {k: v for k, v in m.items() if k != "rows"}
            for label, m in t1_by_magnitude.items()
        },
        "test1_example_flips": examples,
        "test2_reproducibility_by_magnitude": t2_by_magnitude,
        "test2_divergent_examples": divergent_examples,
        "test3_speed_ns_per_call": speed,
        "hypotheses": hypotheses,
    }
    from benchmark.int_vs_float.boundary_gen import OFFSETS_NM
    report["offsets_nm"] = OFFSETS_NM

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True, default=str)

    print("=== Test 1: verdict-mismatch rate vs. exact integer gate (ground truth, T1) ===")
    for label, m in t1_by_magnitude.items():
        print(f"  {label} ({m['n_pairs']} pairs):")
        for name, rate in m["mismatch_rate"].items():
            print(f"    {name:22s} mismatch_rate={rate:.3f} ({m['mismatch_counts'][name]}/{m['n_pairs']})")
    print(f"\n  {len(examples)} total flipped verdicts recorded (all in report.json)")

    print("\n=== Test 2: reproducibility divergence across settings ===")
    for label, m in t2_by_magnitude.items():
        print(f"  {label}: float_divergence={m['float_reproducibility_divergence']:.3f}  "
              f"integer_divergence={m['integer_reproducibility_divergence']:.3f}")

    print("\n=== Test 3: ns/call (honest speed line, not the thesis) ===")
    for label, r in speed.items():
        print(f"  {label}: integer={r['integer_ns_per_call']:.0f} ns  "
              f"float64={r['float64_ns_per_call']:.0f} ns  "
              f"float32={r['float32_ns_per_call']:.0f} ns  "
              f"(integer/float64 = {r['integer_vs_float64_ratio']:.2f}x)")

    print("\n=== Hypotheses ===")
    for name, h in hypotheses.items():
        print(f"  {name}: {h.get('verdict', h)}")

    print(f"\nreport written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
