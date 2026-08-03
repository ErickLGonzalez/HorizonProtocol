"""Provenance-aware causal memory.  [SOUND core]

A key/value store whose writes are events in a causal ledger. The invariants
mirror the HorizonProtocol design and the Global-Variables fact-store culture:

  * Append-only: writes are never destroyed; superseded values are retained
    with provenance (assumption-taint / invalidation-traversal analogue).
  * Causal ordering: a write W2 may supersede W1 only if W1 is in W2's causal
    past (the light-cone gate for geometric observers, happens-before for
    logical ones). A later-in-past write cannot silently overwrite a value it
    could not have seen.
  * Concurrent writes are NOT merged by fiat: they are stored as parallel
    candidates with provenance and surfaced for explicit resolution (the
    PGSD "retain candidates, defer selection" pattern). Reading a key with
    unresolved concurrent writes returns a CONFLICT with all candidates.
  * Every value carries provenance: which observer wrote it, under what clock,
    and its causal predecessors.

This module is clock-agnostic: it takes an `ordering` object exposing
`before(a, b) -> bool` and `concurrent(a, b) -> bool` over write metadata, so
the same memory works with geometric or logical observers.
"""
import hashlib
import json


def _wid(key, value, observer, clock):
    body = json.dumps({"key": key, "value": value, "observer": observer,
                       "clock": clock}, sort_keys=True).encode()
    return hashlib.sha256(body).hexdigest()[:16]


class Write:
    __slots__ = ("wid", "key", "value", "observer", "clock", "preds")

    def __init__(self, key, value, observer, clock, preds):
        self.key = key
        self.value = value
        self.observer = observer
        self.clock = clock            # {"time_ns":..,"pos_nm":..} or {"vc":{..}}
        self.preds = tuple(preds)     # wids this write claims to supersede
        self.wid = _wid(key, value, observer, clock)

    def provenance(self):
        return {"wid": self.wid, "key": self.key, "value": self.value,
                "observer": self.observer, "clock": self.clock,
                "supersedes": list(self.preds)}


class GeometricOrdering:
    """Light-cone ordering over writes with {'time_ns','pos_nm'} clocks.
    Reuses `horizon.geometry` unmodified - the same exact kernel H1-H6
    certify against."""
    def __init__(self):
        from horizon.geometry import causally_admissible
        self._adm = causally_admissible

    def _tp(self, w):
        return w.clock["time_ns"], tuple(w.clock["pos_nm"])

    def before(self, a, b):
        (ta, pa), (tb, pb) = self._tp(a), self._tp(b)
        return tb > ta and self._adm(ta, pa, tb, pb)

    def concurrent(self, a, b):
        (ta, pa), (tb, pb) = self._tp(a), self._tp(b)
        ab = self._adm(ta, pa, tb, pb)
        ba = self._adm(tb, pb, ta, pa)
        return (not ab) and (not ba)

    def witness(self, a, b):
        from horizon.geometry import admissibility_witness
        (ta, pa), (tb, pb) = self._tp(a), self._tp(b)
        return admissibility_witness(ta, pa, tb, pb)


class LogicalOrdering:
    """Vector-clock ordering over writes with {'vc': {...}} clocks."""
    def before(self, a, b):
        from .vclock import happens_before
        return happens_before(a.clock["vc"], b.clock["vc"])

    def concurrent(self, a, b):
        from .vclock import concurrent
        return concurrent(a.clock["vc"], b.clock["vc"])

    def witness(self, a, b):
        return {"vc_a": a.clock["vc"], "vc_b": b.clock["vc"]}


class CausalMemory:
    def __init__(self, ordering):
        self.ordering = ordering
        self.writes = {}              # wid -> Write
        self.by_key = {}              # key -> [wid, ...] in insertion order
        self.rejections = []          # audit log

    def put(self, key, value, observer, clock, supersedes=()):
        w = Write(key, value, observer, clock, supersedes)
        if w.wid in self.writes:
            # idempotent retry: (key, value, observer, clock) hashes to a
            # wid already recorded. Return the ORIGINAL admission rather
            # than re-appending to by_key (which would make _frontier see
            # the same write twice and _get_ falsely report CONFLICT) or
            # overwriting self.writes (which would silently rewrite an
            # append-only entry's provenance if this retry declared a
            # different `supersedes`).
            existing = self.writes[w.wid]
            return {"wid": existing.wid, "verdict": "ADMITTED",
                    "provenance": existing.provenance()}
        # validate claimed supersessions are causally admissible
        for pred_wid in w.preds:
            if pred_wid not in self.writes:
                rec = {"wid": w.wid, "verdict": "REJECTED",
                       "reason": "unknown_predecessor", "pred": pred_wid}
                self.rejections.append(rec)
                return rec
            pred = self.writes[pred_wid]
            if not self.ordering.before(pred, w):
                rec = {"wid": w.wid, "verdict": "REJECTED",
                       "reason": "supersedes_non_ancestor",
                       "pred": pred_wid,
                       "witness": self.ordering.witness(pred, w)}
                self.rejections.append(rec)
                return rec
        self.writes[w.wid] = w
        self.by_key.setdefault(key, []).append(w.wid)
        return {"wid": w.wid, "verdict": "ADMITTED",
                "provenance": w.provenance()}

    def _frontier(self, key):
        """Writes for `key` not superseded by any causally-later write.
        A write is superseded iff some other live write for the same key
        claims it as a validated predecessor (`put` already checked
        `ordering.before` before accepting that claim, so membership in
        `other.preds` alone is sufficient - see MNX-B/C)."""
        wids = self.by_key.get(key, [])
        ws = [self.writes[w] for w in wids]
        frontier = []
        for w in ws:
            superseded = any(w.wid in other.preds
                            for other in ws if other.wid != w.wid)
            if not superseded:
                frontier.append(w)
        return frontier

    def get(self, key):
        """Return the resolved value or a CONFLICT with concurrent candidates."""
        frontier = self._frontier(key)
        if not frontier:
            return {"status": "EMPTY", "key": key}
        if len(frontier) == 1:
            w = frontier[0]
            return {"status": "RESOLVED", "key": key, "value": w.value,
                    "provenance": w.provenance()}
        # multiple live writes: surface as an unresolved conflict
        candidates = [w.provenance() for w in frontier]
        return {"status": "CONFLICT", "key": key,
                "candidates": candidates,
                "note": "concurrent writes retained with provenance; "
                        "resolve explicitly (PGSD deferred selection)"}

    def resolve(self, key, chosen_wid, observer, clock):
        """Explicit conflict resolution: a new write that supersedes ALL current
        frontier candidates (must be causally after each). `chosen_wid` must
        be one of `key`'s current frontier candidates - not merely any wid
        that happens to exist in the store, which could belong to a
        different key entirely or to a write already superseded for this
        one, and would otherwise let a resolution "choose" a value that was
        never actually a live candidate for `key`."""
        frontier = self._frontier(key)
        preds = [w.wid for w in frontier]
        if chosen_wid not in preds:
            return {"verdict": "REJECTED", "reason": "not_a_frontier_candidate",
                    "key": key, "chosen_wid": chosen_wid}
        chosen = self.writes[chosen_wid]
        return self.put(key, chosen.value, observer, clock, supersedes=preds)
