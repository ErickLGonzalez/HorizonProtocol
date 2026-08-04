"""Percentile and throughput aggregation over per-op results.
[REPORTING METRIC ONLY - not an ordering/admissibility decision, same
status as `causalstore.store.coordination_free_rate()`. Uses ordinary
float arithmetic throughout; deliberately outside the float-guard's
scope (see benchmark_harness/tests), since nothing here feeds back into
a gate verdict.]
"""


def _nearest_rank(sorted_vals, p):
    """Nearest-rank percentile (no interpolation): simple, standard, and
    defensible to a skeptical reader - not sensitive to a choice of
    interpolation scheme."""
    if not sorted_vals:
        return None
    n = len(sorted_vals)
    k = int(round((p / 100.0) * (n - 1)))
    k = max(0, min(n - 1, k))
    return sorted_vals[k]


def latency_percentiles(latencies_ns, percentiles=(50, 90, 99, 99.9, 100)):
    """Returns {p: value_ns} for each requested percentile (p=100 is max).
    Ignores None entries (ops with no recorded latency, e.g. rejected)."""
    vals = sorted(v for v in latencies_ns if v is not None)
    return {p: _nearest_rank(vals, p) for p in percentiles}


def median_iqr(values):
    """Returns (median, iqr) for reporting run-to-run spread across
    repetitions of the same configuration (design doc section 5:
    'each configuration runs N repetitions and reports median + IQR')."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None, None
    median = _nearest_rank(vals, 50)
    q1 = _nearest_rank(vals, 25)
    q3 = _nearest_rank(vals, 75)
    return median, (q3 - q1)


def throughput_per_sec(op_results, elapsed_s):
    """Committed ops per second over the run's wall-clock duration."""
    if elapsed_s <= 0:
        return 0.0
    accepted = sum(1 for r in op_results if r.accepted)
    return accepted / elapsed_s


def acceptance_rate(op_results):
    """Fraction of ops the system accepted at all (vs. REJECTED, e.g. a
    stale/non-ancestor supersede). Generic across every adapter."""
    if not op_results:
        return 0.0
    return sum(1 for r in op_results if r.accepted) / len(op_results)
