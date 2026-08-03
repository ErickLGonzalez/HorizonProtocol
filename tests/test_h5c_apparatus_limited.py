"""H5-C: apparatus-limited control - refuse to certify a marginal
measurement, even though every other node is cleanly ADMITTED. [SOUND]"""
import json
import os
import unittest

from horizon.fixtures import build_registry, trusted_node_params
from horizon.measure import verify_measured_certificate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(ROOT, "data", "h5_fixture_marginal.json")


class TestApparatusLimited(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH) as f:
            self.cert = json.load(f)
        self.registry = build_registry()
        self.node_params = trusted_node_params()

    def test_marginal_fixture_is_synthetic_consistent(self):
        self.assertEqual(self.cert["fixture_origin"], "SYNTHETIC_CONSISTENT")

    def test_one_node_lands_between_the_two_floors(self):
        res = verify_measured_certificate(self.cert, self.registry,
                                          self.node_params)
        marginal = [nid for nid, w in res["per_node"].items()
                   if w["verdict"] == "APPARATUS_LIMITED"]
        self.assertEqual(len(marginal), 1)
        w = res["per_node"][marginal[0]]
        self.assertGreaterEqual(w["dt_adjusted_ns"], w["vacuum_floor_ns"])
        self.assertLess(w["dt_adjusted_ns"], w["typical_floor_ns"])

    def test_aggregate_is_apparatus_limited_never_pass(self):
        res = verify_measured_certificate(self.cert, self.registry,
                                          self.node_params)
        self.assertEqual(res["verdict"], "APPARATUS_LIMITED")
        self.assertNotEqual(res["verdict"], "PASS")
        self.assertEqual(res["witness"]["gate"], "budget")
        self.assertIn("apparatus_limited_nodes", res["witness"])

    def test_other_nodes_still_individually_admitted(self):
        res = verify_measured_certificate(self.cert, self.registry,
                                          self.node_params)
        admitted = [nid for nid, w in res["per_node"].items()
                   if w["verdict"] == "ADMITTED"]
        self.assertEqual(len(admitted), len(res["per_node"]) - 1)


if __name__ == "__main__":
    unittest.main()
