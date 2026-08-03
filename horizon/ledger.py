"""The causal ledger: a DAG whose edges must pass the exact light-cone gate.

Events are recorded with (payload_hash, time_ns, pos_nm). A claimed
dependency edge A -> B is ADMITTED iff B lies in the closed future light
cone of A (strictly later in time), and REJECTED otherwise with the exact
integer witness. Events with no admissible ordering either way are
CONCURRENT and are stored unordered - the ledger never fabricates an
order the geometry does not certify.
"""
from .geometry import causally_admissible, admissibility_witness


class CausalLedger:
    def __init__(self):
        self.events = {}     # eid -> {"time_ns": int, "pos_nm": tuple}
        self.edges = set()   # admitted (a, b)
        self.rejections = [] # audit log of rejected edges with witnesses

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
            return {"edge": [a, b], "verdict": "ADMITTED", "witness": w}
        rec = {"edge": [a, b], "verdict": "REJECTED", "witness": w}
        self.rejections.append(rec)
        return rec

    def precedes(self, a: str, b: str) -> bool:
        """Reachability in the admitted DAG (transitive closure query)."""
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

    def concurrent(self, a: str, b: str) -> bool:
        """Geometrically unordered: neither cone contains the other event."""
        ea, eb = self.events[a], self.events[b]
        ab = causally_admissible(ea["time_ns"], ea["pos_nm"],
                                 eb["time_ns"], eb["pos_nm"])
        ba = causally_admissible(eb["time_ns"], eb["pos_nm"],
                                 ea["time_ns"], ea["pos_nm"])
        return (not ab) and (not ba)
