"""Vector clocks: the logical fallback partial order.  [SOUND]

happens-before:  a < b  iff  a <= b and NOT b <= a (standard partial-order
strictness via antisymmetry - never a raw `a != b` dict comparison: two
clocks that differ only by an explicit zero-valued component the other
omits, e.g. `{"n1": 1}` and `{"n1": 1, "n2": 0}`, are the SAME logical
instant under `leq`'s zero-padding, and must compare equal, not
"before" each other in both directions - see mnemesis/memory.py's
CausalMemory.put, which would otherwise accept a write superseding
another at the same logical instant).
concurrent:      neither a < b nor b < a (also covers the "equal under
zero-padding but different dict representation" case above).
This is the same partial-order structure as the causal ledger, for contexts
where physical (time, position) coordinates are unavailable.
"""


def leq(a: dict, b: dict) -> bool:
    keys = set(a) | set(b)
    return all(a.get(k, 0) <= b.get(k, 0) for k in keys)


def happens_before(a: dict, b: dict) -> bool:
    return leq(a, b) and not leq(b, a)


def concurrent(a: dict, b: dict) -> bool:
    return not happens_before(a, b) and not happens_before(b, a)


def merge(a: dict, b: dict) -> dict:
    keys = set(a) | set(b)
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in keys}
