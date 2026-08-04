"""H-D: percentile/throughput math is correct, and report assembly flags
a VOID point when the correctness gate failed - a fast wrong answer must
never silently read as a win. [reporting only, per module docstrings]"""
import unittest

from benchmark_harness.adapters.base import OpResult
from benchmark_harness.collect import (acceptance_rate, latency_percentiles,
                                       median_iqr, throughput_per_sec)
from benchmark_harness.report import build_point, build_report


class TestCollect(unittest.TestCase):
    def test_percentiles_on_known_distribution(self):
        # 1..100 ns: p50 should land near the middle, p100 (max) at 100
        vals = list(range(1, 101))
        p = latency_percentiles(vals, percentiles=(50, 100))
        self.assertEqual(p[100], 100)
        self.assertTrue(45 <= p[50] <= 55)

    def test_percentiles_ignore_none_entries(self):
        vals = [10, None, 20, None, 30]
        p = latency_percentiles(vals, percentiles=(100,))
        self.assertEqual(p[100], 30)

    def test_percentiles_empty_input(self):
        p = latency_percentiles([], percentiles=(50, 99))
        self.assertEqual(p, {50: None, 99: None})

    def test_median_iqr(self):
        median, iqr = median_iqr([1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(median, 5)
        self.assertTrue(iqr >= 0)

    def test_median_iqr_empty(self):
        self.assertEqual(median_iqr([]), (None, None))

    def test_throughput_per_sec(self):
        results = [OpResult(i, True) for i in range(10)] + [OpResult(10, False)]
        self.assertAlmostEqual(throughput_per_sec(results, elapsed_s=2.0), 5.0)

    def test_throughput_zero_elapsed(self):
        results = [OpResult(0, True)]
        self.assertEqual(throughput_per_sec(results, elapsed_s=0), 0.0)

    def test_acceptance_rate(self):
        results = [OpResult(0, True), OpResult(1, True), OpResult(2, False)]
        self.assertAlmostEqual(acceptance_rate(results), 2 / 3)

    def test_acceptance_rate_empty(self):
        self.assertEqual(acceptance_rate([]), 0.0)


class TestReport(unittest.TestCase):
    def test_build_point_ok_status(self):
        results = [OpResult(0, True, commit_seq=0, latency_ns=100)]
        verdict = {"ok": True, "checked_edges": 0, "violations": []}
        pt = build_point("causal-store", 0.1, results, 1.0, verdict)
        self.assertEqual(pt["status"], "OK")

    def test_build_point_excludes_rejected_ops_from_latency_percentiles(self):
        # Regression for the fixed bug (see report.py module erratum): a
        # rejected op still carries a real latency_ns (it took time to
        # fail), but it never reached "commit acknowledgment" - including
        # it could make a system that fails fast look artificially
        # low-latency. One slow accepted op, many fast rejected ops: the
        # reported latency must reflect ONLY the accepted one.
        results = [OpResult(0, True, commit_seq=0, latency_ns=500_000)] + \
                 [OpResult(i, False, latency_ns=10, rejected_reason="x")
                  for i in range(1, 20)]
        verdict = {"ok": True, "checked_edges": 0, "violations": []}
        pt = build_point("causal-store", 0.1, results, 1.0, verdict)
        self.assertEqual(pt["latency_ns"][50], 500_000)
        self.assertEqual(pt["latency_ns"][100], 500_000)

    def test_build_point_void_status_on_violation(self):
        results = [OpResult(0, True, commit_seq=0, latency_ns=100)]
        verdict = {"ok": False, "checked_edges": 1,
                  "violations": [{"op_id": 0, "depends_on": 1, "reason": "x"}]}
        pt = build_point("causal-store", 0.1, results, 1.0, verdict)
        self.assertEqual(pt["status"], "VOID_CORRECTNESS_VIOLATION")

    def test_build_report_flags_any_void(self):
        ok_verdict = {"ok": True, "checked_edges": 0, "violations": []}
        bad_verdict = {"ok": False, "checked_edges": 1,
                       "violations": [{"op_id": 0, "depends_on": 1, "reason": "x"}]}
        r1 = [OpResult(0, True, commit_seq=0, latency_ns=10)]
        points = [build_point("a", 0.0, r1, 1.0, ok_verdict),
                 build_point("b", 0.0, r1, 1.0, bad_verdict)]
        rep = build_report(points)
        self.assertTrue(rep["any_void_points"])
        self.assertIn("a", rep["curves"])
        self.assertIn("b", rep["curves"])

    def test_build_report_no_void_when_all_ok(self):
        ok_verdict = {"ok": True, "checked_edges": 0, "violations": []}
        r1 = [OpResult(0, True, commit_seq=0, latency_ns=10)]
        points = [build_point("a", 0.0, r1, 1.0, ok_verdict)]
        rep = build_report(points)
        self.assertFalse(rep["any_void_points"])

    def test_curves_sorted_by_contention_ratio(self):
        ok_verdict = {"ok": True, "checked_edges": 0, "violations": []}
        r1 = [OpResult(0, True, commit_seq=0, latency_ns=10)]
        points = [build_point("a", 0.5, r1, 1.0, ok_verdict),
                 build_point("a", 0.1, r1, 1.0, ok_verdict)]
        rep = build_report(points)
        ratios = [p["contention_ratio"] for p in rep["curves"]["a"]]
        self.assertEqual(ratios, [0.1, 0.5])


if __name__ == "__main__":
    unittest.main()
