"""The causal ledger: a DAG whose edges must pass the exact light-cone gate.

Events are recorded with (payload_hash, time_ns, pos_nm). A claimed
dependency edge A -> B is ADMITTED iff B lies in the closed future light
cone of A (strictly later in time), and REJECTED otherwise with the exact
integer witness. Events with no admissible ordering either way are
CONCURRENT and are stored unordered - the ledger never fabricates an
order the geometry does not certify.

`precedes()` is the reference reachability query (DFS rescanning the full
edge set per visited node, O(E) per call). `precedes_fast()` is an additive,
opt-in adjacency-indexed BFS (`horizon.reachability_cache`, O(V+E)) for
callers on the performance-sensitive path at scale; it never changes what
counts as an admitted edge, only how quickly reachability over the ALREADY-
admitted edges is queried, and is cross-checked against `precedes()` in
`tests/test_reachability_cache.py`. The adjacency index is built lazily and
invalidated whenever a new edge is admitted.
"""
from .geometry import causally_admissible, admissibility_witness
from .reachability_cache import build_adjacency, precedes_fast


class CausalLedger:
    def __init__(self):
        self.events = {}     # eid -> {"time_ns": int, "pos_nm": tuple}
        self.edges = set()   # admitted (a, b)
        self.rejections = [] # audit log of rejected edges with witnesses
        self._adjacency_cache = None  # lazily built; see precedes_fast()

    def add_event(self, eid: str, time_ns: int, pos_nm):
        if eid in self.events:
            raise ValueError(f"duplicate event id: {eid}")
        self.events[eid] = {"time_ns": int(time_ns),
                            "pos_nm": tuple(int(x) for x in pos_nm)}

    def add_edge(self, a: str, b: str) -> dict:
        ea, eb = self.events[a], self.events[b]
        strictly_later = eb["time_ns"] > ea["time_ns"]
        admissible = strictly_later and causally_admissible(
            ea["time_ns"], ea["pos_nm"], eb["time_ns"], eb["pos_nm"])
        w = admissibility_witness(ea["time_ns"], ea["pos_nm"],
                                  eb["time_ns"], eb["pos_nm"])
        w["strictly_later"] = strictly_later
        if admissible:
            self.edges.add((a, b))
            self._adjacency_cache = None  # invalidate: precedes_fast() rebuilds lazily
            return {"edge": [a, b], "verdict": "ADMITTED", "witness": w}
        rec = {"edge": [a, b], "verdict": "REJECTED", "witness": w}
        self.rejections.append(rec)
        return rec

    def precedes(self, a: str, b: str) -> bool:
        """Reachability in the admitted DAG (transitive closure query).
        Reference implementation - see precedes_fast() for the indexed,
        asymptotically faster equivalent."""
        seen, stack = set(), [a]
        while stack:
            x = stack.pop()
            for (u, v) in self.edges:
                if u == x and v not in seen:
                    if v == b:
                        return True
                    seen.add(v)
                    stack.append(v)
        return False

    def precedes_fast(self, a: str, b: str) -> bool:
        """Same query as precedes(), via a lazily-built, edge-invalidated
        adjacency index (horizon.reachability_cache) - O(V+E) instead of
        O(E) per visited node. Never changes what counts as admitted, only
        how quickly reachability over already-admitted edges is answered."""
        if self._adjacency_cache is None:
            self._adjacency_cache = build_adjacency(self.edges)
        return precedes_fast(self._adjacency_cache, a, b)

    def concurrent(self, a: str, b: str) -> bool:
        """Geometrically unordered: neither cone contains the other event."""
        ea, eb = self.events[a], self.events[b]
        ab = causally_admissible(ea["time_ns"], ea["pos_nm"],
                                 eb["time_ns"], eb["pos_nm"])
        ba = causally_admissible(eb["time_ns"], eb["pos_nm"],
                                 ea["time_ns"], ea["pos_nm"])
        return (not ab) and (not ba)
