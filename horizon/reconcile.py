"""Cross-node event reconciliation under proper-time divergence.  [SOUND]

SP-3 (see docs/sp3-spec.md), built on SP-0's `Worldline` /
`causally_admissible_wl`, SP-2's `TrajectoryEnvelope` / `two_floor_verdict`,
and the causal substrate's vector clocks (`mnemesis.vclock`) — all
imported, never modified.

Ordering between two nodes' events is decided ONLY by:

  1. causal lineage — vector-clock happens-before (`mnemesis.vclock`,
     unmodified), and
  2. light-cone admissibility of that lineage claim — `causally_admissible_wl`
     (SP-0) at the worldline-evaluated coordinate positions, or, when a
     node's position is only known as an SP-2 `TrajectoryEnvelope`, the
     `two_floor_verdict` (SP-2) instead.

NEVER by comparing the two nodes' `ProperTimeStamp`s directly —
`horizon.proper_time.ProperTimeStamp`'s comparison operators raise for a
cross-node comparison, so a code path that tried would fail loudly rather
than silently substituting a physically meaningless clock comparison. Each
`Event` below carries a `proper_time_stamp` for provenance/logging only;
`reconcile` never reads it to decide a verdict (F2).

**Verdict vocabulary note:** the handoff's section 1.3 specifies
`BEFORE`/`AFTER`/`CONCURRENT`/`APPARATUS_LIMITED` as `reconcile`'s output
(`event_a`'s relation to `event_b`); its section 2 (SP3-E) instead lists
`ADMITTED`/`REJECTED`/`APPARATUS_LIMITED`/`CONCURRENT`, reusing
`two_floor`'s vocabulary loosely. This module follows section 1.3's
explicit contract for `reconcile`'s return value (`BEFORE`/`AFTER` require
BOTH a lineage edge AND light-cone/two-floor admissibility to agree;
otherwise `CONCURRENT` or `APPARATUS_LIMITED`) and records the underlying
`ADMITTED`/`REJECTED`/`APPARATUS_LIMITED` physical check in the witness so
both vocabularies are visible and traceable to which check produced them.
"""
from mnemesis.vclock import happens_before

from horizon.worldline import causally_admissible_wl
from horizon.two_floor import two_floor_verdict
from horizon.uncertainty import TrajectoryEnvelope


def _require_int(value, what):
    if not isinstance(value, int):
        raise TypeError(f"{what} must be an exact int, got {type(value).__name__}: {value!r}")
    return value


class Event:
    """One node's stamped event.

    `node_id`: the authoring node. `vclock`: its logical vector clock (a
    dict, `mnemesis.vclock` format) — the causal-lineage signal.
    `t_coord_ns`: the coordinate time (the single frame `Worldline`s and
    the kernel are expressed in — a well-defined choice of inertial frame
    in flat spacetime; NOT the same as the node's own proper time, and
    never compared across nodes as a "shared now" — see module docstring).
    `locator`: a `Worldline` if the position at `t_coord_ns` is known
    exactly, or a `TrajectoryEnvelope` if it is only known within an SP-2
    uncertainty envelope. `proper_time_stamp`: the node's own
    `ProperTimeStamp` at this event — carried for provenance/logging only,
    never read by `reconcile` to decide anything."""

    def __init__(self, node_id, vclock: dict, t_coord_ns: int, locator,
                 proper_time_stamp=None):
        self.node_id = node_id
        self.vclock = dict(vclock)
        self.t_coord_ns = _require_int(t_coord_ns, "t_coord_ns")
        self.locator = locator
        self.proper_time_stamp = proper_time_stamp


def _physical_verdict(from_event: Event, to_event: Event):
    """ADMITTED/REJECTED/APPARATUS_LIMITED for whether `from_event` could
    causally precede `to_event`, dispatching on whether `to_event`'s
    position is exact (`Worldline`) or an SP-2 `TrajectoryEnvelope`."""
    if isinstance(to_event.locator, TrajectoryEnvelope):
        p_from = from_event.locator.position_at(from_event.t_coord_ns)
        result = two_floor_verdict(from_event.t_coord_ns, p_from,
                                   to_event.t_coord_ns, to_event.locator)
        return result["verdict"], result["witness"]
    ok = causally_admissible_wl(from_event.locator, from_event.t_coord_ns,
                                to_event.locator, to_event.t_coord_ns)
    return ("ADMITTED" if ok else "REJECTED"), {"kind": "worldline_pair"}


def reconcile(event_a: Event, event_b: Event) -> dict:
    """`{"verdict": "BEFORE"|"AFTER"|"CONCURRENT"|"APPARATUS_LIMITED",
    "witness": {...}}` describing `event_a`'s relation to `event_b`.
    `BEFORE`/`AFTER` are returned ONLY when a vector-clock lineage edge
    AND the physical check (light cone or two-floor) agree (F4); any
    disagreement — including a lineage claim the physics forbids — is
    retained as `CONCURRENT`, never silently trusted (F3, the #548
    invariant under divergent clocks)."""
    a_before_b = happens_before(event_a.vclock, event_b.vclock)
    b_before_a = happens_before(event_b.vclock, event_a.vclock)

    witness = {
        "node_a": event_a.node_id, "node_b": event_b.node_id,
        "lineage_a_before_b": a_before_b, "lineage_b_before_a": b_before_a,
        "decided_by": "vector_clock_lineage_and_light_cone_only",
        "proper_time_used_for_ordering": False,
    }

    if a_before_b:
        phys_verdict, phys_witness = _physical_verdict(event_a, event_b)
        witness["physical_check"] = {"direction": "a_to_b", "verdict": phys_verdict,
                                     **phys_witness}
        if phys_verdict == "ADMITTED":
            return {"verdict": "BEFORE", "witness": witness}
        if phys_verdict == "APPARATUS_LIMITED":
            return {"verdict": "APPARATUS_LIMITED", "witness": witness}
        witness["reason"] = "lineage_claims_an_edge_the_light_cone_forbids"
        return {"verdict": "CONCURRENT", "witness": witness}

    if b_before_a:
        phys_verdict, phys_witness = _physical_verdict(event_b, event_a)
        witness["physical_check"] = {"direction": "b_to_a", "verdict": phys_verdict,
                                     **phys_witness}
        if phys_verdict == "ADMITTED":
            return {"verdict": "AFTER", "witness": witness}
        if phys_verdict == "APPARATUS_LIMITED":
            return {"verdict": "APPARATUS_LIMITED", "witness": witness}
        witness["reason"] = "lineage_claims_an_edge_the_light_cone_forbids"
        return {"verdict": "CONCURRENT", "witness": witness}

    witness["reason"] = "no_lineage_edge_either_direction"
    return {"verdict": "CONCURRENT", "witness": witness}
