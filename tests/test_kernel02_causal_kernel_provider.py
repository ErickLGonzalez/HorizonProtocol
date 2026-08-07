"""KERNEL-02 (Light Cone Consistency Sequence 6): Horizon's
`protocol/causal-kernel-v2` provider adapter
(`horizon.providers.causal_kernel_provider`).

Exercises every `CausalRelationV2` outcome the adapter can reach, plus the
exact CK2-03 interval-boundary regression case already fixed in
`causal-store/causalstore/ordering.py` -- this is a fresh, independent
re-derivation of that same formula against the top-level `horizon.geometry`
primitives (see the module's own doc comment for why), so it needs its own
proof it doesn't reintroduce the bug those other implementations already
fixed, not an assumption that porting-by-formula was safe.

Not attempted here (disclosed, not silently skipped): full generic
conformance-vector parity against
`protocol/causal-kernel-v2/conformance/vectors.json` the way MnemesisOS's
`cross_check_v2.py`/Rust `tests/v2_conformance.rs` do. That needs either a
vendored copy of the shared vectors file plus a clock-family-detecting
`classify(a, b)` dispatcher (this adapter exposes typed
`classify_logical`/`classify_geometric` entry points instead, matching how
callers actually have geometry-lattice or vector-clock data, not a generic
wire envelope) -- a reasonable CK2-06 follow-up, not done in this PR.
"""
import unittest

from horizon.geometry import C_NM_PER_NS
from horizon.providers.causal_kernel_provider import (
    SCHEMA_VERSION,
    capabilities,
    classify_geometric,
    classify_logical,
)


class TestCapabilities(unittest.TestCase):
    def test_advertises_schema_version_and_both_clock_families(self):
        caps = capabilities()
        self.assertEqual(caps["schema_version"], "2.0.0")
        self.assertEqual(caps["schema_version"], SCHEMA_VERSION)
        self.assertEqual(set(caps["supported_clock_families"]), {"logical", "geometric"})


class TestClassifyLogical(unittest.TestCase):
    def test_strict_before(self):
        d = classify_logical({"n1": 1}, {"n1": 2})
        self.assertEqual(d["relation"], "before")
        self.assertEqual(d["clock_mode"], "logical")
        self.assertEqual(d["reason_code"], "LOGICAL_STRICT_ORDER")
        self.assertEqual(d["schema_version"], SCHEMA_VERSION)

    def test_strict_after(self):
        d = classify_logical({"n1": 2}, {"n1": 1})
        self.assertEqual(d["relation"], "after")

    def test_disjoint_is_logically_concurrent(self):
        d = classify_logical({"n1": 1}, {"n2": 1})
        self.assertEqual(d["relation"], "logically_concurrent")
        self.assertEqual(d["reason_code"], "LOGICAL_DISJOINT_CONCURRENT")

    def test_zero_padded_equivalence_is_equivalent_not_double_before(self):
        # Regression shape for the CK2-02 antisymmetry bug this program
        # already fixed elsewhere (causal-store/causalstore/ordering.py,
        # spikes/causal-substrate/rust): `{"n1": 1}` and
        # `{"n1": 1, "n2": 0}` are the same logical instant.
        d = classify_logical({"n1": 1}, {"n1": 1, "n2": 0})
        self.assertEqual(d["relation"], "equivalent")
        self.assertEqual(d["reason_code"], "LOGICAL_ZERO_PADDED_EQUIVALENT")

    def test_identical_vectors_are_equivalent(self):
        d = classify_logical({"n1": 5}, {"n1": 5})
        self.assertEqual(d["relation"], "equivalent")

    def test_negative_component_is_invalid_not_decided(self):
        d = classify_logical({"n1": -1}, {"n1": 1})
        self.assertEqual(d["relation"], "invalid")
        self.assertEqual(d["reason_code"], "MALFORMED_INPUT")


