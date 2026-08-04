"""Adapter: the "every write coordinates" floor - a total-order
serializer.  [HEURISTIC coordination-cost stand-in, honestly labeled]

Models the one thing every write pays under a total-order protocol
(Raft/2PC): a single global sequence point every op must pass through,
one at a time. This is deliberately NOT a real Raft/2PC implementation
(no leader election, no log replication over the wire) - building one is
future work, not a prerequisite for the harness core (see design doc
section 10's own phased build sequence, step 3).

When a REAL measured round-trip time is supplied (`coordination_rtt_ns`,
e.g. from a live `topology_probe.probe_rtt()` result to a fixed leader
region), each op genuinely waits that long before committing - a real
wall-clock sleep for a real measured duration is not "modeling", but it
is still not a real consensus protocol's cost (no actual message
exchange happens). In LOCAL/loopback mode (`coordination_rtt_ns=0`, the
default) the wait is zero and the resulting latency numbers are
correctness-only, not a performance claim - see
docs/benchmark-harness-spec.md's honest-scoping section.

Always accepts (a total-order protocol never rejects for causal reasons -
it simply serializes everything), which is exactly why this adapter is
the design's "control": at contention_ratio=1 causal-store must converge
toward it (H2), never beat it, or that would indicate a correctness bug
rather than a win.
"""
import itertools
import threading
import time

from .base import Adapter, OpResult


class TotalOrderBaselineAdapter(Adapter):
    name = "total-order-baseline"

    def __init__(self, coordination_rtt_ns=0):
        self.coordination_rtt_ns = coordination_rtt_ns
        self._lock = threading.Lock()
        self._seq = None

    def setup(self, regions):
        self._seq = itertools.count()

    def apply_op(self, op):
        t0 = time.perf_counter()
        with self._lock:
            if self.coordination_rtt_ns:
                time.sleep(self.coordination_rtt_ns / 1e9)
            commit_seq = next(self._seq)
        latency_ns = int((time.perf_counter() - t0) * 1e9)
        return OpResult(op["op_id"], True, commit_seq, latency_ns)
