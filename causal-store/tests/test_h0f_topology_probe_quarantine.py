"""H-F: the LIVE half of topology_probe.py (probe_rtt/probe_topology,
real network I/O) is never called from the deterministic/testable path -
only local_topology() may be, mirroring horizon/capture.py's own
quarantine discipline (see tests/test_h5b_replay_pass.py). [SOUND]
"""
import ast
import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUARANTINED_NAMES = {"probe_rtt", "probe_topology"}


def _referenced_names(path):
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


class TestTopologyProbeQuarantine(unittest.TestCase):
    def test_live_probe_functions_never_referenced_outside_their_own_module(self):
        offenders = []
        for path in (glob.glob(os.path.join(ROOT, "tests", "*.py"))
                     + glob.glob(os.path.join(ROOT, "scripts", "*.py"))
                     + glob.glob(os.path.join(ROOT, "benchmark_harness", "*.py"))
                     + glob.glob(os.path.join(ROOT, "benchmark_harness", "adapters", "*.py"))):
            if os.path.basename(path) == "topology_probe.py":
                continue  # the module defines these names; that's not a reference
            if QUARANTINED_NAMES & _referenced_names(path):
                offenders.append(path)
        self.assertEqual(offenders, [],
                         f"LIVE topology_probe functions referenced outside "
                         f"topology_probe.py: {offenders}")

    def test_local_topology_is_deterministic_and_labeled(self):
        from benchmark_harness.topology_probe import local_topology
        a = local_topology(["us-east", "eu-west"])
        b = local_topology(["us-east", "eu-west"])
        self.assertEqual(a, b)
        self.assertEqual(a["mode"], "LOCAL_LOOPBACK")
        for r in a["results"].values():
            self.assertEqual(r["rtt_ns_median"], 0)


if __name__ == "__main__":
    unittest.main()