class TestClassifyGeometric(unittest.TestCase):
    def test_before_inside_cone(self):
        d = classify_geometric(0, (0, 0, 0), 0, 100, (C_NM_PER_NS, 0, 0), 0, "f", "f")
        self.assertEqual(d["relation"], "before")
        self.assertEqual(d["clock_mode"], "geometric")
        self.assertEqual(d["reason_code"], "GEOMETRIC_INTERVAL_CERTAIN_BEFORE")

    def test_after_is_the_mirror_of_before(self):
        d = classify_geometric(100, (C_NM_PER_NS, 0, 0), 0, 0, (0, 0, 0), 0, "f", "f")
        self.assertEqual(d["relation"], "after")
        self.assertEqual(d["reason_code"], "GEOMETRIC_INTERVAL_CERTAIN_AFTER")

    def test_same_event_is_equivalent(self):
        d = classify_geometric(50, (1, 2, 3), 0, 50, (1, 2, 3), 0, "f", "f")
        self.assertEqual(d["relation"], "equivalent")
        self.assertEqual(d["reason_code"], "GEOMETRIC_SAME_EVENT")

    def test_widely_separated_simultaneous_events_are_spacelike(self):
        d = classify_geometric(0, (0, 0, 0), 0, 0, (C_NM_PER_NS, 0, 0), 0, "f", "f")
        self.assertEqual(d["relation"], "spacelike")
        self.assertEqual(d["reason_code"], "GEOMETRIC_INTERVAL_SPACELIKE")

    def test_negative_uncertainty_is_invalid_not_decided(self):
        d = classify_geometric(0, (0, 0, 0), -1, 100, (0, 0, 0), 0, "f", "f")
        self.assertEqual(d["relation"], "invalid")
        self.assertEqual(d["reason_code"], "GEOMETRIC_NEGATIVE_UNCERTAINTY")

    def test_frame_mismatch_is_incomparable_not_decided(self):
        d = classify_geometric(0, (0, 0, 0), 0, 1, (0, 0, 0), 0, "alpha", "beta")
        self.assertEqual(d["relation"], "incomparable")
        self.assertEqual(d["reason_code"], "GEOMETRIC_FRAME_MISMATCH")

    def test_uncertainty_that_cannot_resolve_the_order_is_apparatus_limited(self):
        # 500ns apart with 1000ns combined uncertainty -> cannot resolve
        # (mirrors causalstore.ordering's own equivalent unit test).
        d = classify_geometric(0, (0, 0, 0), 500, 500, (C_NM_PER_NS, 0, 0), 500, "f", "f")
        self.assertEqual(d["relation"], "apparatus_limited")
        self.assertEqual(d["reason_code"], "GEOMETRIC_INTERVAL_STRADDLES_FLOOR")

    def test_widening_the_gap_beyond_uncertainty_resolves_to_before(self):
        d = classify_geometric(0, (0, 0, 0), 500, 5000, (C_NM_PER_NS, 0, 0), 500, "f", "f")
        self.assertEqual(d["relation"], "before")

    def test_interval_boundary_regression_ck2_03(self):
        # Exact case from `causalstore/ordering.py`'s own erratum comment:
        # a ~1,000,000km separation has a required light-time floor of
        # ~3,335,641ns; a measured dt just 500ns past that floor, with
        # 2000ns combined uncertainty, must be APPARATUS_LIMITED (the
        # uncertainty band still straddles the floor) -- the bug this
        # regression guards against reported it as resolved/certain
        # because it compared the raw elapsed time to the uncertainty
        # instead of the MARGIN to the true floor.
        pos_b = (1_000_000_000_000_000, 0, 0)  # 1,000,000 km in nm
        required_ns = 3_335_641  # min_light_time_ns(pos_a, pos_b), pinned by the erratum's own numbers
        dt = required_ns + 500
        d = classify_geometric(0, (0, 0, 0), 1000, dt, pos_b, 1000, "f", "f")
        self.assertEqual(d["required_light_time_ns"], required_ns)
        self.assertEqual(d["relation"], "apparatus_limited")
        self.assertEqual(d["reason_code"], "GEOMETRIC_INTERVAL_STRADDLES_FLOOR")

    def test_reverse_direction_straddling_the_boundary_is_apparatus_limited_not_after(self):
        # Codex review (PR #16, P1): b measured BEFORE a (dt negative), but
        # the uncertainty band straddles the reverse light-time floor too --
        # this must be APPARATUS_LIMITED, not a certain `after`. The fixed
        # bug: a single `resolves(a, b)`-style boolean (not symmetric under
        # argument order) was composed with directional `causally_admissible`
        # checks, so this exact shape (required_ns=1, dt=-2, combined_u=2,
        # true interval [-4, 0]) was wrongly reported `after` -- and the
        # argument-swapped case wrongly reported `apparatus_limited`,
        # proving the asymmetry directly.
        pos_a = (0, 0, 0)
        pos_b = (C_NM_PER_NS, 0, 0)  # required_ns == 1
        d_ab = classify_geometric(2, pos_a, 1, 0, pos_b, 1, "f", "f")  # dt = 0 - 2 = -2
        self.assertEqual(d_ab["required_light_time_ns"], 1)
        self.assertEqual(d_ab["measured_dt_ns"], -2)
        self.assertEqual(d_ab["relation"], "apparatus_limited")
        d_ba = classify_geometric(0, pos_b, 1, 2, pos_a, 1, "f", "f")  # swapped: dt = +2
        self.assertEqual(d_ba["relation"], "apparatus_limited")

    def test_witness_fields_are_populated_for_a_decided_geometric_relation(self):
        d = classify_geometric(0, (0, 0, 0), 0, 100, (C_NM_PER_NS, 0, 0), 0, "f", "f")
        self.assertEqual(d["measured_dt_ns"], 100)
        self.assertEqual(d["uncertainty_low_ns"], 100)
        self.assertEqual(d["uncertainty_high_ns"], 100)
        self.assertIsNotNone(d["required_light_time_ns"])

    def test_witness_fields_are_none_for_a_family_incomparable_result(self):
        d = classify_geometric(0, (0, 0, 0), 0, 1, (0, 0, 0), 0, "alpha", "beta")
        self.assertIsNone(d["measured_dt_ns"])
        self.assertIsNone(d["required_light_time_ns"])


class TestEveryDecisionHasTheSharedSchemaVersion(unittest.TestCase):
    def test_logical_and_geometric_decisions_both_carry_2_0_0(self):
        for d in [
            classify_logical({"n1": 1}, {"n1": 2}),
            classify_geometric(0, (0, 0, 0), 0, 100, (C_NM_PER_NS, 0, 0), 0, "f", "f"),
        ]:
            self.assertEqual(d["schema_version"], "2.0.0")


if __name__ == "__main__":
    unittest.main()
