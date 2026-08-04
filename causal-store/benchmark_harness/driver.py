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

(Erratum: an earlier version started each op's latency clock INSIDE the
worker task, after `ThreadPoolExecutor` had already dequeued it - so under
saturation (`rate_per_s` exceeding the adapter's capacity, or a busy
closed-loop pool), the time an op spent WAITING for a free worker was
invisible to the reported latency. That is exactly the queueing delay
open-loop mode exists to expose (module docstring: "exposing queueing
under load") - omitting it made saturation look substantially faster than
a real client would experience. Fixed: the latency clock now starts at
`issued_at` - the scheduled target time for open-loop, or the moment the
driver loop reaches the op for closed-loop - captured BEFORE
`pool.submit()`, not inside the worker. The driver's own end-to-end
measurement (issuance to result, including any dependency wait and any
queueing wait) is now authoritative and always overwrites whatever an
adapter set internally, since only the driver can see the queueing delay
by construction.)
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

    def task(op, issued_at):
        for dep in op.get("depends_on", []):
            dep_future = futures.get(dep)
            if dep_future is not None:
                dep_future.result()  # block until the predecessor committed
        result = adapter.apply_op(op)
        result.latency_ns = int((time.perf_counter() - issued_at) * 1e9)
        with results_lock:
            results[op["op_id"]] = result
        return result

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        if mode == "closed":
            for op in trace:
                issued_at = time.perf_counter()
                futures[op["op_id"]] = pool.submit(task, op, issued_at)
        else:  # open-loop: issue on a fixed schedule, don't wait for completion
            interval_s = 1.0 / rate_per_s
            t_start = time.perf_counter()
            for i, op in enumerate(trace):
                target = t_start + i * interval_s
                delay = target - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                # the SCHEDULED time, not the (possibly later) actual
                # submit time - latency is measured from when the op was
                # supposed to be issued, the standard open-loop definition
                # that avoids "coordinated omission."
                futures[op["op_id"]] = pool.submit(task, op, target)

        for f in futures.values():
            f.result()  # propagate any exception; wait for full completion

    return [results[op["op_id"]] for op in trace]
