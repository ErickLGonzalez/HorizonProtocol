"""D0-F: the vendored geometry.py kernel has not silently drifted. [SOUND]

causal-store deliberately vendors a frozen copy of HorizonProtocol's exact
light-cone kernel rather than importing `horizon.geometry` at runtime (see
`causalstore/geometry.py`'s docstring and docs/d0-spec.md section 2: shared
BY VALUE, not by coupling - the engine must remain importable and correct
even if the `horizon` package is absent). But "shared by value" only holds
if the value stays identical over time. This is an offline, CI-time-only
check - never imported by the engine itself, so it adds no runtime coupling
- that the vendored copy is still byte-for-byte identical to
`horizon/geometry.py`, catching silent kernel drift between the two copies.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(ROOT)


class TestGeometryHash(unittest.TestCase):
    def test_vendored_geometry_matches_horizon_geometry_byte_for_byte(self):
        vendored = os.path.join(ROOT, "causalstore", "geometry.py")
        upstream = os.path.join(REPO_ROOT, "horizon", "geometry.py")
        self.assertTrue(os.path.isfile(upstream),
                        "horizon/geometry.py not found at the expected "
                        "sibling path - this check assumes causal-store "
                        "lives alongside horizon/ in the same repo")
        with open(vendored, "rb") as f:
            vendored_bytes = f.read()
        with open(upstream, "rb") as f:
            upstream_bytes = f.read()
        self.assertEqual(vendored_bytes, upstream_bytes,
                         "causalstore/geometry.py has drifted from "
                         "horizon/geometry.py - the vendored kernel copy "
                         "must stay byte-identical (see module docstring)")


if __name__ == "__main__":
    unittest.main()
