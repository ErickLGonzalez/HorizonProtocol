"""Vector clocks: the logical fallback partial order.  [SOUND]

happens-before:  a < b  iff  a[k] <= b[k] for all k and a != b.
concurrent:      neither a < b nor b < a.
This is the same partial-order structure as the causal ledger, for contexts
where physical (time, position) coordinates are unavailable.
"""


def leq(a: dict, b: dict) -> bool:
    keys = set(a) | set(b)
    return all(a.get(k, 0) <= b.get(k, 0) for k in keys)


def happens_before(a: dict, b: dict) -> bool:
    return a != b and leq(a, b)


def concurrent(a: dict, b: dict) -> bool:
    return not happens_before(a, b) and not happens_before(b, a)


def merge(a: dict, b: dict) -> dict:
    keys = set(a) | set(b)
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in keys}
