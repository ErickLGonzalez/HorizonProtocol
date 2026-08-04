"""H7-A: real Earth-Mars light-time geometry (exact). [SOUND]"""
import unittest
from horizon.deepspace import (one_way_light_time_ns, light_time_table,
                               EARTH_MARS_MIN_M, EARTH_MARS_MAX_M, C_EFF_VACUUM)
from horizon.geometry import C_NM_PER_NS, min_light_time_ns


class TestDeepSpace(unittest.TestCase):
    def test_vacuum_c_eff_is_unity(self):
        self.assertEqual(C_EFF_VACUUM, (1, 1))

    def test_closest_owlt_about_3_min(self):
        owlt = one_way_light_time_ns(EARTH_MARS_MIN_M)
        minutes = owlt / 1e9 / 60
        self.assertGreater(minutes, 2.9)
        self.assertLess(minutes, 3.2)

    def test_farthest_owlt_about_22_min(self):
        owlt = one_way_light_time_ns(EARTH_MARS_MAX_M)
        minutes = owlt / 1e9 / 60
        self.assertGreater(minutes, 22.0)
        self.assertLess(minutes, 22.6)

    def test_light_time_is_exact_lower_bound(self):
        d = EARTH_MARS_MIN_M
        owlt = one_way_light_time_ns(d)
        d_nm = d * 1_000_000_000
        self.assertGreaterEqual(C_NM_PER_NS * owlt, d_nm)
        self.assertLess(C_NM_PER_NS * (owlt - 1), d_nm)

    def test_table_monotone(self):
        rows = light_time_table()
        owlts = [r["one_way_light_time_ns"] for r in rows]
        self.assertEqual(owlts, sorted(owlts))

    def test_delegates_to_geometry_kernel(self):
        # one_way_light_time_ns must agree exactly with the general 3-D
        # kernel it delegates to, not a separate reimplementation
        d = EARTH_MARS_MIN_M
        d_nm = d * 1_000_000_000
        self.assertEqual(one_way_light_time_ns(d),
                         min_light_time_ns((0, 0, 0), (d_nm, 0, 0)))


if __name__ == "__main__":
    unittest.main()
