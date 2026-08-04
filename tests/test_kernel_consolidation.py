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

ONE documented, narrow exception: `causal-store/causalstore/geometry.py`.
Unlike H6/MNX1 (overlays living inside this same repo/process, where
importing `horizon.geometry` costs nothing), causal-store's own design
(`docs/distributed-system-design.md` section 4.2, "shared by value, not
by coupling") deliberately vendors a frozen copy so the engine stays
importable and correct in contexts where the `horizon` package isn't
present at all - a stated architecture goal, not an oversight. This does
NOT reopen the "even one that currently agrees is still a risk" concern
above: `test_no_drift_in_documented_vendored_copies` below re-checks the
byte-for-byte hash on every run of THIS suite (not just causal-store's own
D0-F gate), so drift is caught here too, unconditionally.
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

# Documented, narrow exceptions to both checks below - see module docstring.
# Each entry names the canonical file it must stay byte-identical to;
# `test_no_drift_in_documented_vendored_copies` enforces that identity.
DOCUMENTED_VENDORED_COPIES = {
    "causal-store/causalstore/geometry.py": "horizon/geometry.py",
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
            if rel in DOCUMENTED_VENDORED_COPIES:
                continue
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
            if rel in DOCUMENTED_VENDORED_COPIES:
                continue
            base = os.path.basename(rel)
            if base in ("geometry.py", "ledger.py") and not rel.startswith("horizon/"):
                offenders.append(rel)
        self.assertEqual(offenders, [],
                         f"file(s) named like a kernel module outside "
                         f"horizon/: {offenders}")

    def test_no_drift_in_documented_vendored_copies(self):
        # the ONE thing that makes DOCUMENTED_VENDORED_COPIES safe: every
        # exempted copy must still be byte-for-byte identical to its
        # canonical source, checked unconditionally on every run of this
        # suite - not only when causal-store's own D0-F gate happens to run.
        for vendored_rel, canonical_rel in DOCUMENTED_VENDORED_COPIES.items():
            vendored_path = os.path.join(ROOT, vendored_rel)
            canonical_path = os.path.join(ROOT, canonical_rel)
            self.assertTrue(os.path.isfile(vendored_path),
                            f"documented vendored copy {vendored_rel} no "
                            f"longer exists - remove its stale exception")
            with open(vendored_path, "rb") as f:
                vendored_bytes = f.read()
            with open(canonical_path, "rb") as f:
                canonical_bytes = f.read()
            self.assertEqual(vendored_bytes, canonical_bytes,
                             f"{vendored_rel} has drifted from its "
                             f"canonical source {canonical_rel} - a "
                             f"documented vendored copy must stay exact")


if __name__ == "__main__":
    unittest.main()
