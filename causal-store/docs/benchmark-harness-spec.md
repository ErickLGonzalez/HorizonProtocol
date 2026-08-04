# Benchmark Harness Spec — causal-store vs. Best-in-Class Geo-Distributed Systems

**Program:** causal-store · **Benchmark:** D1-HARNESS · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none · **Empirical claim:** NONE

This implements the harness described in the uploaded design document
(`causalstoreBenchmarkHarnessDesign.md`). It is split, deliberately, into two
things that must never be confused:

1. **The harness itself** (`benchmark_harness/`) — workload generation,
   dependency-respecting scheduling, a correctness gate, percentile/report
   assembly, and the adapter contract. This is buildable, testable, and
   certified entirely in this repository (gate `D1-HARNESS`, this document).
2. **A genuine live, cross-region measurement** (the design doc's own "D1") —
   requires real cloud VMs, real inter-region network links, and (for the
   competitor comparison) real CockroachDB/YugabyteDB/Tiga clusters. **This
   has not happened yet.** Nothing in this repository claims it has. Section 8
   is the runbook for the live agent that will actually do it.

Confusing these two would repeat exactly the mistake this program corrected
once already (`docs/distributed-system-design.md`'s live-H8-run overclaim,
before the genuine H8-LIVE Azure capture existed) — see the honest-scoping
section below and the certificate's own `benchmark_id: "D1-HARNESS"` (never
`"D1"`) for how this is prevented structurally, not just by prose.

---

## 1. What this is and is not (per the design doc, section 0)

- **Is:** a harness that replays one deterministic, ground-truth-labeled trace
  through any number of adapters and reports latency/throughput curves plus a
  correctness verdict, swept across a contention ratio.
- **Is not:** a benchmark against proprietary exchange matching engines
  (inaccessible). The comparison set is open, installable systems.
- **Is not (yet):** a full-database comparison, or a live cross-region
  measurement. causal-store D0 is an ordering/commit engine without
  durability/replication/fault-tolerance, and every number in this repository
  so far is either LOCAL_LOOPBACK (this document) or the D0 benchmark's own
  MODELED estimate (`causal-store/bench/geo_workload.py`) — neither is a
  measured wide-area result.

## 2. Architecture

```
causal-store/benchmark_harness/
  __init__.py
  topology_probe.py     # LIVE inter-region RTT probe (quarantined) + local_topology() stand-in
  workload_gen.py        # neutral trace with a physically-grounded ground-truth dependency graph
  driver.py               # dependency-respecting closed-/open-loop load driver
  collect.py               # percentile/throughput aggregation (reporting only)
  verify_order.py           # the correctness gate (H4)
  report.py                 # curve assembly + VOID-point flagging
  adapters/
    base.py                    # the Adapter/OpResult/AdapterUnavailable contract
    causalstore_adapter.py      # trace -> causal-store write()
    baseline_adapter.py          # trace -> total-order serializer (the "every write coordinates" floor)
    sql_common.py                 # shared Postgres-wire plumbing for Cockroach/Yugabyte
    cockroach_adapter.py           # trace -> CockroachDB (untested in this build - see section 6)
    yugabyte_adapter.py             # trace -> YugabyteDB (untested in this build - see section 6)
    tiga_adapter.py                  # always AdapterUnavailable - no buildable client (design doc section 1)
causal-store/scripts/run_harness_local.py   # runs gates H-A..H-F + a LOCAL_LOOPBACK sweep; emits the certificate
causal-store/tests/test_h0{a..f}_*.py        # the gates
```

Diverges from the design doc's own tree (`bench/topology_probe.py`, etc.) only
in namespacing: this repo already has `causal-store/bench/geo_workload.py` (the
D0 MODELED micro-benchmark), so the new harness lives in its own
`benchmark_harness/` package to keep the two clearly distinct in imports,
certificates, and prose.

### 2.1 The ground-truth dependency graph (design doc section 3.2)

The design doc requires contention to be "physically meaningful, not
synthetic." `workload_gen.py` operationalizes this directly with the SAME
exact kernel primitive causal-store itself uses (`min_light_time_ns`, vendored
in `causalstore/geometry.py`): when a write targets a key another recent write
touched, the generator checks whether enough logical time elapsed for a signal
to have crossed the two writes' origin regions.

- **Not enough time elapsed** → the pair is recorded as genuinely
  **concurrent** (`concurrent_pairs`, no dependency edge) — a correct system
  may retain both, in either order; that is not a violation.
- **Enough time elapsed** → the pair is recorded as a genuine **dependency**
  (`depends_on`) — a real read-modify-write the workload is explicitly
  constructing, which every system under test MUST order correctly.

This directly implements the design doc's two stated mechanisms (section 3.2)
as one physical test rather than two independently-tuned parameters, and
reuses causal-store's own admissibility physics for the benchmark's ground
truth, which is the point: the harness's notion of "real dependency" is
grounded in the same physics causal-store's `GeometricOrdering` uses, not an
arbitrary synthetic rule.

### 2.2 The adapter contract and `commit_seq`

