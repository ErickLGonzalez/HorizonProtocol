"""Adapter: neutral trace -> YugabyteDB (YSQL) transactions.  [HEURISTIC -
external system, outside the trusted/exact path by design]

Written per YugabyteDB's documented Postgres-wire (YSQL) client API
(psycopg2), but NOT exercised against a live cluster in this build -
this sandbox has neither `psycopg2` nor a YugabyteDB cluster available
(see docs/benchmark-harness-spec.md's honest-scoping section and
cockroach_adapter.py's module docstring, which this mirrors).

Config knobs a real run should set explicitly (design doc section 6):
  - replication factor matching the region count under test
  - YSQL's tablet/placement configuration matching the actual node regions
  - the isolation level intended for the comparison (YugabyteDB's
    SERIALIZABLE, or a documented weaker level - see design doc section
    6 point 2)
"""
from .sql_common import PostgresWireAdapter


class YugabyteAdapter(PostgresWireAdapter):
    name = "yugabytedb"
    default_port = 5433
