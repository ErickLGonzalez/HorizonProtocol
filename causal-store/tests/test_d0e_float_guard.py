"""D0-E: the exactness boundary is enforced, not merely claimed. [SOUND]

docs/d0-spec.md section 4 claims `ordering.py`/`geometry.py` are float-guard
clean and that `store.py`'s `coordination_free_rate()` is the only float/
division in the package, explicitly kept off the trusted admissibility/
ordering path. This applies the same AST walk HorizonProtocol's own
`tests/test_float_guard.py` runs against the shared kernel, scoped to
causal-store's own copy - this package deliberately vendors `geometry.py`
rather than importing `horizon.geometry` (see its own docstring), so it
needs its own guard rather than relying on the top-level one.
"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRUSTED_MODULES = ["causalstore/geometry.py", "causalstore/ordering.py"]
# store.py's coordination_free_rate() docstring names this its one documented
# reporting-metric exception (see causalstore/store.py). Kept as an exact
# line number, not a broad module exemption, so any OTHER float creeping into
# store.py's write()/read() decision path still fails this test.
EXEMPT_STORE_LINE = 200


class FloatFinder(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_Constant(self, node):
        if isinstance(node.value, float):
            self.violations.append((node.lineno, "float literal", repr(node.value)))
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Div):
            self.violations.append((node.lineno, "true division (/)", ""))
        self.generic_visit(node)

    def visit_Call(self, node):
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name in ("sqrt", "float"):
            self.violations.append((node.lineno, f"{name}(...) call", ""))
        self.generic_visit(node)


def _scan(path):
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    finder = FloatFinder()
    finder.visit(tree)
    return finder.violations


class TestFloatGuard(unittest.TestCase):
    def test_ordering_and_geometry_contain_no_floats(self):
        for rel_path in TRUSTED_MODULES:
            violations = _scan(os.path.join(ROOT, rel_path))
            self.assertEqual(violations, [],
                             f"{rel_path} contains float-guard violations: "
                             f"{violations}")

    def test_store_isolates_its_floats_to_the_documented_reporting_metric(self):
        # store.py is allowed float/division violations on exactly ONE line:
        # coordination_free_rate()'s `return (... / t) if t else 0.0`, its
        # documented reporting metric, explicitly annotated in the module as
        # outside the trusted path. A violation on any OTHER line is a real
        # exactness regression on the trusted write()/read() decision path.
        violations = _scan(os.path.join(ROOT, "causalstore", "store.py"))
        stray = [v for v in violations if v[0] != EXEMPT_STORE_LINE]
        self.assertEqual(stray, [],
                         f"store.py contains a float-guard violation outside "
                         f"the documented coordination_free_rate() line "
                         f"({EXEMPT_STORE_LINE}): {stray}")
        self.assertTrue(violations,
                        f"expected the documented violation at line "
                        f"{EXEMPT_STORE_LINE} to still be present - if "
                        f"coordination_free_rate() was rewritten to be exact, "
                        f"remove this exemption entirely instead of leaving "
                        f"stale cover")


if __name__ == "__main__":
    unittest.main()