Every adapter reports `commit_seq`: a per-adapter, strictly increasing integer
assigned **after** an op's commit genuinely succeeds, reflecting that
adapter's own client-observed commit order. `driver.py` guarantees a dependent
op is never issued before its declared predecessor's result is already known
(mirroring how a real client can't formulate a read-modify-write before it has
the read result) — which means `commit_seq`'s precision requirement is modest:
a simple local counter, assigned strictly after commit, is sufficient for
`verify_order.py`'s correctness check regardless of how any given backend
schedules transactions internally. `causalstore_adapter.py` and
`baseline_adapter.py` both use exactly this scheme; `sql_common.py` reuses it
for the Postgres-wire adapters rather than depending on either database's
internal HLC/commit-timestamp precision.

## 3. Correctness gate (H4)

`verify_order.py` checks exactly one thing: for every `depends_on` edge, did
the dependency's `commit_seq` come before the dependent's, in that system's own
order? **Nothing else is a violation** — two ops the generator flagged as
genuinely concurrent may commit in either order, or both be retained, without
that being incorrect (design doc section 4). A run with any violation is
reported `status: VOID_CORRECTNESS_VIOLATION` and its latency numbers are void
per H4: a fast wrong answer is not a result.

## 4. Gates (this repository's local, LOCAL_LOOPBACK certification)

- **H-A** — workload generator: deterministic for a fixed seed; the dependency
  graph never violates the physical light-time floor (checked directly,
  bidirectionally, not merely spot-checked).
- **H-B** — `verify_order.py` accepts a correctly-ordered dependency AND
  catches an injected violation (a gate that only ever passes is worthless).
- **H-C** — `driver.py` respects `depends_on` ordering under real thread
  concurrency, in both closed- and open-loop mode.
- **H-D** — `collect.py`'s percentile/throughput math on known distributions;
  `report.py` correctly flags a VOID point and never hides one in a curve.
- **H-E** — the adapter contract: causal-store and the baseline conform
  end-to-end with zero correctness violations; Cockroach/Yugabyte/Tiga report
  `AdapterUnavailable` loudly in this environment, never silently, never faked.
- **H-F** — the LIVE half of `topology_probe.py` (`probe_rtt`/`probe_topology`,
  real socket I/O) is never referenced outside its own module — the same
  quarantine discipline `horizon/capture.py` already applies, checked by AST
  inspection.

