"""Run the Z3 proof as a test: all kernel theorems must be PROVEN (unsat). [PROOF]"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kernel_proof import T3_null_cone_exact, run_all


class TestKernelProof(unittest.TestCase):
    def test_all_theorems_proven(self):
        results = run_all()
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertTrue(r["proven"], f"{r['theorem']} not proven: {r['z3_status']}")

    def test_faithfulness_specifically(self):
        from kernel_proof import T1_faithfulness
        self.assertTrue(T1_faithfulness()["proven"])

    def test_biased_predicate_is_caught(self):
        # Regression test for the erratum documented in kernel_proof.py's
        # module docstring: an earlier version of T3 was formulated as a
        # self-referential integer tautology that reported PROVEN
        # unconditionally, regardless of the predicate's actual shape - it
        # would never have caught a broken kernel. The fixed T3 must
        # correctly report a counterexample when the admissibility
        # comparison is deliberately perturbed by a nonzero integer bias,
        # proving the query genuinely depends on the predicate being
        # verified rather than being vacuously true by construction.
        self.assertTrue(T3_null_cone_exact(bias=0)["proven"])
        for bias in (1, -1, 1000, -1000):
            result = T3_null_cone_exact(bias=bias)
            self.assertFalse(result["proven"],
                             f"T3 failed to catch a bias={bias} broken predicate")


if __name__ == "__main__":
    unittest.main()
