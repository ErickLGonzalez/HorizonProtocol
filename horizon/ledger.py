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
from .edge_claims import EdgeClaim, EdgeKind
from .geometry import causally_admissible, admissibility_witness
from .reachability_cache import build_adjacency, precedes_fast


class CausalLedger:
    def __init__(self):
        self.events = {}     # eid -> {"time_ns": int, "pos_nm": tuple}
        self.edges = set()   # admitted (a, b)
        self.rejections = [] # audit log of rejected edges with witnesses
        self.edge_claims = [] # CK2-05: typed EdgeClaim log, additive
        self._adjacency_cache = None  # lazily built; see precedes_fast()

    def add_event(self, eid: str, time_ns: int, pos_nm):
        if eid in self.events:
            raise ValueError(f"duplicate event id: {eid}")
        self.events[eid] = {"time_ns": int(time_ns),
                            "pos_nm": tuple(int(x) for x in pos_nm)}

    def add_edge(self, a: str, b: str) -> dict:
        """Admit (or reject) the edge on physical admissibility ALONE.

        CK2-05: an admitted edge only proves an influence was geometrically
        POSSIBLE (`EdgeKind.PHYSICAL_ADMISSIBILITY`) -- it is never, by
        itself, evidence that a real dependency was observed. A caller that
        also wants to assert an actual dependency must separately call
        `add_dependency_claim` with its own evidence; this method never
        upgrades one claim into the other.
        """
        ea, eb = self.events[a], self.events[b]
        strictly_later = eb["time_ns"] > ea["time_ns"]
        admissible = strictly_later and causally_admissible(
            ea["time_ns"], ea["pos_nm"], eb["time_ns"], eb["pos_nm"])
        w = admissibility_witness(ea["time_ns"], ea["pos_nm"],
                                  eb["time_ns"], eb["pos_nm"])
        w["strictly_later"] = strictly_later
        if admissible:
            is_new = (a, b) not in self.edges
            self.edges.add((a, b))
            if is_new:
                # Only mint a NEW claim the first time this edge is admitted
                # -- add_edge(a, b) retried on an already-admitted pair is a
                # no-op for `self.edges` (a set) and must be a no-op for
                # `edge_claims` too, or a retry would keep appending
                # identical physical_admissibility claims and break the
                # one-to-one correspondence with admitted edges.
                self._adjacency_cache = None  # invalidate: precedes_fast() rebuilds lazily
                # `asserted_at` ties this claim to the exact geometric facts
                # that produced it (deterministic, no wall-clock dependency)
                # rather than a separate, unmodeled assertion timestamp.
                self.edge_claims.append(EdgeClaim(
                    from_event=a, to_event=b, kind=EdgeKind.PHYSICAL_ADMISSIBILITY,
                    asserted_by="horizon.geometry.causally_admissible",
                    asserted_at=str(eb["time_ns"]),
                ))
            return {"edge": [a, b], "verdict": "ADMITTED", "witness": w}
        rec = {"edge": [a, b], "verdict": "REJECTED", "witness": w}
        self.rejections.append(rec)
        return rec

    def add_dependency_claim(self, a: str, b: str, kind: str, asserted_by: str,
                              asserted_at: str, evidence_refs=None) -> EdgeClaim:
        """Explicitly assert a dependency-type claim (declared/observed/
        attested) between two known events. Distinct from `add_edge`:
        physical admissibility is never a substitute for this call, and
        this call never checks or requires physical admissibility either --
        the two claims are evidence for different questions ("was it
        possible" vs. "did it happen") and are recorded independently."""
        if a not in self.events or b not in self.events:
            raise KeyError("both events must already be recorded via add_event")
        if kind not in EdgeKind.DEPENDENCY_KINDS:
            raise ValueError(
                f"add_dependency_claim expects a dependency kind "
                f"({sorted(EdgeKind.DEPENDENCY_KINDS)}), got {kind!r}"
            )
        claim = EdgeClaim(
            from_event=a, to_event=b, kind=kind, asserted_by=asserted_by,
            asserted_at=asserted_at, evidence_refs=evidence_refs,
        )
        self.edge_claims.append(claim)
        return claim

    def has_observed_dependency(self, a: str, b: str) -> bool:
        """True iff at least one dependency-type claim (declared, observed,
        or attested -- NOT bare physical admissibility) has been recorded
        for this exact (a, b) pair."""
        return any(
            c.from_event == a and c.to_event == b and c.kind in EdgeKind.DEPENDENCY_KINDS
            for c in self.edge_claims
        )

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
