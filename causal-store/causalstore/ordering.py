"""L2 — the ordering contract and its two implementations.  [SOUND]

THE CONTRACT (the only coupling point in the whole system):

    class Ordering:
        def before(self, a, b) -> bool      # is event a in event b's causal past?
        def concurrent(self, a, b) -> bool  # neither before the other?
        def resolves(self, a, b) -> bool    # is a-vs-b decided, or apparatus-limited?
        def witness(self, a, b) -> dict     # evidence for the decision

CK2-05 (protocol/causal-kernel-v2 SPEC.md, gate G-CK2-3): `resolves` is now
part of the required contract, not an optional extra. `concurrent()` alone
cannot distinguish a pair PROVEN independent from one that is merely
apparatus-limited (clock uncertainty straddles the light-time floor), and
`causalstore.store.CausalStore.write()`'s coordination-free path must never
treat the latter as the former. All three implementations below already
provided `resolves()`; this only makes it load-bearing for every consumer,
not just `HybridOrdering`'s internal fallback choice.

Events carry a `clock` dict, one of:
    {"time_ns": int, "pos_nm": [x,y,z], "u_ns": int}   # geometric
    {"vc": {node_id: counter}}                          # logical

Anything satisfying this contract can drive the store. This is a STABLE ABI:
a future database/memory layer, a third-party timing source, or a different
ordering scheme plugs in here without touching the engine.

(Erratum: an earlier version of `GeometricOrdering.resolves()` tested
`abs(tb - ta) > combined_u` - the RAW elapsed time against the combined clock
uncertainty, with no reference at all to the light-time floor required for
the claimed separation. A pair can have an elapsed time of many seconds
(comfortably larger than a microsecond-scale `combined_u`) while still
sitting within nanoseconds of its own (also large) required floor - exactly
the boundary case a resolution check exists to catch. Concretely confirmed:
for a ~1,000,000 km separation with a required floor of ~3,335,641 ns, a
measured `dt` of `floor + 500` ns with `combined_u = 2000` ns was reported
RESOLVED by the old formula (500 ns margin, comfortably inside the 2000 ns
uncertainty band) - a pair whose admissibility verdict a clock-error-sized
perturbation could flip, wrongly treated as settled. `HybridOrdering`'s
entire safety argument - "geometric where it resolves, logical fallback
elsewhere" - depends on `resolves()` correctly gating exactly this case, so
this was not a cosmetic bug. Fixed: `resolves()` now compares the MARGIN to
`horizon.geometry`'s exact `min_light_time_ns` floor against the combined
uncertainty, not the raw elapsed time - the same "compare to the true floor,
never to a disconnected proxy quantity" discipline HorizonProtocol's own
H5/H7/H8 budgeted gates already apply.)

(Erratum 2: `GeometricOrdering.before()` computed the exact geometric verdict
but never consulted `resolves()` at all, so an unresolved pair (one where
clock uncertainty cannot rule out the opposite order) was still reported as
a definite `before`/`after` - contradicting this class's own docstring
("otherwise reports unresolved... caller treats as concurrent"). This was
invisible through `HybridOrdering`, which always checks `geo.resolves()`
itself before trusting `geo.before()` - but `GeometricOrdering` is also a
supported STANDALONE L2 implementation (used directly by `CausalStore` in
tests and `bench/geo_workload.py`), and there nothing enforced the promise.
Concretely confirmed: two co-located writes 1ns apart with 1000ns uncertainty
each (`combined_u=2000ns`, `required_ns=0`) are unresolved (`resolves()` is
False), yet `before()` reported the later one as a definite causal successor
- exactly the ambiguous case `CausalStore.write()` needs surfaced, not
hidden, since it decides whether to supersede or retain a value. Fixed:
`before()` now returns False whenever `resolves()` is False, so an unresolved
pair falls through to `concurrent()` = True on both instances of this class,
matching the documented contract without requiring every caller to know
about `resolves()` itself.)
"""
from .geometry import C_NM_PER_NS, admissibility_witness, causally_admissible, min_light_time_ns


