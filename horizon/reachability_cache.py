"""Additive O(V+E) reachability for the causal ledger.  [SOUND, PERF]

`scripts/bench.py` showed `CausalLedger.precedes()` is O(E) per call via a
DFS that rescans the full edge SET at every visited node, giving O(V*E)
worst case queried across the graph. This module adds an adjacency-indexed
BFS that does not modify the kernel or the ledger's admissibility gate - it
is a drop-in faster reachability query that returns identical answers,
cross-checked against `CausalLedger.precedes()` (the reference) in
`tests/test_reachability_cache.py`.
"""
from collections import defaultdict, deque


def build_adjacency(edges):
    adj = defaultdict(list)
    for (u, v) in edges:
        adj[u].append(v)
    return adj


def precedes_fast(adj, a, b):
    """BFS over the adjacency index; O(V+E) worst case, O(path) typical."""
    if a == b:
        return False
    seen = {a}
    q = deque([a])
    while q:
        x = q.popleft()
        for v in adj.get(x, ()):
            if v == b:
                return True
            if v not in seen:
                seen.add(v)
                q.append(v)
    return False
