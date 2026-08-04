"""causal-store — a coordination-free geo-distributed event store.

Performance-first: two writes that the light cone proves causally independent
(spacelike-separated) cannot have caused each other, so they commit WITHOUT
coordination. Only genuine causal dependencies need ordering. This targets the
geo-distributed transaction bottleneck where wide-area round trips for consensus
dominate latency.

The engine is built on ONE narrow, documented contract (the L2 ordering
interface) so that:
  * a geometric ordering (exact light-cone, HorizonProtocol kernel) drives it
    where clock/distance let the geometry resolve;
  * a logical ordering (vector clocks) is the always-available fallback;
  * a future memory/database layer plugs in via the same contract WITHOUT the
    engine depending on it (a minimal in-memory store ships here for testing).

No external dependencies. Exact integer arithmetic on every ordering decision.
"""
__version__ = "0.1.0"
BENCHMARK_ID = "D0"
