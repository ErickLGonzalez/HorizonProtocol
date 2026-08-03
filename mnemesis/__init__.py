"""MnemesisOS <-> HorizonProtocol convergence.

A provenance-aware, causally-ordered memory substrate built directly on the
HorizonProtocol causal ledger. The thesis (docs/mnemesis-convergence.md):

  A causal ledger IS a multi-observer memory. Writes are events; the merge
  admissibility gate IS the light-cone gate; concurrent writes are stored
  unordered and resolved WITH PROVENANCE, never silently overwritten.

Two clocks are supported on one interface:
  * GEOMETRIC observers carry (time_ns, pos_nm) and order by the exact
    light-cone gate (reuses `horizon.geometry`, unmodified).
  * LOGICAL observers carry a vector clock and order by the standard
    happens-before partial order, for the case where geometry is unavailable.
Both yield the same three-way relation: BEFORE / AFTER / CONCURRENT.
"""
__version__ = "0.1.0"
BENCHMARK_ID = "MNX1"
