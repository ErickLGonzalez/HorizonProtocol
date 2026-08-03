"""H2-B: causal-isolation precondition, two-sided. [SOUND]"""
import unittest
from horizon.commitment import (SITE_1, SITE_2, DT_RESP_NS, DT_ROUND_NS,
                                isolation_gate, sustained_isolation_gate)
from horizon.geometry import causally_admissible, min_light_time_ns


class TestIsolationGate(unittest.TestCase):
    def test_frozen_geometry_is_isolated(self):
        res = isolation_gate(SITE_1, SITE_2, DT_RESP_NS)
        self.assertEqual(res["verdict"], "PASS")
        mlt = min_light_time_ns(SITE_1, SITE_2)
        # exact-integer statements of the same fact
        self.assertLess(DT_RESP_NS, mlt)
        self.assertFalse(causally_admissible(0, SITE_1, DT_RESP_NS, SITE_2))
        self.assertFalse(res["exact_witness"]["admissible"])
        self.assertEqual(res["one_way_light_time_ns"], mlt)

    def test_converse_control_missized_window_is_admissible(self):
        mlt = min_light_time_ns(SITE_1, SITE_2)
        dt_bad = mlt + 1
        self.assertTrue(causally_admissible(0, SITE_1, dt_bad, SITE_2))
        res = isolation_gate(SITE_1, SITE_2, dt_bad)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertTrue(res["exact_witness"]["admissible"])

    def test_symmetry(self):
        a = isolation_gate(SITE_1, SITE_2, DT_RESP_NS)
        b = isolation_gate(SITE_2, SITE_1, DT_RESP_NS)
        self.assertEqual(a["verdict"], b["verdict"])
        self.assertEqual(a["one_way_light_time_ns"], b["one_way_light_time_ns"])

    def test_sustained_schedule_is_cross_round_isolated(self):
        res = sustained_isolation_gate(SITE_1, SITE_2, DT_ROUND_NS, DT_RESP_NS)
        mlt = min_light_time_ns(SITE_1, SITE_2)
        self.assertEqual(res["verdict"], "PASS")
        self.assertFalse(causally_admissible(0, SITE_1,
                                             DT_ROUND_NS + DT_RESP_NS, SITE_2))
        self.assertLess(DT_ROUND_NS + DT_RESP_NS, mlt)

    def test_sustained_schedule_converse_control(self):
        # a round period tight enough that a round-k response could still
        # reach the other site inside round k+1's window must be caught,
        # even though the single-window isolation_gate alone would miss it
        mlt = min_light_time_ns(SITE_1, SITE_2)
        dt_round_bad = mlt  # dt_round_bad + DT_RESP_NS > mlt
        single_window = isolation_gate(SITE_1, SITE_2, DT_RESP_NS)
        self.assertEqual(single_window["verdict"], "PASS")
        res = sustained_isolation_gate(SITE_1, SITE_2, dt_round_bad, DT_RESP_NS)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertTrue(res["exact_witness"]["admissible"])


if __name__ == "__main__":
    unittest.main()
