"""Typed edge claims (CK2-05, protocol/causal-kernel-v2 SPEC.md §4).

Physical admissibility (the geometric cone test passing -- an influence was
POSSIBLE) and observed dependency (the creator actually observed the
predecessor) are different claims requiring different evidence, and must
never be conflated. This module is the shared vocabulary both
`horizon.ledger.CausalLedger` and `mnemesis.memory.CausalMemory` use to keep
that distinction explicit and auditable.

Rule (SPEC.md §4): a `physical_admissibility` claim is never automatically
upgraded to `observed_dependency` by any conforming implementation. A caller
asserting `observed_dependency` must supply its own evidence for that claim.
"""
import hashlib
import json


class EdgeKind:
    DECLARED_DEPENDENCY = "declared_dependency"
    OBSERVED_DEPENDENCY = "observed_dependency"
    ATTESTED_DEPENDENCY = "attested_dependency"
    PHYSICAL_ADMISSIBILITY = "physical_admissibility"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    RESOLVES = "resolves"
    INVALIDATES = "invalidates"

    ALL = frozenset({
        DECLARED_DEPENDENCY, OBSERVED_DEPENDENCY, ATTESTED_DEPENDENCY,
        PHYSICAL_ADMISSIBILITY, DERIVED_FROM, SUPERSEDES, RESOLVES,
        INVALIDATES,
    })

    # Kinds that assert an actual dependency happened (as opposed to merely
    # having been geometrically possible). Used by
    # `CausalLedger.has_observed_dependency` below.
    DEPENDENCY_KINDS = frozenset({
        DECLARED_DEPENDENCY, OBSERVED_DEPENDENCY, ATTESTED_DEPENDENCY,
    })


def compute_edge_id(from_event, to_event, kind, asserted_by, asserted_at):
    payload = {
        "from_event": from_event, "to_event": to_event, "kind": kind,
        "asserted_by": asserted_by, "asserted_at": asserted_at,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


class EdgeClaim:
    """One typed claim about the relationship between two events.
    Immutable once constructed -- claims are additive evidence, never
    edited; a mistaken claim is superseded/invalidated by a NEW claim of
    kind `invalidates`, never mutated in place."""

    __slots__ = (
        "edge_id", "from_event", "to_event", "kind", "evidence_refs",
        "asserted_by", "asserted_at", "relation_decision_ref",
    )

    def __init__(self, from_event, to_event, kind, asserted_by, asserted_at,
                 evidence_refs=None, relation_decision_ref=None):
        if kind not in EdgeKind.ALL:
            raise ValueError(f"unknown EdgeKind: {kind!r}")
        if not asserted_by:
            raise ValueError("asserted_by is required")
        if not asserted_at:
            raise ValueError("asserted_at is required")
        self.from_event = from_event
        self.to_event = to_event
        self.kind = kind
        self.asserted_by = asserted_by
        self.asserted_at = asserted_at
        self.evidence_refs = tuple(evidence_refs or ())
        self.relation_decision_ref = relation_decision_ref
        self.edge_id = compute_edge_id(from_event, to_event, kind, asserted_by, asserted_at)

    def as_dict(self):
        d = {
            "edge_id": self.edge_id,
            "from_event": self.from_event,
            "to_event": self.to_event,
            "kind": self.kind,
            "asserted_by": self.asserted_by,
            "asserted_at": self.asserted_at,
        }
        if self.evidence_refs:
            d["evidence_refs"] = list(self.evidence_refs)
        if self.relation_decision_ref is not None:
            d["relation_decision_ref"] = self.relation_decision_ref
        return d
