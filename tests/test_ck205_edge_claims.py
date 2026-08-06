"""CK2-05 (protocol/causal-kernel-v2 SPEC.md §4): typed edge claims.

Physical admissibility and observed dependency are different claims
requiring different evidence and must never be conflated -- these tests
prove `CausalLedger` keeps them separate rather than silently upgrading one
into the other.
"""
import dataclasses
import unittest

from horizon.edge_claims import EdgeClaim, EdgeKind, compute_edge_id
from horizon.geometry import C_NM_PER_NS
from horizon.ledger import CausalLedger


class TestAdmissibilityIsNotObservedDependency(unittest.TestCase):
    def setUp(self):
        self.L = CausalLedger()
        self.L.add_event("A", 0, (0, 0, 0))
        self.L.add_event("B", 10, (C_NM_PER_NS, 0, 0))

    def test_admitted_edge_records_only_a_physical_admissibility_claim(self):
        self.L.add_edge("A", "B")
        claims = [c for c in self.L.edge_claims if c.from_event == "A" and c.to_event == "B"]
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].kind, EdgeKind.PHYSICAL_ADMISSIBILITY)

    def test_admitted_edge_alone_is_not_an_observed_dependency(self):
        self.L.add_edge("A", "B")
        self.assertFalse(self.L.has_observed_dependency("A", "B"))

    def test_explicit_observed_dependency_claim_is_recorded_and_visible(self):
        self.L.add_edge("A", "B")
        self.L.add_dependency_claim(
            "A", "B", EdgeKind.OBSERVED_DEPENDENCY,
            asserted_by="agent-1", asserted_at="10",
            evidence_refs=["log:agent-1:read-A-before-writing-B"],
        )
        self.assertTrue(self.L.has_observed_dependency("A", "B"))

    def test_dependency_claim_does_not_require_prior_physical_admissibility(self):
        # The two questions ("was it possible" vs "did it happen") are
        # independent -- a dependency claim can be recorded even for a pair
        # add_edge was never called on (e.g. rejected, or not yet checked).
        self.L.add_dependency_claim(
            "A", "B", EdgeKind.DECLARED_DEPENDENCY,
            asserted_by="agent-2", asserted_at="1",
        )
        self.assertTrue(self.L.has_observed_dependency("A", "B"))
        self.assertEqual(self.L.edges, set())  # add_edge was never called

    def test_dependency_claim_rejects_physical_admissibility_kind(self):
        with self.assertRaises(ValueError):
            self.L.add_dependency_claim(
                "A", "B", EdgeKind.PHYSICAL_ADMISSIBILITY,
                asserted_by="agent-1", asserted_at="1",
            )

    def test_dependency_claim_rejects_unknown_events(self):
        with self.assertRaises(KeyError):
            self.L.add_dependency_claim(
                "A", "unknown-event", EdgeKind.OBSERVED_DEPENDENCY,
                asserted_by="agent-1", asserted_at="1",
            )

    def test_retrying_add_edge_does_not_duplicate_the_admissibility_claim(self):
        # review fix: add_edge(a, b) is idempotent for `edges` (a set) but
        # was unconditionally appending a new claim on every call --
        # breaking the 1:1 correspondence between admitted edges and
        # physical_admissibility claims on a retry.
        self.L.add_edge("A", "B")
        self.L.add_edge("A", "B")
        self.L.add_edge("A", "B")
        claims = [c for c in self.L.edge_claims if c.from_event == "A" and c.to_event == "B"]
        self.assertEqual(len(claims), 1)

    def test_rejected_edge_still_records_no_dependency_claim(self):
        # A REJECTED admissibility check must not manufacture any claim.
        self.L.add_event("C", 0, (C_NM_PER_NS, 0, 0))  # spacelike to A
        self.L.add_edge("A", "C")
        self.assertEqual(len([c for c in self.L.edge_claims if c.to_event == "C"]), 0)
        self.assertFalse(self.L.has_observed_dependency("A", "C"))


class TestEdgeClaimConstruction(unittest.TestCase):
    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            EdgeClaim("A", "B", "assumed_dependency", "agent-1", "1")

    def test_missing_asserted_by_rejected(self):
        with self.assertRaises(ValueError):
            EdgeClaim("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "", "1")

    def test_missing_asserted_at_rejected(self):
        with self.assertRaises(ValueError):
            EdgeClaim("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "")

    def test_edge_id_is_deterministic_and_matches_schema_pattern(self):
        c1 = EdgeClaim("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1")
        c2 = EdgeClaim("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1")
        self.assertEqual(c1.edge_id, c2.edge_id)
        self.assertTrue(c1.edge_id.startswith("sha256:"))
        self.assertEqual(len(c1.edge_id), len("sha256:") + 64)

    def test_edge_id_changes_when_any_field_changes(self):
        base = compute_edge_id("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1")
        variants = [
            compute_edge_id("A2", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1"),
            compute_edge_id("A", "B2", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1"),
            compute_edge_id("A", "B", EdgeKind.DECLARED_DEPENDENCY, "agent-1", "1"),
            compute_edge_id("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-2", "1"),
            compute_edge_id("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "2"),
        ]
        self.assertEqual(len(set(variants) | {base}), 6)

    def test_as_dict_omits_empty_optional_fields(self):
        c = EdgeClaim("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1")
        d = c.as_dict()
        self.assertNotIn("evidence_refs", d)
        self.assertNotIn("relation_decision_ref", d)

    def test_claim_is_genuinely_immutable_not_just_by_docstring(self):
        # review fix: __slots__ alone does not prevent reassignment; the
        # class must actually raise on mutation, including for the field
        # that has_observed_dependency() reads (`kind`) and the one
        # edge_id's own hash was derived from (`from_event`).
        c = EdgeClaim("A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1")
        for field, value in (
            ("kind", EdgeKind.DECLARED_DEPENDENCY),
            ("from_event", "C"),
            ("to_event", "C"),
            ("evidence_refs", ("forged",)),
            ("edge_id", "sha256:" + "0" * 64),
        ):
            with self.assertRaises(dataclasses.FrozenInstanceError, msg=field):
                setattr(c, field, value)

    def test_as_dict_includes_populated_optional_fields(self):
        c = EdgeClaim(
            "A", "B", EdgeKind.OBSERVED_DEPENDENCY, "agent-1", "1",
            evidence_refs=["ref-1"], relation_decision_ref="decision-1",
        )
        d = c.as_dict()
        self.assertEqual(d["evidence_refs"], ["ref-1"])
        self.assertEqual(d["relation_decision_ref"], "decision-1")


if __name__ == "__main__":
    unittest.main()
