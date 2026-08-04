# causal-store

**A coordination-free, geo-distributed event store.** Writes that the speed of
light proves causally independent commit without any consensus round trip — only
genuine causal dependencies serialize. Built for the geo-distributed latency
problem that dominates financial and other wide-area systems.

## The pitch, quantified
On a 5-region workload: **~85% of writes commit coordination-free**, a **modeled
~6.8x latency reduction** vs a total-order (Paxos/Raft/2PC) baseline — because
most writes to different keys are causally independent and skip the wide-area
round trip that total-order protocols pay on every write.

## Run
```
python3 causal-store/scripts/run_d0.py               # D0 gates + certificate; exits 0 iff green
python3 causal-store/bench/geo_workload.py           # the D0 benchmark, standalone (MODELED)
python3 causal-store/scripts/run_harness_local.py   # benchmark-harness gates + a LOCAL_LOOPBACK sweep
cd causal-store && python3 -m unittest discover tests -v
```

## How it works
- Events carry a physical clock (measured time, surveyed position, measured
  uncertainty) and/or a vector clock.
- The **light-cone ordering** (exact integer, machine-checked kernel) decides
  causal relations; two spacelike events are provably independent and commit free.
- Where clocks are too coarse for the distance, the **hybrid ordering** falls back
  to vector clocks — correctness always, physical certification where it resolves.
- Concurrent writes are **retained with provenance**, never dropped: coordination-
  freedom (fast) never loses data (safe).

## Design boundaries (honest)
- The advantage grows with distance; inside one datacenter geometry can't resolve
  and you fall back to logical ordering (no harm, no geometric gain).
- Coordination-free commit is correct for commutative/CRDT-safe ops or with
  conflict retention; non-commutative same-key ops still coordinate.
- Benchmark latency is MODELED, not measured on real links — a real deployment
  measures wide-area behavior.
- Fault tolerance, durability, and replication are future tracks; this is the
  ordering/commit engine.

## Interop (decoupled by design)
The engine depends only on two contracts: the **L2 ordering** interface
(`before/concurrent/witness`) and the **StoreBackend** interface
(`append/events_for_key/all_events`). A memory/database layer or a third-party
timing source plugs in without the engine importing it. A minimal in-memory
backend ships for testing. See `docs/d0-spec.md`.

## Integration note
Vendors the exact HorizonProtocol `geometry.py` kernel (machine-checked) rather
than importing `horizon.geometry` — deliberately and permanently, per
`docs/distributed-system-design.md` section 4.2's "shared by value, not by
coupling" principle: the engine must stay importable and correct even where
the `horizon` package isn't present. Test D0-F (`tests/test_d0f_geometry_hash.py`)
enforces that the vendored copy stays byte-identical to `horizon/geometry.py`,
so drift is caught without introducing a runtime dependency.

## Benchmark harness (D1-HARNESS)
`benchmark_harness/` implements the comparison harness against best-in-class
geo-distributed systems (CockroachDB, YugabyteDB, Tiga, and a self-run
total-order baseline) from `causalstoreBenchmarkHarnessDesign.md`: a neutral,
deterministic trace with a **physically-grounded ground-truth dependency
graph** (using the same exact `min_light_time_ns` kernel primitive
causal-store's own ordering uses) is replayed through any number of adapters,
and a correctness gate (`verify_order.py`) voids any run that violates a real
dependency — a fast wrong answer is never reported as a win.

**This repository certifies the harness itself, not a live cross-region
result.** Every run so far uses `topology_probe.local_topology()` (0ns
loopback); CockroachDB/YugabyteDB adapters are written per each system's
documented client API but have not been run against a real cluster in this
build (no `psycopg2`, no cluster, in this sandbox); Tiga has no buildable
client. `certificates/harness_certificate.json` is labeled `D1-HARNESS`,
never `D1`, so it can never be mistaken for the design doc's actual live
measurement. See `docs/benchmark-harness-spec.md` section 8 for the runbook a
live agent follows to produce a genuine `D1` result on real Azure
infrastructure (reusing the H8-LIVE region mapping).
