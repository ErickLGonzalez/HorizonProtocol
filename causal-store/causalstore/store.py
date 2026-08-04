"""L3 — the coordination-free event store (performance-first).  [SOUND core]

The central performance claim: a write that is spacelike-separated (concurrent)
from all current writes for its key CANNOT have been caused by them, so it
commits LOCALLY AND IMMEDIATELY — no consensus round trip. Only genuine causal
dependencies (a write superseding an earlier one) create ordering constraints,
and conflicts (concurrent writes to the same key) are RETAINED with provenance,
never silently dropped, so nothing a coordination-free commit produces is lost.

Persistence is behind an interface (StoreBackend). A minimal in-memory backend
ships for testing; a real database/memory layer plugs in via the same contract
WITHOUT the engine importing it.

(Erratum: an earlier version of `write()` classified a new write's relation to
the frontier by testing only "is the write after every frontier member?" and
"is the write concurrent with every frontier member?", falling through to the
"mixed" conflict-retention branch for anything else — including the case where
an EXISTING frontier member is causally after the new write. That direction was
never checked. A write carrying a stale/earlier vector clock (or an old
geometric timestamp) than an already-current value would fall into "mixed",
collect zero ancestors (nothing in the frontier is before it), and be appended
as a live CONFLICT candidate sitting alongside the true current value —
resurrecting a causally-superseded write as if it were still in play.
Concretely confirmed: write A (vc {n1:1}), write B superseding A (vc {n1:2}),
then write C with vc {n1:1} (identical to the already-superseded A) — `read()`
reported CONFLICT between B and C, though C is causally BEFORE B. Fixed:
`write()` now checks, before any other classification, whether any current
frontier member dominates (is causally after) the incoming write; if so the
write is REJECTED with witness, the same "reject, don't silently admit"
pattern already used for `supersedes_non_ancestor`.)
"""
import hashlib
import json


def event_id(payload, origin_node, clock):
    body = json.dumps({"p": payload, "o": origin_node, "c": clock},
                      sort_keys=True).encode()
    return hashlib.sha256(body).hexdigest()[:16]


class StoreBackend:
    """Persistence contract. Implement to back the store with anything."""
    def append(self, event): raise NotImplementedError
    def events_for_key(self, key): raise NotImplementedError
    def all_events(self): raise NotImplementedError


class InMemoryBackend(StoreBackend):
    """Minimal test backend. NOT the product; a real memory/DB layer replaces it."""
    def __init__(self):
        self._by_key = {}
        self._all = []
    def append(self, event):
        self._by_key.setdefault(event["key"], []).append(event)
        self._all.append(event)
    def events_for_key(self, key):
        return list(self._by_key.get(key, []))
    def all_events(self):
        return list(self._all)


class CommitResult:
    __slots__ = ("event_id", "mode", "coordinated", "verdict", "witness", "supersedes")
    def __init__(self, eid, mode, coordinated, verdict, witness=None, supersedes=()):
        self.event_id = eid
        self.mode = mode                # "coordination_free" | "causal_supersede" | "conflict_retained"
        self.coordinated = coordinated  # bool: did this require a coordination step?
        self.verdict = verdict
        self.witness = witness
        self.supersedes = list(supersedes)
    def as_dict(self):
        return {"event_id": self.event_id, "mode": self.mode,
                "coordinated": self.coordinated, "verdict": self.verdict,
                "supersedes": self.supersedes,
                **({"witness": self.witness} if self.witness else {})}


