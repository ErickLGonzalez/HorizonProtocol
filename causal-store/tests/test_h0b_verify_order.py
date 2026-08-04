"""H-B: verify_order.py must both accept a correct order AND catch an
injected violation - a gate that only ever returns ok=True is worthless.
[SOUND]"""
import unittest

from benchmark_harness.adapters.base import OpResult
from benchmark_harness.verify_order import verify


def op(op_id, depends_on=()):
    return {"op_id": op_id, "depends_on": list(depends_on)}


class TestVerifyOrder(unittest.TestCase):
    def test_correctly_ordered_dependency_passes(self):
        trace = [op(0), op(1, depends_on=[0])]
        results = {0: OpResult(0, True, commit_seq=0),
                  1: OpResult(1, True, commit_seq=1)}
        v = verify(trace, results)
        self.assertTrue(v["ok"])
        self.assertEqual(v["checked_edges"], 1)
        self.assertEqual(v["violations"], [])

    def test_violated_dependency_is_caught(self):
        # op 1 depends on op 0, but op 0's commit_seq is LATER - a real
        # causality violation, and the whole point of this gate.
        trace = [op(0), op(1, depends_on=[0])]
        results = {0: OpResult(0, True, commit_seq=5),
                  1: OpResult(1, True, commit_seq=2)}
        v = verify(trace, results)
        self.assertFalse(v["ok"])
        self.assertEqual(len(v["violations"]), 1)
        self.assertEqual(v["violations"][0]["reason"], "dependency_not_ordered_before")

    def test_rejected_predecessor_is_not_a_violation(self):
        # if the dependency itself never committed, there is nothing to
        # order - not a violation, just nothing to check.
        trace = [op(0), op(1, depends_on=[0])]
        results = {0: OpResult(0, False, rejected_reason="x"),
                  1: OpResult(1, True, commit_seq=0)}
        v = verify(trace, results)
        self.assertTrue(v["ok"])

    def test_missing_result_is_a_violation_not_silently_skipped(self):
        trace = [op(0), op(1, depends_on=[0])]
        results = {1: OpResult(1, True, commit_seq=0)}  # op 0's result missing
        v = verify(trace, results)
        self.assertFalse(v["ok"])
        self.assertEqual(v["violations"][0]["reason"], "missing_result")

    def test_no_dependencies_means_nothing_to_check(self):
        trace = [op(0), op(1)]
        results = {0: OpResult(0, True, commit_seq=0),
                  1: OpResult(1, True, commit_seq=1)}
        v = verify(trace, results)
        self.assertTrue(v["ok"])
        self.assertEqual(v["checked_edges"], 0)


if __name__ == "__main__":
    unittest.main()
