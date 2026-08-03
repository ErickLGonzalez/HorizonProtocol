"""Kernel consolidation: there is exactly ONE light-cone admissibility
kernel in this repository, and every overlay imports it rather than
vendoring a copy. [SOUND]

H6 and MNX1 were each delivered as standalone overlay packages that
vendored their own byte-identical copy of `horizon/geometry.py` (and, for
MNX1, `horizon/ledger.py`); those vendored copies were deleted at
integration time and every import routed to the shared `horizon` package
(see docs/h6-spec.md, docs/mnemesis-convergence.md). This test makes that
a permanent, CI-enforced invariant rather than a one-time cleanup: a
future overlay that reintroduces a vendored kernel copy - even one that
currently agrees with the original - is silent drift risk waiting to
happen the next time only one copy gets patched.
"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The one canonical location for each kernel primitive.
CANONICAL_DEFINITIONS = {
    "causally_admissible": "horizon/geometry.py",
    "admissibility_witness": "horizon/geometry.py",
    "min_light_time_ns": "horizon/geometry.py",
    "dist2": "horizon/geometry.py",
    "CausalLedger": "horizon/ledger.py",
}


def _all_py_files():
    paths = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in
                      (".git", "__pycache__", "node_modules")]
        for fn in filenames:
            if fn.endswith(".py"):
                paths.append(os.path.join(dirpath, fn))
    return paths


def _top_level_defs(path):
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


class TestKernelConsolidation(unittest.TestCase):
    def test_no_duplicate_kernel_definitions(self):
        offenders = {}
        for path in _all_py_files():
            rel = os.path.relpath(path, ROOT)
            defs = _top_level_defs(path)
            for name, canonical_rel in CANONICAL_DEFINITIONS.items():
                if name in defs and rel != canonical_rel:
                    offenders.setdefault(name, []).append(rel)
        self.assertEqual(offenders, {},
                         f"kernel primitive(s) redefined outside their "
                         f"canonical module (vendored copy?): {offenders}")

    def test_no_file_named_geometry_or_ledger_outside_horizon(self):
        # a vendored copy is most often reintroduced under the same
        # filename in a new package - catch that shape even before
        # checking definitions
        offenders = []
        for path in _all_py_files():
            rel = os.path.relpath(path, ROOT)
            base = os.path.basename(rel)
            if base in ("geometry.py", "ledger.py") and not rel.startswith("horizon/"):
                offenders.append(rel)
        self.assertEqual(offenders, [],
                         f"file(s) named like a kernel module outside "
                         f"horizon/: {offenders}")


if __name__ == "__main__":
    unittest.main()
