"""The load driver: replays a trace against one adapter, closed-loop or
open-loop, timestamping every op.  [SOUND core - timestamps and scheduling
only; makes no admissibility decision itself]

Both loop modes respect the trace's `depends_on` edges at ISSUANCE time:
an op is never handed to the adapter until every op it depends on has
already been applied and returned a result. This mirrors how a real
client actually behaves - it cannot formulate a read-modify-write before
it has the read result - and is what makes causal-store's `supersedes`
list (and any SQL adapter's read-then-write) meaningful rather than a
race. Ops with NO dependency may run fully concurrently.

- **Closed-loop** (`mode="closed"`): `concurrency` workers pull ready ops
  and issue them back-to-back; throughput is whatever the system
  sustains.
- **Open-loop** (`mode="open"`): ops are issued on a fixed schedule
  (`rate_per_s`) regardless of whether prior ops finished, exposing
  queueing under load - the design doc requires both because a
  closed-loop number alone hides saturation.

Uses only `concurrent.futures`/`threading`/`time` (stdlib). This driver
measures wall-clock latency as observed IN THIS PROCESS; when adapters
talk to real remote systems (a live run), that latency genuinely includes
the network - see docs/benchmark-harness-spec.md.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor


def run(adapter, trace, mode="closed", concurrency=8, rate_per_s=None):
    """Replay `trace` (a list of op dicts, see workload_gen.py) through
    `adapter.apply_op`. Returns {op_id: OpResult} for every op.

    `mode="open"` requires `rate_per_s`.
    """
    if mode not in ("closed", "open"):
        raise ValueError(f"mode must be 'closed' or 'open', got {mode!r}")
    if mode == "open" and not rate_per_s:
        raise ValueError("open-loop mode requires rate_per_s > 0")

    futures = {}
    results = {}
    results_lock = threading.Lock()

    def task(op):
        for dep in op.get("depends_on", []):
            dep_future = futures.get(dep)
            if dep_future is not None:
                dep_future.result()  # block until the predecessor committed
        t0 = time.perf_counter()
        result = adapter.apply_op(op)
        if result.latency_ns is None:
            result.latency_ns = int((time.perf_counter() - t0) * 1e9)
        with results_lock:
            results[op["op_id"]] = result
        return result

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        if mode == "closed":
            for op in trace:
                futures[op["op_id"]] = pool.submit(task, op)
        else:  # open-loop: issue on a fixed schedule, don't wait for completion
            interval_s = 1.0 / rate_per_s
            t_start = time.perf_counter()
            for i, op in enumerate(trace):
                target = t_start + i * interval_s
                delay = target - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                futures[op["op_id"]] = pool.submit(task, op)

        for f in futures.values():
            f.result()  # propagate any exception; wait for full completion

    return [results[op["op_id"]] for op in trace]
