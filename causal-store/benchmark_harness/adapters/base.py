"""The adapter contract every system-under-test implements.  [SOUND core]

An adapter's ONLY job is to translate one neutral trace op into a call
against its target system and report what actually happened, in the
uniform `OpResult` shape `verify_order.py`, `collect.py`, and `report.py`
all understand. The neutral trace and this contract are the fairness
guarantee (see docs/benchmark-harness-spec.md section on fair-play): every
system replays the SAME trace through the SAME contract, so differences
in the results are the systems', not the harness's.

`commit_seq` is the one field every adapter MUST assign consistently: a
per-adapter, strictly increasing integer reflecting the order THIS
system actually made each accepted op visible (its "client-observed
commit order") - for causal-store, the backend's own append order; for a
SQL system, e.g. the commit order of its own commit-timestamp/LSN. This
is deliberately NOT wall-clock time (adapters may commit concurrently)
and NOT trace order (a fast concurrent system may commit op 5 before op
2) - it is the one thing `verify_order.py` needs to check a dependency:
"did the predecessor become visible, in this system's own order, before
the dependent?"

A missing/unavailable target system is a loud, named failure
(`AdapterUnavailable`), never a silently-skipped or faked result - see
the design doc's own rule: "a badly-tuned [or missing] competitor is a
false result."
"""


class AdapterUnavailable(Exception):
    """Raised by setup() when this adapter's target system isn't
    installed, buildable, or reachable in the current environment. The
    harness reports this as a named gap, never as a fabricated result."""


class OpResult:
    __slots__ = ("op_id", "accepted", "commit_seq", "latency_ns", "rejected_reason")

    def __init__(self, op_id, accepted, commit_seq=None, latency_ns=None,
                rejected_reason=None):
        self.op_id = op_id
        self.accepted = accepted          # bool: did the system commit this op
        self.commit_seq = commit_seq      # int or None: this system's own commit order
        self.latency_ns = latency_ns      # int or None: client-observed commit latency
        self.rejected_reason = rejected_reason

    def as_dict(self):
        return {"op_id": self.op_id, "accepted": self.accepted,
                "commit_seq": self.commit_seq, "latency_ns": self.latency_ns,
                "rejected_reason": self.rejected_reason}


class Adapter:
    """Subclass and implement apply_op(). setup()/teardown() are hooks for
    adapters that need a live connection, process, or cluster."""
    name = "base"

    def setup(self, regions):
        """Called once before the trace runs, with the list of region
        names the trace uses. Raise AdapterUnavailable if this adapter's
        target system cannot be used in the current environment."""

    def apply_op(self, op):
        """op is one neutral trace dict (see workload_gen.py). Must
        return an OpResult. May be called concurrently from multiple
        threads (see driver.py) - implementations must be thread-safe."""
        raise NotImplementedError

    def teardown(self):
        """Called once after the trace run completes, success or not."""

    def diagnostics(self):
        """Optional, adapter-specific diagnostic metrics that explain WHY
        the latency curve looks as it does (design doc section 4: e.g.
        causal-store's own coordination-free rate) - NOT part of the
        fair cross-system comparison, so report.py includes this
        per-system rather than trying to normalize it across adapters.
        Default: no diagnostics."""
        return {}
