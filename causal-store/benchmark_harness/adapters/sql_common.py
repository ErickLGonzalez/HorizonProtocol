"""Shared plumbing for the Postgres-wire-compatible competitor adapters
(CockroachDB, YugabyteDB).  [HEURISTIC - external system, outside the
trusted/exact path by design; NOT exercised against a live cluster in
this build - see module docstrings on cockroach_adapter.py /
yugabyte_adapter.py]

`commit_seq` is assigned by THIS adapter, under a lock, strictly AFTER a
transaction's COMMIT call returns successfully - i.e. it is exactly
"this client's own observed order of successful commits" (the same
definition adapters/base.py documents, and the same mechanism
baseline_adapter.py already uses). This deliberately does NOT rely on
any cluster-internal HLC/commit-timestamp precision: because driver.py
already guarantees a dependent op's predecessor result is known before
the dependent is even issued (see driver.py's docstring), a simple
local, post-commit counter is sufficient for verify_order.py's
correctness check regardless of how either database schedules
transactions internally.

(Erratum: an earlier version's `setup()` only did `CREATE TABLE IF NOT
EXISTS`, never clearing prior rows. Every generated trace restarts
`op_id` at 0 (workload_gen.generate_trace()), but a real database table
persists across `setup()` calls - so the SECOND contention point, a
repetition, or a rerun against the same database would try to INSERT
`op_id=0` again, collide with the FIRST point's still-present row, and
have every op with a colliding op_id caught by `apply_op`'s exception
handler as an ordinary rejection. Nearly an entire sweep beyond its first
point could silently measure duplicate-key failures rather than genuine
CockroachDB/YugabyteDB commits. Fixed: `setup()` now clears the table
before each run, so every `setup()` call starts from a genuinely clean
slate regardless of what a prior invocation left behind.)
"""
import itertools
import threading
import time

from .base import Adapter, AdapterUnavailable, OpResult

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS causal_bench_events (
    op_id BIGINT PRIMARY KEY,
    key_name TEXT NOT NULL,
    value_text TEXT NOT NULL,
    depends_on_op_id BIGINT
)
"""

_INSERT_SQL = """
INSERT INTO causal_bench_events (op_id, key_name, value_text, depends_on_op_id)
VALUES (%s, %s, %s, %s)
"""

_CHECK_DEP_SQL = "SELECT 1 FROM causal_bench_events WHERE op_id = %s"

_CLEAR_TABLE_SQL = "DELETE FROM causal_bench_events"


class PostgresWireAdapter(Adapter):
    """Base for any Postgres-wire-protocol system under test. Subclasses
    set `name` and may override `_extra_setup_sql` for engine-specific
    session settings (e.g. isolation level)."""
    name = "postgres-wire-base"
    _extra_setup_sql = ()

    def __init__(self, dsn=None):
        self.dsn = dsn
        self._psycopg2 = None
        self._local = threading.local()
        self._lock = threading.Lock()
        self._seq = None
        self._all_conns = []  # every per-thread connection opened, for teardown

    def setup(self, regions):
        if not self.dsn:
            raise AdapterUnavailable(
                f"{self.name}: no DSN configured - pass a real "
                f"postgres-wire connection string (see "
                f"docs/benchmark-harness-spec.md's runbook)")
        try:
            import psycopg2  # optional dependency, not in this repo's stdlib-only core
        except ImportError as exc:
            raise AdapterUnavailable(
                f"{self.name}: psycopg2 is not installed in this "
                f"environment (pip install psycopg2-binary)") from exc
        self._psycopg2 = psycopg2
        try:
            conn = self._connect()
        except Exception as exc:  # noqa: BLE001 - any connection failure is AdapterUnavailable
            raise AdapterUnavailable(
                f"{self.name}: could not connect to {self.dsn!r}: {exc}") from exc
        try:
            with conn.cursor() as cur:
                for stmt in (_CREATE_TABLE_SQL, *self._extra_setup_sql, _CLEAR_TABLE_SQL):
                    cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        self._seq = itertools.count()

    def _connect(self):
        conn = self._psycopg2.connect(self.dsn)
        conn.autocommit = False
        return conn

    def _thread_conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
            with self._lock:
                self._all_conns.append(conn)
        return conn

    def apply_op(self, op):
        conn = self._thread_conn()
        dep_ids = op.get("depends_on", [])
        dep_id = dep_ids[0] if dep_ids else None
        t0 = time.perf_counter()
        try:
            with conn.cursor() as cur:
                if dep_id is not None:
                    cur.execute(_CHECK_DEP_SQL, (dep_id,))
                    if cur.fetchone() is None:
                        conn.rollback()
                        return OpResult(op["op_id"], False, None,
                                        int((time.perf_counter() - t0) * 1e9),
                                        rejected_reason="unknown_predecessor")
                cur.execute(_INSERT_SQL, (op["op_id"], op["key"], op["value"], dep_id))
            conn.commit()
        except Exception as exc:  # noqa: BLE001 - report as a rejected op, never crash the run
            conn.rollback()
            return OpResult(op["op_id"], False, None,
                            int((time.perf_counter() - t0) * 1e9),
                            rejected_reason=f"sql_error:{exc}")
        with self._lock:
            commit_seq = next(self._seq)
        latency_ns = int((time.perf_counter() - t0) * 1e9)
        return OpResult(op["op_id"], True, commit_seq, latency_ns)

    def teardown(self):
        with self._lock:
            conns, self._all_conns = self._all_conns, []
        for conn in conns:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup, never raise from teardown
                pass
