"""int_vs_float — exact-integer vs floating-point light-cone gate comparison.

The claim under test is NOT "the integer gate is faster." It is the claim
`formal/kernel_proof.py`'s T1 already proves for the abstract predicate:
the exact-integer gate has zero rounding gap against the real light-cone
condition, so it is exactly correct and bit-identical everywhere, while any
floating-point implementation of the same predicate carries a tolerance
that is an attack surface, a source of cross-platform non-determinism, and
capable of flipping a security verdict near the cone. This package builds a
faithful (not strawman) floating-point control and measures that gap with
numbers - see docs/int-vs-float-results.md for the results and
`run_int_vs_float.py` for the three tests.

Nothing here modifies `horizon/geometry.py` (the frozen, machine-checked
kernel) or is imported by any verifier.
"""
