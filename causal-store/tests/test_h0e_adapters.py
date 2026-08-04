"""H-E: the adapter contract. [SOUND]

causal-store and the total-order baseline are the two required adapters
for this build's local gate (design doc section 10, phase-2 deliverable);
Cockroach/YugabyteDB/Tiga must report AdapterUnavailable LOUDLY in this
environment (no client library / cluster / packaged release), never
silently skip and never fabricate a result.
"""
import sys
import types
import unittest
import unittest.mock

from causalstore.geometry import C_NM_PER_NS
from benchmark_harness import driver, verify_order
from benchmark_harness.adapters.base import AdapterUnavailable
from benchmark_harness.adapters.baseline_adapter import TotalOrderBaselineAdapter
from benchmark_harness.adapters.causalstore_adapter import CausalStoreAdapter
from benchmark_harness.adapters.cockroach_adapter import CockroachAdapter
from benchmark_harness.adapters.sql_common import PostgresWireAdapter
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


class _FakeDatabase:
    """Shared state a fake psycopg2 `connect()` call always returns a
    handle to - simulating a real database that PERSISTS across separate
    connections/setup() calls, which is exactly the property the fixed
    bug (see sql_common.py's module erratum) depended on to reproduce."""
    def __init__(self):
        self.rows = set()


class _FakeCursor:
    def __init__(self, db):
        self.db = db
        self._last_fetch = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        s = sql.strip()
        if s.startswith("SELECT 1"):
            self._last_fetch = (1,) if params[0] in self.db.rows else None
        elif s.startswith("INSERT"):
            op_id = params[0]
            if op_id in self.db.rows:
                raise Exception("duplicate key value violates unique constraint")
            self.db.rows.add(op_id)
        elif s.startswith("DELETE"):
            self.db.rows.clear()

    def fetchone(self):
        return self._last_fetch


class _FakeConn:
    def __init__(self, db):
        self.db = db
        self.autocommit = False

    def cursor(self):
        return _FakeCursor(self.db)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class TestSqlCommonTableClearing(unittest.TestCase):
    """Regression for the fixed bug: setup() used to only CREATE TABLE IF
    NOT EXISTS, never clearing prior rows, so a second setup() against the
    same persistent database collided with the first run's op_id=0 row
    and reported an ordinary rejection instead of a real commit."""

    def _fake_psycopg2(self, db):
        return types.SimpleNamespace(connect=lambda dsn: _FakeConn(db))

    def test_second_setup_against_same_database_clears_stale_rows(self):
        db = _FakeDatabase()
        with unittest.mock.patch.dict(sys.modules, {"psycopg2": self._fake_psycopg2(db)}):
            a = PostgresWireAdapter(dsn="fake://shared-db")
            a.setup(["r1"])
            r1 = a.apply_op({"op_id": 0, "key": "k", "value": "v1", "depends_on": []})
            self.assertTrue(r1.accepted)

            # a second adapter instance/setup() against the SAME database
            # (e.g. the next contention point in a sweep) must not collide
            # with the first run's op_id=0 row.
            b = PostgresWireAdapter(dsn="fake://shared-db")
            b.setup(["r1"])
            r2 = b.apply_op({"op_id": 0, "key": "k", "value": "v2", "depends_on": []})
            self.assertTrue(r2.accepted,
                            "second setup() did not clear stale rows from "
                            "the first run - op_id=0 collided")

    def test_without_the_fix_the_collision_would_have_been_a_rejection(self):
        # sanity check that the fake actually models a real unique-key
        # collision (proves the test is exercising the right failure mode)
        db = _FakeDatabase()
        db.rows.add(0)  # simulate a stale row already present, no clear
        with unittest.mock.patch.dict(sys.modules, {"psycopg2": self._fake_psycopg2(db)}):
            conn = _FakeConn(db)
            with conn.cursor() as cur:
                with self.assertRaises(Exception):
                    cur.execute("INSERT INTO causal_bench_events (op_id, key_name, "
                               "value_text, depends_on_op_id) VALUES (%s, %s, %s, %s)",
                               (0, "k", "v", None))


if __name__ == "__main__":
    unittest.main()
