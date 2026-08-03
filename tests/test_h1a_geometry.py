"""H1-A: exact geometry kernel. [SOUND, E0]"""
import unittest
from horizon.geometry import (C_NM_PER_NS, dist2, causally_admissible,
                              min_light_time_ns, admissibility_witness)


class TestGeometry(unittest.TestCase):
    def test_c_is_exact_integer(self):
        self.assertEqual(C_NM_PER_NS, 299_792_458)

    def test_dist2_pythagorean(self):
        self.assertEqual(dist2((0, 0, 0), (3, 4, 0)), 25)

    def test_null_ray_exactly_admissible(self):
        # one lattice light-step along x: d = c * 1ns exactly -> admissible
        p2 = (C_NM_PER_NS, 0, 0)
        self.assertTrue(causally_admissible(0, (0, 0, 0), 1, p2))

    def test_one_nm_beyond_null_ray_rejected(self):
        p2 = (C_NM_PER_NS + 1, 0, 0)
        self.assertFalse(causally_admissible(0, (0, 0, 0), 1, p2))

    def test_negative_dt_rejected(self):
        self.assertFalse(causally_admissible(5, (0, 0, 0), 4, (0, 0, 0)))

    def test_min_light_time_exact_boundary(self):
        p2 = (C_NM_PER_NS, 0, 0)
        self.assertEqual(min_light_time_ns((0, 0, 0), p2), 1)
        p3 = (C_NM_PER_NS + 1, 0, 0)
        self.assertEqual(min_light_time_ns((0, 0, 0), p3), 2)
        self.assertEqual(min_light_time_ns((0, 0, 0), (0, 0, 0)), 0)

    def test_min_light_time_is_minimal_and_sufficient(self):
        # 10 m in nm, off-axis
        p2 = (6_000_000_000, 8_000_000_000, 0)
        dt = min_light_time_ns((0, 0, 0), p2)
        self.assertTrue((C_NM_PER_NS * dt) ** 2 >= dist2((0, 0, 0), p2))
        if dt > 0:
            self.assertTrue((C_NM_PER_NS * (dt - 1)) ** 2 < dist2((0, 0, 0), p2))

    def test_witness_records_exact_integers(self):
        w = admissibility_witness(0, (0, 0, 0), 1, (C_NM_PER_NS + 1, 0, 0))
        self.assertFalse(w["admissible"])
        self.assertEqual(w["lhs_c_dt_squared"], C_NM_PER_NS ** 2)
        self.assertEqual(w["rhs_dist_squared_nm2"], (C_NM_PER_NS + 1) ** 2)
        self.assertLess(w["lhs_c_dt_squared"], w["rhs_dist_squared_nm2"])


if __name__ == "__main__":
    unittest.main()
