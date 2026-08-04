"""H-A: the workload generator is deterministic and its dependency graph
is physically grounded. [SOUND]"""
import unittest

from causalstore.geometry import C_NM_PER_NS
from benchmark_harness.workload_gen import DEFAULT_CONTENTION_SWEEP, generate_trace

REGIONS = ["us-east", "us-west", "eu-west"]
POSITIONS = {
    "us-east": (0, 0, 0),
    "us-west": (C_NM_PER_NS * 12_000_000, 0, 0),
    "eu-west": (C_NM_PER_NS * 28_000_000, 0, 0),
}


class TestWorkloadGen(unittest.TestCase):
    def test_deterministic_for_same_seed(self):
        a = generate_trace(REGIONS, POSITIONS, n_keys=50, n_ops=300,
                           contention_ratio=0.3, seed="s1")
        b = generate_trace(REGIONS, POSITIONS, n_keys=50, n_ops=300,
                           contention_ratio=0.3, seed="s1")
        self.assertEqual(a["trace"], b["trace"])
        self.assertEqual(a["concurrent_pairs"], b["concurrent_pairs"])

    def test_different_seed_differs(self):
        a = generate_trace(REGIONS, POSITIONS, n_keys=50, n_ops=300,
                           contention_ratio=0.3, seed="s1")
        b = generate_trace(REGIONS, POSITIONS, n_keys=50, n_ops=300,
                           contention_ratio=0.3, seed="s2")
        self.assertNotEqual(a["trace"], b["trace"])

    def test_contention_zero_yields_no_dependencies_or_conflicts(self):
        # n_keys is astronomically larger than n_ops so an INCIDENTAL
        # collision from the uniform "fresh key" draw is negligible; this
        # isolates the property actually being tested: contention_ratio=0
        # means the DELIBERATE recency-based contend roll never fires.
        out = generate_trace(REGIONS, POSITIONS, n_keys=10**12, n_ops=200,
                             contention_ratio=0.0, seed="s3")
        for op in out["trace"]:
            self.assertEqual(op["depends_on"], [])
        self.assertEqual(out["concurrent_pairs"], [])

    def test_same_region_same_key_pair_is_always_a_dependency(self):
        # two writes to the same key from the SAME region are never
        # physically concurrent (required_ns = 0, elapsed_ns > 0 always)
        out = generate_trace(["us-east"], {"us-east": (0, 0, 0)}, n_keys=1,
                             n_ops=50, contention_ratio=1.0, seed="s4")
        for op in out["trace"][1:]:
            self.assertEqual(op["depends_on"], [op["op_id"] - 1])
        self.assertEqual(out["concurrent_pairs"], [])

    def test_dependency_edges_always_satisfy_the_physical_light_time_floor(self):
        # the invariant workload_gen must never violate, regardless of
        # which regions any given pair happens to land on: a depends_on
        # edge may only exist where enough logical time elapsed for a
        # signal to have crossed the two origins' separation. Force heavy
        # same-key contention with tiny time steps so both same-region
        # (trivially satisfied, required_ns=0) and cross-region (usually
        # NOT satisfied) pairs both occur in one run.
        from causalstore.geometry import min_light_time_ns
        out = generate_trace(["us-east", "eu-west"], POSITIONS, n_keys=1,
                             n_ops=200, contention_ratio=1.0, seed="s5",
                             time_step_range=(1, 10))
        trace = out["trace"]
        for op in trace:
            for dep_id in op["depends_on"]:
                pred = trace[dep_id]
                required_ns = min_light_time_ns(POSITIONS[pred["origin_region"]],
                                                POSITIONS[op["origin_region"]])
                elapsed_ns = op["t_logical_ns"] - pred["t_logical_ns"]
                self.assertGreaterEqual(elapsed_ns, required_ns,
                                        f"op {op['op_id']} depends_on {dep_id} "
                                        f"but the light-time floor was not met")
        for pred_id, op_id in out["concurrent_pairs"]:
            pred, op = trace[pred_id], trace[op_id]
            required_ns = min_light_time_ns(POSITIONS[pred["origin_region"]],
                                            POSITIONS[op["origin_region"]])
            elapsed_ns = op["t_logical_ns"] - pred["t_logical_ns"]
            self.assertLess(elapsed_ns, required_ns,
                            f"pair ({pred_id},{op_id}) flagged concurrent but "
                            f"actually satisfies the light-time floor")
        # with regions chosen per-op and heavy same-key contention, both
        # mechanisms should actually occur in this run - a generator that
        # always/never triggers one of them would be a coverage gap, not
        # a passing test.
        self.assertTrue(any(op["depends_on"] for op in trace))
        self.assertTrue(out["concurrent_pairs"])

    def test_invalid_contention_ratio_rejected(self):
        with self.assertRaises(ValueError):
            generate_trace(REGIONS, POSITIONS, n_keys=10, n_ops=10,
                           contention_ratio=1.5, seed="s6")

    def test_missing_region_position_rejected(self):
        with self.assertRaises(ValueError):
            generate_trace(["nowhere"], POSITIONS, n_keys=10, n_ops=10,
                           contention_ratio=0.1, seed="s7")

    def test_default_contention_sweep_is_the_documented_points(self):
        self.assertEqual(DEFAULT_CONTENTION_SWEEP,
                         (0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0))


if __name__ == "__main__":
    unittest.main()
