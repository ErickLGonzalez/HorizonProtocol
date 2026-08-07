"""KERNEL-02 (Light Cone Consistency Sequence 6): Horizon's implementation of
the `protocol/causal-kernel-v2` provider contract.

`SEQ6_STABLE_KERNEL.md`'s required behavior: "MnemesisOS works in logical
mode without Horizon. Horizon supplies geometric evidence through an
adapter, not internal coupling." This module is that adapter -- it
translates HorizonProtocol's native primitives into the eight-value
`CausalRelationV2` vocabulary (`protocol/causal-kernel-v2/SPEC.md`) that
MnemesisOS's `crates/causal-kernel` (KERNEL-01) and
`spikes/causal-substrate/rust` both speak, so a decision produced here has
the exact same shape (`schema_version`, `relation`, `clock_mode`,
`reason_code`, `required_light_time_ns`, `measured_dt_ns`,
`uncertainty_low_ns`, `uncertainty_high_ns`) as one produced by either of
those. It imports only from the top-level `horizon`/`mnemesis` PRODUCTION
packages (`horizon.geometry`, `mnemesis.vclock`) -- never `causal-store`
(a separate benchmark-harness subproject with its own sys.path setup, not
an installed package this one can import cleanly) -- so this adapter has no
coupling to that subproject.

Why the resolves/apparatus-limited arithmetic is re-derived here rather than
imported: neither `horizon.ledger.CausalLedger` nor `horizon.geometry` has
any notion of per-event clock uncertainty (`CausalLedger` events are exact
`(time_ns, pos_nm)` pairs) -- `causal-store/causalstore/ordering.py`'s
`GeometricOrdering` is the only HorizonProtocol module that models
uncertainty at all, and it lives in that same unimportable subproject. The
four-way interval decision in `classify_geometric` matches MnemesisOS's
`classify_geometric_v2` (`spikes/causal-substrate/rust` and
`crates/causal-kernel`) exactly -- symmetric interval comparisons against
`required_ns` (from this repo's own `horizon.geometry.min_light_time_ns`),
not a separately-computed "resolves" boolean composed with directional
admissibility checks (an earlier version of this file did that, mirroring
`causalstore.ordering.GeometricOrdering.resolves`/`before` too literally --
that composition is unsound because `resolves()` is not symmetric under
argument order; see the review-fix comment in `classify_geometric` for the
concrete counterexample). Not invented fresh, and covered by this module's
own test suite including the exact CK2-03 interval-boundary regression case
those other implementations already carry.

`classify_logical` has one disclosed protocol-fidelity gap: HorizonProtocol's
native vector-clock representation (`mnemesis.vclock`, plain
`{node_id: counter}` dicts) carries no `observer_id`/`observer_epoch`, so
this adapter cannot reproduce CK2-04's `LOGICAL_EPOCH_CHANGE`/
`LOGICAL_COUNTER_REGRESSION` reason codes -- there is no epoch concept in
this repo's logical clocks to detect a change in. `capabilities()` still
advertises `"logical"` support (the core happens-before/concurrent
comparison is fully correct and CK2-02-hardened), but a caller relying on
epoch-change detection specifically must not expect it from this provider.
"""
from horizon.geometry import min_light_time_ns
from mnemesis.vclock import leq

SCHEMA_VERSION = "2.0.0"


