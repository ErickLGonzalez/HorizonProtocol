"""Neutral trace generator with a physically-grounded ground-truth
dependency graph.  [SOUND core]

The design doc (section 3.2) requires contention to be "physically
meaningful, not synthetic": two same-key writes are either (a) genuinely
concurrent - close enough in time that no signal could have carried the
first write's result to the second write's origin before it was issued,
so a correct system may retain both, in either order, without that being
a violation - or (b) a genuine causal dependency, where the workload
explicitly builds a read-then-write chain, and every correct system MUST
order the dependency before the dependent write.

This generator operationalizes that single physical test directly, using
the SAME exact light-cone primitive causal-store itself is built on
(`min_light_time_ns`, vendored from `horizon.geometry` - see
`causalstore/geometry.py`): when a write targets a key another recent
write touched, check whether enough logical time has elapsed for a
signal to have crossed the two writes' origin regions. If not, the pair
is recorded as genuinely CONCURRENT (no dependency edge - a correct
system may commit both, in any order). If so, the pair is recorded as a
genuine DEPENDENCY (the later write's `depends_on` names the earlier
write's op_id) - a real read-modify-write the workload is explicitly
constructing, which every system under test MUST order correctly.

This is deliberately the same physical test causal-store's own
`GeometricOrdering` uses to decide `resolves()`/`before()` - the
benchmark's ground truth and the engine's own admissibility decision are
grounded in the same physics, on purpose. Nothing here is a synthetic
tolerance: `min_light_time_ns` is exact integer, same as elsewhere in
this program.
"""
from causalstore.geometry import min_light_time_ns

DEFAULT_CONTENTION_SWEEP = (0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0)


class _Rng:
    """A tiny deterministic PRNG so the trace generator has no dependency
    on the stdlib `random` module's exact algorithm staying stable across
    Python versions (LCG, fixed constants) - reproducibility across
    interpreter versions matters more here than statistical quality."""
    def __init__(self, seed):
        self.state = hash(seed) & 0xFFFFFFFFFFFFFFFF or 1

    def next_int(self, n):
        # xorshift64* - deterministic, fast, stdlib-free
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 7)
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        self.state = x & 0xFFFFFFFFFFFFFFFF
        return (x % n) if n > 0 else 0

    def choice(self, seq):
        return seq[self.next_int(len(seq))]


def generate_trace(regions, region_positions_nm, n_keys, n_ops,
                   contention_ratio, seed, recent_window=32,
                   time_step_range=(1, 1000)):
    """Generate a deterministic trace of `n_ops` write ops.

    `regions`: list of region names.
    `region_positions_nm`: {region_name: (x, y, z)} exact integer nm.
    `contention_ratio`: probability [0,1] that an op targets a key a
      recent op also touched (vs. a fresh, untouched key). This is the
      swept independent variable (see DEFAULT_CONTENTION_SWEEP).
    `recent_window`: how many of the most-recently-touched keys count as
      "recent" for the contention roll.

    Returns a list of op dicts:
      {"op_id": int, "type": "write", "key": str, "value": str,
       "origin_region": str, "t_logical_ns": int, "depends_on": [op_id,...]}
    plus a parallel "concurrent_pairs" list of (op_id, op_id) pairs the
    generator determined are genuinely concurrent same-key writes (no
    dependency edge, but flagged so a report can show how much of the
    contention was physically-concurrent vs. a real dependency chain).
    """
    if not (0.0 <= contention_ratio <= 1.0):
        raise ValueError(f"contention_ratio must be in [0,1], got {contention_ratio}")
    if n_ops <= 0 or n_keys <= 0:
        raise ValueError("n_ops and n_keys must be positive")
    missing = [r for r in regions if r not in region_positions_nm]
    if missing:
        raise ValueError(f"region_positions_nm missing entries for: {missing}")

    rng = _Rng(seed)
    trace = []
    concurrent_pairs = []
    last_writer_of_key = {}     # key -> op_id of the most recent write
    recent_keys = []            # bounded recency list, most-recent last
    t_ns = 0
    lo, hi = time_step_range

    for op_id in range(n_ops):
        t_ns += lo + rng.next_int(hi - lo + 1)
        origin_region = rng.choice(regions)

        contend = recent_keys and (rng.next_int(1_000_000) < int(contention_ratio * 1_000_000))
        if contend:
            key = rng.choice(recent_keys)
        else:
            key = f"k{rng.next_int(n_keys)}"

        depends_on = []
        pred_id = last_writer_of_key.get(key)
        if pred_id is not None:
            pred = trace[pred_id]
            required_ns = min_light_time_ns(region_positions_nm[pred["origin_region"]],
                                            region_positions_nm[origin_region])
            elapsed_ns = t_ns - pred["t_logical_ns"]
            if elapsed_ns >= required_ns:
                # enough logical time for a signal to have carried the
                # predecessor's result to this write's origin: a genuine
                # read-modify-write dependency.
                depends_on = [pred_id]
            else:
                # not enough time for any signal to cross that distance:
                # a genuinely concurrent same-key conflict, not a
                # dependency - both writes may legitimately be retained.
                concurrent_pairs.append((pred_id, op_id))

        op = {"op_id": op_id, "type": "write", "key": key,
              "value": f"v{op_id}", "origin_region": origin_region,
              "t_logical_ns": t_ns, "depends_on": depends_on}
        trace.append(op)
        last_writer_of_key[key] = op_id
        recent_keys.append(key)
        if len(recent_keys) > recent_window:
            recent_keys.pop(0)

    return {"trace": trace, "concurrent_pairs": concurrent_pairs,
            "regions": list(regions), "n_keys": n_keys,
            "contention_ratio": contention_ratio, "seed": seed}
