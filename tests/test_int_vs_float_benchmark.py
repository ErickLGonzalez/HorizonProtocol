"""Sanity tests for benchmark/int_vs_float/ - this is an informational
comparison harness, not a security gate (see its own module docstrings and
docs/int-vs-float-results.md), so these tests check the harness is wired
together correctly and its one guaranteed invariant holds, not any
PASS/FAIL security verdict.
"""
import unittest

from benchmark.int_vs_float.boundary_gen import MAGNITUDES_NM, boundary_pairs
from benchmark.int_vs_float.float_gate import (
    DEFAULT_EPS, causally_admissible_float, causally_admissible_float64_naive,
)
from benchmark.int_vs_float.run_int_vs_float import (
    test1_verdict_mismatch, test2_reproducibility, test3_speed,
)
from horizon.geometry import causally_admissible


class TestBoundaryGen(unittest.TestCase):
    def test_ground_truth_matches_construction(self):
        # by construction: radius_nm = C*dt exactly, so offset k<=0 (on or
        # inside the null cone) must be admissible and k>0 (outside) must
        # not - cross-checked here against the real, unmodified kernel
        # rather than assumed.
        for label in MAGNITUDES_NM:
            for bv in boundary_pairs(label):
                expected = bv["offset_nm"] <= 0
                self.assertEqual(bv["exact_admissible"], expected,
                                 f"{label} k={bv['offset_nm']}")
                self.assertEqual(
                    bv["exact_admissible"],
                    causally_admissible(bv["t1"], bv["p1"], bv["t2"], bv["p2"]))

    def test_on_cone_point_is_exact_integer(self):
        for label in MAGNITUDES_NM:
            bv = next(iter(boundary_pairs(label)))
            self.assertEqual(bv["offset_nm"], 0)
            self.assertTrue(bv["exact_admissible"])


class TestFloatGate(unittest.TestCase):
    def test_agrees_with_integer_gate_well_inside_resolution(self):
        # at metric scale, well within float64's resolution, the float
        # gate should agree with the exact kernel - a basic sanity check
        # that the float control isn't a strawman that's simply broken.
        bvs = list(boundary_pairs("metric (~1 m)"))
        bv = next(b for b in bvs if b["offset_nm"] == 0)
        got = causally_admissible_float(bv["t1"], bv["p1"], bv["t2"], bv["p2"],
                                         precision="float64", eps=0.0)
        self.assertEqual(got, bv["exact_admissible"])

    def test_naive_and_instrumented_float64_agree(self):
        # the Test 3 speed path (causally_admissible_float64_naive) must
        # decide the SAME predicate as the instrumented, parameterized
        # path used in Test 1/2 - only the implementation is stripped
        # down, not the arithmetic.
        for label in MAGNITUDES_NM:
            for bv in boundary_pairs(label):
                naive = causally_admissible_float64_naive(
                    bv["t1"], bv["p1"], bv["t2"], bv["p2"], eps=DEFAULT_EPS["float64"])
                instrumented = causally_admissible_float(
                    bv["t1"], bv["p1"], bv["t2"], bv["p2"],
                    precision="float64", eps=DEFAULT_EPS["float64"])
                self.assertEqual(naive, instrumented, f"{label} k={bv['offset_nm']}")


class TestRunner(unittest.TestCase):
    def test_integer_reproducibility_divergence_is_always_zero(self):
        # the one hard invariant this harness checks: integer addition is
        # associative, so reordered summation must be bit-identical -
        # unlike the float side, this must be 0.0 at every magnitude.
        by_magnitude, _ = test2_reproducibility()
        for label, m in by_magnitude.items():
            self.assertEqual(m["integer_reproducibility_divergence"], 0.0, label)

    def test_report_functions_run_without_error(self):
        t1, examples = test1_verdict_mismatch()
        self.assertEqual(set(t1), set(MAGNITUDES_NM))
        for m in t1.values():
            self.assertGreater(m["n_pairs"], 0)
        speed = test3_speed()
        for r in speed.values():
            self.assertGreater(r["integer_ns_per_call"], 0)
            self.assertGreater(r["float64_ns_per_call"], 0)


if __name__ == "__main__":
    unittest.main()
