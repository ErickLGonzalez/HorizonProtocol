"""H6-B: replay the consistent fixture over real geography -> PASS. [SOUND]"""
import json
import os
import unittest

from horizon.geo_registry import load_geo_registry, trusted_node_params
from horizon.measure import verify_measured_certificate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(ROOT, "data", "h6_fixture_capture.json")


class TestReplay(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH) as f:
            self.cert = json.load(f)
        _, self.registry, _, node_u_ns, _ = load_geo_registry()
        self.node_params = trusted_node_params(node_u_ns)

    def test_committed_fixture_is_synthetic_consistent(self):
        self.assertEqual(self.cert["fixture_origin"], "SYNTHETIC_CONSISTENT")

    def test_certificate_does_not_carry_its_own_gate_parameters(self):
        self.assertNotIn("node_params", self.cert)

    def test_replay_all_nodes_admitted(self):
        res = verify_measured_certificate(self.cert, self.registry, self.node_params,
                                          required_station_ids=set(self.registry))
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(set(res["per_node"]), set(self.registry))
        for nid, w in res["per_node"].items():
            self.assertEqual(w["verdict"], "ADMITTED", nid)

    def test_determinism_across_regeneration(self):
        from horizon.geo_fixtures import build_synthetic_consistent_capture
        again, _, _ = build_synthetic_consistent_capture()
        self.assertEqual(self.cert, again)

    def test_verifier_is_standalone(self):
        import ast
        import inspect
        import horizon.measure as m
        tree = ast.parse(inspect.getsource(m))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any("fixtures" in n for n in imported), imported)
        self.assertFalse(any("capture" in n for n in imported), imported)
        self.assertFalse(any("simulate" in n for n in imported), imported)
        self.assertFalse(any("geo_" in n for n in imported), imported)


if __name__ == "__main__":
    unittest.main()