class GeometricOrdering:
    """Exact light-cone ordering. Resolves only when flight-time can exceed
    clock uncertainty; otherwise reports unresolved (caller treats as concurrent
    for the performance path, or falls back to logical for correctness)."""

    def _tp(self, e):
        c = e["clock"]
        return c["time_ns"], tuple(c["pos_nm"]), c.get("u_ns", 0)

    def before(self, a, b):
        ta, pa, ua = self._tp(a)
        tb, pb, ub = self._tp(b)
        # a strictly before b, admissible even crediting uncertainty against us:
        # require b later than a by more than the combined uncertainty AND inside cone
        if tb <= ta:
            return False
        # an unresolved pair (clock uncertainty cannot rule out the opposite
        # order) must never be reported as a definite before/after - see
        # module erratum 2. Both before(a,b) and before(b,a) fall to False,
        # so concurrent(a,b) correctly reports True for an unresolved pair.
        if not self.resolves(a, b):
            return False
        return causally_admissible(ta, pa, tb, pb)

    def concurrent(self, a, b):
        return (not self.before(a, b)) and (not self.before(b, a))

    def resolves(self, a, b):
        """True iff clock uncertainty cannot flip the admissibility verdict:
        the measured elapsed time, adjusted by the combined uncertainty in
        either direction, stays entirely on one side of the exact light-time
        floor required for this pair's separation (see module erratum)."""
        ta, pa, ua = self._tp(a)
        tb, pb, ub = self._tp(b)
        dt = tb - ta
        combined_u = ua + ub
        required_ns = min_light_time_ns(pa, pb)
        # the true dt could be anywhere in [dt - combined_u, dt + combined_u];
        # resolved iff that whole interval stays on one side of required_ns
        return (dt - combined_u >= required_ns) or (dt + combined_u < required_ns)

    def witness(self, a, b):
        ta, pa, ua = self._tp(a)
        tb, pb, ub = self._tp(b)
        w = admissibility_witness(ta, pa, tb, pb)
        w["combined_u_ns"] = ua + ub
        w["required_ns"] = min_light_time_ns(pa, pb)
        w["resolves"] = self.resolves(a, b)
        return w


class LogicalOrdering:
    """Vector-clock happens-before — the always-available fallback.

    (Erratum 3: `before()` used raw dict inequality (`x != y`) as the strict
    half of the partial order instead of `leq(x, y) and not leq(y, x)`. Two
    vector clocks that are the same logical instant up to zero-padding - e.g.
    `{"n1": 1}` and `{"n1": 1, "n2": 0}`, which every component-wise
    comparison treats as equal - are a DIFFERENT dict, so `x != y` was True
    for both orderings while `leq` also held both ways, making `before(a, b)`
    and `before(b, a)` simultaneously True: an antisymmetry violation of the
    causal partial order this class exists to provide. Fixed to derive strict
    order from `leq` alone, matching the normalized pattern already proven in
    `mnemesis/vclock.py::happens_before`.)
    """

    def _vc(self, e):
        return e["clock"]["vc"]

    def _leq(self, x, y):
        keys = set(x) | set(y)
        return all(x.get(k, 0) <= y.get(k, 0) for k in keys)

    def before(self, a, b):
        x, y = self._vc(a), self._vc(b)
        return self._leq(x, y) and not self._leq(y, x)

    def concurrent(self, a, b):
        return (not self.before(a, b)) and (not self.before(b, a))

    def resolves(self, a, b):
        return True  # vector clocks always decide

    def witness(self, a, b):
        return {"vc_a": self._vc(a), "vc_b": self._vc(b)}


class HybridOrdering:
    """Geometric where it resolves, logical elsewhere. Requires events to carry
    BOTH a geometric clock and a vc. This is the production default: physical
    certification when distance/precision allow, logical correctness always."""

    def __init__(self):
        self.geo = GeometricOrdering()
        self.log = LogicalOrdering()

    def before(self, a, b):
        if self.geo.resolves(a, b):
            return self.geo.before(a, b)
        return self.log.before(a, b)

    def concurrent(self, a, b):
        return (not self.before(a, b)) and (not self.before(b, a))

    def resolves(self, a, b):
        return True

    def witness(self, a, b):
        if self.geo.resolves(a, b):
            w = self.geo.witness(a, b); w["mode"] = "geometric"; return w
        w = self.log.witness(a, b); w["mode"] = "logical_fallback"; return w