Then `run_harness_local.py` runs a `LOCAL_LOOPBACK` sweep (causal-store vs. the
total-order baseline, across the design doc's full contention sweep) and
requires **zero VOID points** before the certificate can read `PASS`.

## 5. Honest scoping — read before trusting any number from this build

- **`benchmark_id` is `"D1-HARNESS"`, never `"D1"`.** D1 (design doc section 8)
  is the live cross-region measurement; this repository has not run it.
- **Every run in this build uses `topology_probe.local_topology()`**: 0ns
  loopback "network," single in-process execution. This certifies the
  harness's own correctness, not any cross-region performance claim.
- **The total-order baseline's `coordination_rtt_ns=0` in this build.** Its
  latency numbers here are correctness-only (it always accepts, in strict
  order) — not a performance claim. A live run that supplies a REAL measured
  RTT (from `topology_probe.probe_rtt()` to a fixed leader region) turns this
  into a genuine wall-clock coordination cost, still not a full Raft/2PC
  implementation (no real leader election or log replication over the wire —
  see `baseline_adapter.py`'s docstring).
- **CockroachDB/YugabyteDB adapters are written, not validated.** This sandbox
  has neither `psycopg2` nor a running cluster. They are reference
  implementations per each system's documented client API, reporting
  `AdapterUnavailable` here — see section 6 before trusting their numbers in
  any future run.
- **Tiga has no adapter.** No stable public client library or packaged
  release exists (design doc section 1); `tiga_adapter.py` always reports
  unavailable, per the design doc's own instruction to report the gap rather
  than half-configure a competitor.

## 6. Before trusting Cockroach/Yugabyte numbers from a future run

Per the design doc's fair-play protocol (section 6), before any comparison
result is published:

1. Confirm `setup()` actually succeeds against a real cluster with a real DSN
   (`AdapterUnavailable` must not fire).
2. Confirm the schema (`sql_common._CREATE_TABLE_SQL`) and the chosen isolation
   level are documented in the run's report — tune each system to its
   documented best practice (replication factor, locality-aware placement).
3. If causal-store's guarantee is weaker than the SQL system's default
   (serializable), either configure the SQL system to a comparable level and
   say so, or show both numbers (design doc section 6, point 2).
4. Re-run gate H-E against the real cluster before trusting the full sweep.

## 7. Registered falsifiers (design doc section 9, H1–H4)

- **H1:** at low contention (≤0.1), causal-store's p99 commit latency is
  materially lower than the competitors' because most writes skip wide-area
  consensus. *Falsified if the measured gap is small on a genuine live run.*
- **H2:** as contention → 1, causal-store converges toward the competitors.
  *Falsified if causal-store stays magically faster — a correctness bug, not
  a win.*
- **H3:** against Tiga (if ever built), causal-store is competitive at low
  contention. *Falsified if Tiga dominates across the board — an honest,
  publishable outcome, not a harness defect.*
- **H4:** causal-store's order never violates a ground-truth dependency. *If
  violated, the latency numbers are void* — this is the one falsifier this
  repository's local gate (H-B, H-E) already checks on every run.

## 8. Runbook: what the live agent actually does

This section is written for whoever (human or agent) runs the genuine D1 live
measurement — the counterpart to `docs/HANDOFF-H8-LIVE-Azure.md`, which this
mirrors.

### 8.1 Infrastructure

Reuse the H8-LIVE Azure region mapping (`data/h8_nodes.json`) where possible —
same non-negotiables as every prior live sprint: stdlib only in the trusted
path, exact integer lattice, do not modify `causalstore/geometry.py` or
`causalstore/ordering.py`, honesty labels survive (a live run is never
presented as cleaner than it is).

1. Provision ≥3 (5 recommended, per the design doc) Azure VMs across the
   `data/h8_nodes.json` regions. Update positions from Azure's published
   region coordinates if any region changes.
2. Install `chrony`; configure NTP, and PTP (`/dev/ptp_hyperv`) where the SKU
   supports it — same tier ladder as `docs/HANDOFF-H8-LIVE-Azure.md` section 2.
3. Open the chosen ports in each VM's NSG for: (a) the benchmark's own op
   traffic (causal-store adapter, baseline adapter — pick a port), and (b)
   `topology_probe`'s TCP probe port.
4. If comparing against CockroachDB/YugabyteDB: provision a cluster per each
   system's own multi-region deployment guide, with locality flags matching
   the actual Azure regions. Install `psycopg2` on the driver host.

### 8.2 Measure the topology (never skip this)

On one node (or from a driver host that can reach all regions), run:

```bash
python3 causal-store/benchmark_harness/topology_probe.py \
    --endpoint us-east-1=<ip>:9800 --endpoint us-west-2=<ip>:9800 \
    --endpoint eu-west-1=<ip>:9800 --rounds 10
```

Record the output JSON (`mode: "LIVE_PROBE"`) — this is the real RTT matrix
every result must be reported alongside (design doc section 2's fairness
rule).

### 8.3 Run the sweep

For causal-store, build `region_clocks` from the real surveyed positions and
each node's *measured* `u_ns` (from `chronyc tracking`, same convention as
`scripts/live_orchestrate.py`) — do not use a nominal tier value. Extend
`run_harness_local.py`'s pattern (or write a `run_harness_live.py` companion)
to:

1. Call `topology_probe.probe_topology()` for the real matrix (section 8.2).
2. For each `contention_ratio` in `workload_gen.DEFAULT_CONTENTION_SWEEP`,
   generate the trace with the REAL surveyed positions.
3. Run `driver.run()` against each adapter — causal-store and the baseline
   first (design doc section 10, phase 2), then Cockroach/Yugabyte/Tiga once
   available (phase 3) — with the adapter's connection actually reaching the
   remote nodes over the real network this time.
4. Run `verify_order.verify()` per point; abort the report for any VOID point
   per H4, exactly as the local gate does.
5. Emit the report with `benchmark_id: "D1"` (now genuinely earned) and
   `topology_probe`'s real `LIVE_PROBE` result attached — never `D1-HARNESS`,
   which is reserved for this local, loopback certification.

### 8.4 Interpreting the result

- **Low contention, causal-store faster: the headline**, IF it holds under
  real network jitter — the whole point of running this for real rather than
  trusting the D0 MODELED estimate.
- **Contention → 1, causal-store converges to the baseline: expected and
  correct** (H2) — do not treat this as a regression.
- **A correctness violation (H4) at any contention point voids that point's
  timing** — investigate before reporting, exactly as `docs/HANDOFF-H8-LIVE-
  Azure.md` treats an honest REJECTED receipt as a signal to investigate
  clock/position data, not the gate.

### 8.5 Deliverables

1. The real `LIVE_PROBE` topology JSON (section 8.2).
2. A live sweep report with `benchmark_id: "D1"`, covering at minimum
   causal-store vs. the baseline across the full contention sweep, plus
   whichever competitors were reachable (report exactly which weren't, and
   why — never silently omit one).
3. A short `docs/d1-live-report.md` (mirroring `docs/h8-live-report.md`)
   recording: regions used, the real RTT matrix, per-point latency curves,
   the correctness verdict per point, and an honest limits paragraph.
4. **Zero changes** to `causalstore/geometry.py`, `causalstore/ordering.py`,
   `causalstore/store.py`, or `verify_order.py`'s correctness logic. Confirm
   the existing D0 and harness-local suites still pass unchanged.

### 8.6 Prohibited

- Do not label a `LOCAL_LOOPBACK` or `LIVE_PROBE`-less run `"D1"`.
- Do not tune `u_ns` below the measured clock uncertainty to force a faster
  result.
- Do not report a competitor as available if its `setup()` didn't genuinely
  succeed against a real cluster.
- Do not modify `verify_order.py`'s correctness check to make a result look
  cleaner — an honest VOID point is a finding, not a bug to suppress.
