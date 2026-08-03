"""H2-B: causal-isolation precondition, two-sided. [SOUND]"""
import unittest
from horizon.commitment import (SITE_1, SITE_2, DT_RESP_NS, isolation_gate)
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


if __name__ == "__main__":
    unittest.main()