def capabilities():
    """What this provider can back with real evidence -- see
    KERNEL-03/`consistency::negotiate_capabilities` on the MnemesisOS side:
    a provider must only ever advertise a clock family it can actually
    classify, never one it merely could support in principle.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "supported_clock_families": ["logical", "geometric"],
    }


def _decision(relation, clock_mode, reason_code, **extra):
    d = {
        "schema_version": SCHEMA_VERSION,
        "relation": relation,
        "clock_mode": clock_mode,
        "reason_code": reason_code,
        "required_light_time_ns": None,
        "measured_dt_ns": None,
        "uncertainty_low_ns": None,
        "uncertainty_high_ns": None,
    }
    d.update(extra)
    return d


def classify_logical(vector_a: dict, vector_b: dict) -> dict:
    """Classify two vector clocks (plain `{node_id: counter}` dicts,
    `mnemesis.vclock`'s native shape). See the module doc for why this
    cannot detect an epoch change (HorizonProtocol's vector clocks carry no
    epoch)."""
    if any(v < 0 for v in vector_a.values()) or any(v < 0 for v in vector_b.values()):
        return _decision("invalid", "logical", "MALFORMED_INPUT")
    # `mnemesis.vclock.concurrent` deliberately folds "equivalent under
    # zero-padding" into its own notion of "concurrent" (see its docstring)
    # -- CausalRelationV2 needs that split back out, so this classifies
    # directly off `leq` in both directions rather than composing
    # `happens_before`/`concurrent`, matching `causal_kernel::classify_logical_v2`'s
    # own `leq_ab`/`leq_ba` structure exactly.
    leq_ab = leq(vector_a, vector_b)
    leq_ba = leq(vector_b, vector_a)
    if leq_ab and leq_ba:
        return _decision("equivalent", "logical", "LOGICAL_ZERO_PADDED_EQUIVALENT")
    if leq_ab:
        return _decision("before", "logical", "LOGICAL_STRICT_ORDER")
    if leq_ba:
        return _decision("after", "logical", "LOGICAL_STRICT_ORDER")
    return _decision("logically_concurrent", "logical", "LOGICAL_DISJOINT_CONCURRENT")


def classify_geometric(
    time_ns_a: int,
    pos_nm_a,
    uncertainty_ns_a: int,
    time_ns_b: int,
    pos_nm_b,
    uncertainty_ns_b: int,
    frame_id_a: str,
    frame_id_b: str,
) -> dict:
    """Classify two geometric clocks. `frame_id` is caller-supplied (not
    read off `pos_nm`) because HorizonProtocol's position lattices
    (`horizon.geo_frame.GeoFrame`) carry frame identity separately from the
    quantized nanometer coordinates themselves -- two positions are only
    comparable at all when both were quantized onto the SAME frame."""
    if uncertainty_ns_a < 0 or uncertainty_ns_b < 0:
        return _decision("invalid", "geometric", "GEOMETRIC_NEGATIVE_UNCERTAINTY")
    if frame_id_a != frame_id_b:
        return _decision("incomparable", "geometric", "GEOMETRIC_FRAME_MISMATCH")
    if time_ns_a == time_ns_b and tuple(pos_nm_a) == tuple(pos_nm_b):
        return _decision("equivalent", "geometric", "GEOMETRIC_SAME_EVENT")

    dt = time_ns_b - time_ns_a
    combined_u = uncertainty_ns_a + uncertainty_ns_b
    required_ns = min_light_time_ns(pos_nm_a, pos_nm_b)
    extra = {
        "required_light_time_ns": required_ns,
        "measured_dt_ns": dt,
        "uncertainty_low_ns": dt - combined_u,
        "uncertainty_high_ns": dt + combined_u,
    }

    # Codex review (PR #16, P1): the previous version computed a single
    # `resolves(a, b)` boolean (mirroring `causalstore.ordering`'s
    # `resolves()`, which is NOT symmetric under argument order -- e.g.
    # dt=-2, combined_u=2, required_ns=1 gives `resolves(a,b)=True` but
    # `resolves(b,a)=False`) and then gated separate `causally_admissible`
    # checks in each direction against it, so a genuinely apparatus-limited
    # reverse-direction pair could be reported as a certain `after`.
    # Matches MnemesisOS's `classify_geometric_v2` exactly instead: four
    # mutually exclusive interval comparisons, symmetric by construction,
    # with no separate "resolves" flag to misapply.
    if abs(dt) + combined_u < required_ns:
        return _decision("spacelike", "geometric", "GEOMETRIC_INTERVAL_SPACELIKE", **extra)
    if dt - combined_u >= required_ns:
        return _decision("before", "geometric", "GEOMETRIC_INTERVAL_CERTAIN_BEFORE", **extra)
    if (-dt) - combined_u >= required_ns:
        return _decision("after", "geometric", "GEOMETRIC_INTERVAL_CERTAIN_AFTER", **extra)
    return _decision(
        "apparatus_limited", "geometric", "GEOMETRIC_INTERVAL_STRADDLES_FLOOR", **extra
    )
