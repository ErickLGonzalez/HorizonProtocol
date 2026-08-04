"""Correctness gate: did the system's committed order respect every
ground-truth causal dependency the trace declared?  [SOUND core]

H4 (design doc section 9): a system's committed order must never violate
a real causal dependency. If it does, the accompanying latency numbers
are VOID - a fast wrong answer is not a result worth reporting, and this
module's verdict is the thing report.py checks before it will include a
run's timing at all.

This is the ONLY correctness property checked here - not whether two
genuinely CONCURRENT writes got serialized one way or the other (a
linearizable system may commit either order for two commutative/
independent writes; that is not a violation, see workload_gen.py's
docstring on why concurrent_pairs carry no dependency edge at all).
"""


def verify(trace, results_by_op_id):
    """`trace`: the op list from workload_gen.generate_trace()'s output.
    `results_by_op_id`: {op_id: OpResult}, as returned by driver.run()
    (call `{r.op_id: r for r in driver.run(...)}` to build this).

    Returns {"ok": bool, "checked_edges": int, "violations": [...]}.
    A violation records exactly which dependency was not honored and the
    two commit_seq values that prove it, so a failure is debuggable, not
    just a boolean.
    """
    violations = []
    checked = 0
    for op in trace:
        for dep_id in op.get("depends_on", []):
            checked += 1
            r_op = results_by_op_id.get(op["op_id"])
            r_dep = results_by_op_id.get(dep_id)
            if r_op is None or r_dep is None:
                violations.append({"op_id": op["op_id"], "depends_on": dep_id,
                                   "reason": "missing_result"})
                continue
            if not r_op.accepted or not r_dep.accepted:
                # nothing committed on one or both sides - no order to violate
                continue
            if r_op.commit_seq is None or r_dep.commit_seq is None:
                violations.append({"op_id": op["op_id"], "depends_on": dep_id,
                                   "reason": "missing_commit_seq"})
                continue
            if not (r_dep.commit_seq < r_op.commit_seq):
                violations.append({
                    "op_id": op["op_id"], "depends_on": dep_id,
                    "reason": "dependency_not_ordered_before",
                    "dependency_commit_seq": r_dep.commit_seq,
                    "dependent_commit_seq": r_op.commit_seq,
                })
    return {"ok": len(violations) == 0, "checked_edges": checked,
            "violations": violations}
