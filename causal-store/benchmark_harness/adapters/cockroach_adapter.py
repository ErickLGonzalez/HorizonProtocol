"""Adapter: neutral trace -> CockroachDB transactions.  [HEURISTIC -
external system, outside the trusted/exact path by design]

Written per CockroachDB's documented Postgres-wire client API
(psycopg2), but NOT exercised against a live cluster in this build -
this sandbox has neither `psycopg2` nor a CockroachDB cluster available
(see docs/benchmark-harness-spec.md's honest-scoping section). Before
this adapter's numbers are trusted for a real comparison, the live agent
must validate it against a real cluster per the design doc's fair-play
protocol (section 6): confirm the schema, isolation level, and that
`setup()` succeeds against a real DSN before running the full sweep.

Config knobs a real run should set explicitly (design doc section 6,
"tune every competitor to its documented best practice"):
  - appropriate replication factor for the region count under test
  - locality-aware placement matching the actual node regions
  - the isolation level intended for the comparison (CockroachDB's
    default SERIALIZABLE, or a documented weaker level if compared
    against causal-store's weaker guarantee - see design doc section 6
    point 2 on showing both numbers when guarantees differ)
Document whichever choice is made in the run's certificate/report.
"""
from .sql_common import PostgresWireAdapter


class CockroachAdapter(PostgresWireAdapter):
    name = "cockroachdb"
    default_port = 26257
