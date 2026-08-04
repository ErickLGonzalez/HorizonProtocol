"""H-C: the driver respects depends_on ordering at issuance time, under
concurrency, in both closed- and open-loop mode. [SOUND]"""
import threading
import time
import unittest

from benchmark_harness import driver
from benchmark_harness.adapters.base import Adapter, OpResult


class RecordingAdapter(Adapter):
    """Records the wall-clock order apply_op was actually called in, plus
    whether a dependency's result was already recorded when a dependent
    op arrived - the property the driver exists to guarantee."""
    name = "recording"

    def __init__(self):
        self.lock = threading.Lock()
        self.call_order = []
        self.dependency_violations = []
        self._completed = set()

    def apply_op(self, op):
        for dep in op.get("depends_on", []):
            with self.lock:
                if dep not in self._completed:
                    self.dependency_violations.append((op["op_id"], dep))
        time.sleep(0.001)  # widen the window so a race would actually show up
        with self.lock:
            self.call_order.append(op["op_id"])
            self._completed.add(op["op_id"])
        return OpResult(op["op_id"], True, commit_seq=len(self.call_order) - 1)


def chain_trace(n):
    """A strict dependency chain: op i depends on op i-1."""
    return [{"op_id": i, "depends_on": [i - 1] if i > 0 else []} for i in range(n)]


def independent_trace(n):
    return [{"op_id": i, "depends_on": []} for i in range(n)]


class SlowAdapter(Adapter):
    """Every op takes `work_s` to execute - deliberately slower than the
    open-loop `rate_per_s` schedule, so ops queue behind a single worker."""
    name = "slow"

    def __init__(self, work_s):
        self.work_s = work_s

    def apply_op(self, op):
        time.sleep(self.work_s)
        return OpResult(op["op_id"], True, commit_seq=op["op_id"])


class TestDriver(unittest.TestCase):
    def test_closed_loop_respects_a_dependency_chain_under_concurrency(self):
        a = RecordingAdapter()
        results = driver.run(a, chain_trace(20), mode="closed", concurrency=8)
        self.assertEqual(a.dependency_violations, [])
        self.assertEqual(a.call_order, list(range(20)))  # forced into strict order
        self.assertEqual(len(results), 20)

    def test_closed_loop_independent_ops_can_run_concurrently(self):
        a = RecordingAdapter()
        results = driver.run(a, independent_trace(20), mode="closed", concurrency=8)
        self.assertEqual(a.dependency_violations, [])
        self.assertEqual(len(results), 20)
        self.assertEqual({r.op_id for r in results}, set(range(20)))

    def test_open_loop_respects_dependencies_too(self):
        a = RecordingAdapter()
        results = driver.run(a, chain_trace(10), mode="open", concurrency=4,
                             rate_per_s=1000)
        self.assertEqual(a.dependency_violations, [])
        self.assertEqual(a.call_order, list(range(10)))
        self.assertEqual(len(results), 10)

    def test_open_loop_requires_rate(self):
        a = RecordingAdapter()
        with self.assertRaises(ValueError):
            driver.run(a, independent_trace(3), mode="open")

    def test_invalid_mode_rejected(self):
        a = RecordingAdapter()
        with self.assertRaises(ValueError):
            driver.run(a, independent_trace(3), mode="sideways")

    def test_results_returned_in_trace_order(self):
        a = RecordingAdapter()
        trace = independent_trace(15)
        results = driver.run(a, trace, mode="closed", concurrency=4)
        self.assertEqual([r.op_id for r in results], [op["op_id"] for op in trace])

    def test_open_loop_latency_includes_queueing_delay_under_saturation(self):
        # Regression for the fixed bug (see driver.py module erratum): the
        # latency clock used to start only after a worker dequeued the
        # op, hiding time spent waiting for a free worker. Single worker,
        # each op takes 30ms, scheduled at 200/s (5ms apart) - the driver
        # cannot possibly keep up, so ops queue up behind the one worker.
        work_s = 0.03
        rate_per_s = 200  # 5ms apart - far faster than the 30ms of work
        n = 6
        a = SlowAdapter(work_s)
        results = driver.run(a, independent_trace(n), mode="open",
                             concurrency=1, rate_per_s=rate_per_s)
        # the last op's true queueing wait is roughly (n-1)*work_s minus
        # the small scheduled offset - it must be well beyond a single
        # op's own work duration, or the queueing delay was not captured.
        last = results[-1]
        self.assertGreater(last.latency_ns, work_s * 1e9 * (n - 1) * 0.5,
                           "open-loop latency does not reflect queueing "
                           "delay under saturation")

    def test_closed_loop_latency_does_not_include_pre_issuance_time(self):
        # sanity check on the fix: closed-loop latency should be close to
        # the adapter's own work duration when there is no contention
        # (concurrency comfortably exceeds the trace size).
        work_s = 0.01
        a = SlowAdapter(work_s)
        results = driver.run(a, independent_trace(3), mode="closed", concurrency=8)
        for r in results:
            self.assertLess(r.latency_ns, work_s * 1e9 * 3)


if __name__ == "__main__":
    unittest.main()
