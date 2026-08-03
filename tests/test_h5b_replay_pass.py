"""H5-B: replay PASS over the committed fixture; standalone verifier. [SOUND]"""
import json
import os
import unittest

from horizon.fixtures import NODE_U_NS, build_registry
from horizon.measure import verify_measured_certificate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(ROOT, "data", "h5_fixture_capture.json")


class TestReplayPass(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE_PATH) as f:
            self.cert = json.load(f)
        self.registry = build_registry()

    def test_committed_fixture_is_synthetic_consistent(self):
        self.assertEqual(self.cert["fixture_origin"], "SYNTHETIC_CONSISTENT")

    def test_replay_all_nodes_admitted(self):
        res = verify_measured_certificate(self.cert, self.registry)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(set(res["per_node"]), set(NODE_U_NS))
        for nid, w in res["per_node"].items():
            self.assertEqual(w["verdict"], "ADMITTED", nid)

    def test_declared_uncertainty_recorded_per_node(self):
        for nid, params in self.cert["node_params"].items():
            self.assertEqual(params["u_ns"], NODE_U_NS[nid])

    def test_determinism_across_regeneration(self):
        from horizon.fixtures import build_synthetic_consistent_capture
        again, _ = build_synthetic_consistent_capture()
        self.assertEqual(self.cert, again)

    def test_verifier_is_standalone(self):
        # trusted-path hygiene: check actual import statements (the module
        # docstring legitimately *names* fixtures/capture in prose)
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

    def test_capture_module_never_imported_by_trusted_or_test_code(self):
        import ast
        import glob
        offenders = []
        for path in (glob.glob(os.path.join(ROOT, "horizon", "*.py"))
                     + glob.glob(os.path.join(ROOT, "scripts", "*.py"))
                     + glob.glob(os.path.join(ROOT, "tests", "*.py"))):
            if os.path.basename(path) == "capture.py":
                continue
            with open(path) as f:
                tree = ast.parse(f.read(), filename=path)
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                if any("capture" in n for n in names):
                    offenders.append(path)
        self.assertEqual(offenders, [],
                         f"horizon.capture imported outside its own module: {offenders}")


if __name__ == "__main__":
    unittest.main()