class CausalStore:
    def __init__(self, ordering, backend=None):
        self.ordering = ordering
        self.backend = backend or InMemoryBackend()
        self.stats = {"total": 0, "coordination_free": 0, "coordinated": 0}

    def write(self, key, value, origin_node, clock, supersedes=None):
        eid = event_id({"k": key, "v": value}, origin_node, clock)
        ev = {"event_id": eid, "key": key, "value": value,
              "origin_node": origin_node, "clock": clock,
              "supersedes": list(supersedes or [])}

        frontier = self._frontier(key)
        self.stats["total"] += 1

        # explicit supersession claims must be causally valid
        for pred in ev["supersedes"]:
            pe = self._find(pred)
            if pe is None:
                return CommitResult(eid, "rejected", False, "REJECTED",
                                    {"reason": "unknown_predecessor", "pred": pred})
            if not self.ordering.before(pe, ev):
                return CommitResult(eid, "rejected", False, "REJECTED",
                                    {"reason": "supersedes_non_ancestor",
                                     **self.ordering.witness(pe, ev)})

        # THE PERFORMANCE DECISION: relation to the current frontier
        if not frontier:
            self.backend.append(ev)
            self.stats["coordination_free"] += 1
            return CommitResult(eid, "coordination_free", False, "ADMITTED")

        # a write causally BEFORE an existing frontier member is stale: admitting
        # it would resurrect an already-superseded value as a live conflict
        # candidate (see module erratum). Reject before considering any other
        # relation to the frontier.
        dominators = [f for f in frontier if self.ordering.before(ev, f)]
        if dominators:
            return CommitResult(eid, "rejected", False, "REJECTED",
                                {"reason": "stale_write_dominated_by_existing_frontier",
                                 "dominating_event_ids": [f["event_id"] for f in dominators]})

        if all(self.ordering.before(f, ev) for f in frontier):
            # ev causally follows the whole frontier: clean supersede, no coordination
            ev["supersedes"] = list({*ev["supersedes"], *(f["event_id"] for f in frontier)})
            self.backend.append(ev)
            self.stats["coordination_free"] += 1
            return CommitResult(eid, "causal_supersede", False, "ADMITTED",
                                supersedes=ev["supersedes"])
        if all(self.ordering.concurrent(f, ev) for f in frontier):
            # spacelike to everything current: COMMIT FREE, retained as concurrent
            self.backend.append(ev)
            self.stats["coordination_free"] += 1
            return CommitResult(eid, "coordination_free", False, "ADMITTED")

        # mixed: some concurrent, some ancestor -> retain with provenance,
        # supersede only the ones it causally follows. Still no global consensus:
        # a single local decision using the exact order.
        anc = [f["event_id"] for f in frontier if self.ordering.before(f, ev)]
        ev["supersedes"] = list({*ev["supersedes"], *anc})
        self.backend.append(ev)
        self.stats["coordinated"] += 1
        return CommitResult(eid, "conflict_retained", True, "ADMITTED",
                            supersedes=ev["supersedes"])

    def read(self, key):
        frontier = self._frontier(key)
        if not frontier:
            return {"status": "EMPTY", "key": key}
        if len(frontier) == 1:
            f = frontier[0]
            return {"status": "RESOLVED", "key": key, "value": f["value"],
                    "event_id": f["event_id"], "origin": f["origin_node"]}
        return {"status": "CONFLICT", "key": key,
                "candidates": [{"event_id": f["event_id"], "value": f["value"],
                               "origin": f["origin_node"]} for f in frontier]}

    def _frontier(self, key):
        evs = self.backend.events_for_key(key)
        frontier = []
        for e in evs:
            superseded = any(e["event_id"] in o["supersedes"] for o in evs
                             if o["event_id"] != e["event_id"])
            if not superseded:
                frontier.append(e)
        return frontier

    def _find(self, eid):
        for e in self.backend.all_events():
            if e["event_id"] == eid:
                return e
        return None

    def coordination_free_rate(self):
        # REPORTING METRIC ONLY - not an ordering/security decision. The float
        # division here never touches an admissibility verdict (those are exact
        # integer, in ordering.py/geometry.py). Kept out of the trusted gate path.
        t = self.stats["total"]
        return (self.stats["coordination_free"] / t) if t else 0.0
