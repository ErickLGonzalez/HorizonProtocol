"""H6-A: real geography -> exact nm lattice. [SOUND output, HEURISTIC geodesy]"""
import math
import unittest

from horizon.geometry import dist2
from horizon.geo_registry import load_geo_registry


class TestFrame(unittest.TestCase):
    def setUp(self):
        self.frame, self.registry, self.node_llh, self.node_u_ns, self.spec = \
            load_geo_registry()

    def test_origin_maps_to_near_zero(self):
        # us-east-1 IS the frame origin -> ENU (0,0,0) within quantization
        p = self.registry["us-east-1"].pos_nm
        self.assertLess(max(abs(c) for c in p), 100)  # < 100 nm from origin

    def test_positions_are_integers(self):
        for nid, st in self.registry.items():
            for c in st.pos_nm:
                self.assertIsInstance(c, int)

    def test_intercontinental_distance_plausible(self):
        p0 = self.registry["us-east-1"].pos_nm
        d_km = math.isqrt(dist2(p0, self.registry["ap-southeast-1"].pos_nm)) / 1e12
        # Virginia to Singapore chord ~ 12,000 km, well over 10,000
        self.assertGreater(d_km, 10_000)
        self.assertLess(d_km, 13_000)

    def test_deterministic(self):
        _, reg2, _, _, _ = load_geo_registry()
        self.assertEqual({n: st.pos_nm for n, st in self.registry.items()},
                         {n: st.pos_nm for n, st in reg2.items()})

    def test_quantization_recorded(self):
        meta = self.frame.metadata()
        self.assertEqual(meta["quantization_nm"], self.spec.get("quantization_nm", 1))
        self.assertIn("geodesy", meta)


if __name__ == "__main__":
    unittest.main()
