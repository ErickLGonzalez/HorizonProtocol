"""H-E: the adapter contract. [SOUND]

causal-store and the total-order baseline are the two required adapters
for this build's local gate (design doc section 10, phase-2 deliverable);
Cockroach/YugabyteDB/Tiga must report AdapterUnavailable LOUDLY in this
environment (no client library / cluster / packaged release), never
silently skip and never fabricate a result.
"""
import unittest

from causalstore.geometry import C_NM_PER_NS
from benchmark_harness import driver, verify_order
from benchmark_harness.adapters.base import AdapterUnavailable
from benchmark_harness.adapters.baseline_adapter import TotalOrderBaselineAdapter
from benchmark_harness.adapters.causalstore_adapter import CausalStoreAdapter
from benchmark_harness.adapters.cockroach_adapter import CockroachAdapter
from benchmark_harness.adapters.tiga_adapter import TigaAdapter
from benchmark_harness.adapters.yugabyte_adapter import YugabyteAdapter
from benchmark_harness.workload_gen import generate_trace

REGIONS = ["us-east", "us-west", "eu-west"]
POSITIONS = {
    "us-east": (0, 0, 0),
    "us-west": (C_NM_PER_NS * 12_000_000, 0, 0),
    "eu-west": (C_NM_PER_NS * 28_000_000, 0, 0),
}
REGION_CLOCKS = {r: {"pos_nm": POSITIONS[r], "u_ns": 1000} for r in REGIONS}


class TestCausalStoreAndBaselineAdapters(unittest.TestCase):
    def setUp(self):
        self.trace = generate_trace(REGIONS, POSITIONS, n_keys=100, n_ops=500,
                                    contention_ratio=0.2, seed="adapter-test")["trace"]

    def test_causalstore_adapter_end_to_end_no_violations(self):
        a = CausalStoreAdapter(REGION_CLOCKS)
        a.setup(REGIONS)
        results = driver.run(a, self.trace, mode="closed", concurrency=4)
        by_id = {r.op_id: r for r in results}
        verdict = verify_order.verify(self.trace, by_id)
        self.assertTrue(verdict["ok"], verdict["violations"])
        self.assertGreater(verdict["checked_edges"], 0)
        diag = a.diagnostics()
        self.assertIn("coordination_free_rate", diag)

    def test_baseline_adapter_end_to_end_no_violations(self):
        a = TotalOrderBaselineAdapter()
        a.setup(REGIONS)
        results = driver.run(a, self.trace, mode="closed", concurrency=4)
        by_id = {r.op_id: r for r in results}
        verdict = verify_order.verify(self.trace, by_id)
        self.assertTrue(verdict["ok"], verdict["violations"])
        self.assertTrue(all(r.accepted for r in results))  # never rejects

    def test_causalstore_adapter_missing_region_clocks_is_unavailable(self):
        a = CausalStoreAdapter({"us-east": REGION_CLOCKS["us-east"]})
        with self.assertRaises(AdapterUnavailable):
            a.setup(REGIONS)

    def test_baseline_commit_seq_is_strictly_increasing_under_concurrency(self):
        a = TotalOrderBaselineAdapter()
        a.setup(REGIONS)
        results = driver.run(a, self.trace, mode="closed", concurrency=8)
        seqs = sorted(r.commit_seq for r in results)
        self.assertEqual(seqs, list(range(len(results))))  # a true total order


class TestCompetitorAdaptersReportUnavailableHonestly(unittest.TestCase):
    def test_cockroach_without_dsn_is_unavailable(self):
        a = CockroachAdapter()
        with self.assertRaises(AdapterUnavailable):
            a.setup(REGIONS)

    def test_yugabyte_without_dsn_is_unavailable(self):
        a = YugabyteAdapter()
        with self.assertRaises(AdapterUnavailable):
            a.setup(REGIONS)

    def test_tiga_is_always_unavailable_in_this_environment(self):
        a = TigaAdapter()
        with self.assertRaises(AdapterUnavailable):
            a.setup(REGIONS)

    def test_no_adapter_silently_returns_a_fake_result_on_setup_failure(self):
        # every competitor adapter's setup() either succeeds or raises
        # AdapterUnavailable - it must never return a falsy/empty value
        # that a caller could mistake for "ran with no data."
        for cls in (CockroachAdapter, YugabyteAdapter, TigaAdapter):
            a = cls()
            with self.assertRaises(AdapterUnavailable):
                a.setup(REGIONS)


if __name__ == "__main__":
    unittest.main()
