"""Float guard: the central method claim - "no floats in any security
gate" - is enforced by CI, not merely reviewed. [SOUND]

Walks every listed trusted-path module's AST and fails if it finds a
float literal, `math.sqrt`/bare `sqrt`, a `float(...)` call, or true
division (`/`, as opposed to floor division `//`) anywhere. HEURISTIC
modules where floats are the documented, deliberate point (geodesy in
`horizon/geo_frame.py`, live network timing in `horizon/capture.py` and
`horizon/h6_capture.py`, and the world-model simulators/fixture builders
that derive frozen constants once via float math) are explicitly excluded
below, by name, with the reason - this is a documented exception list,
not a silent skip.
"""
import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every module on the trusted (gate-deciding) path. Must contain ZERO
# floats, ZERO true-division, ZERO math.sqrt/float() calls.
TRUSTED_MODULES = [
    "horizon/__init__.py",
    "mnemesis/__init__.py",
    "horizon/geometry.py",
    "horizon/worldline.py",
    "horizon/occultation.py",
    "horizon/light_delay.py",
    "horizon/uncertainty.py",
    "horizon/two_floor.py",
    "horizon/proper_time.py",
    "horizon/reconcile.py",
    "horizon/events.py",
    "horizon/certificate.py",
    "horizon/ledger.py",
    "horizon/stations.py",
    "horizon/commitment.py",
    "horizon/distance.py",
    "horizon/beacon.py",
    "horizon/measure.py",
    "horizon/geo_registry.py",
    "horizon/geo_fixtures.py",
    "horizon/latency_gate.py",
    "horizon/beq.py",
    "horizon/deepspace_protocol.py",
    "horizon/signed_capture.py",
    "horizon/capture_verify.py",
    "horizon/build_frame.py",
    "horizon/reachability_cache.py",
    "horizon/edge_claims.py",
    "mnemesis/memory.py",
    "mnemesis/vclock.py",
]

# Documented exceptions: floats are the deliberate point of these modules
# (irreducibly-float geodesy, or live network timing), and none of them
# is ever imported by a trusted verifier (asserted elsewhere by each
# sprint's own "verifier is standalone" tests).
EXEMPT_MODULES = {
    "horizon/deepspace.py": "one_way_light_time_ns itself is exact integer "
                            "(delegates to geometry.min_light_time_ns); "
                            "light_time_table()'s seconds/minutes fields are "
                            "float for human-readable certificate display "
                            "only, never fed back into a gate decision",
    "horizon/geo_frame.py": "WGS84 ellipsoid -> ECEF -> ENU geodesy; float "
                            "math runs once at frame-construction time, "
                            "then every coordinate is quantized to an "
                            "integer nm lattice - see docs/h6-spec.md",
    "horizon/fixtures.py": "llh_to_enu_nm is a float-based derivation used "
                           "once, offline, to compute the frozen integer "
                           "constants in NODES_NM - see horizon/fixtures.py's "
                           "own docstring",
    "horizon/capture.py": "HEURISTIC, quarantined live NTP/HTTP timing; "
                          "never imported by a verifier",
    "horizon/h6_capture.py": "HEURISTIC, quarantined live NTP timing; "
                             "never imported by a verifier",
    "horizon/beacon_sim.py": "HEURISTIC world-model simulator",
    "horizon/commit_sim.py": "HEURISTIC world-model simulator",
    "horizon/db_sim.py": "HEURISTIC world-model simulator",
    "horizon/simulate.py": "HEURISTIC world-model simulator",
    "horizon/qubit_sim.py": "HEURISTIC, quarantined deterministic qubit-"
                            "measurement stand-in; never imported by a "
                            "verifier (test H7-D asserts this)",
    "horizon/quantum_interface.py": "documented interface/contract only "
                                    "([SPEC], not [SOUND]) - no gate "
                                    "arithmetic; contains no floats today "
                                    "but is not on the numeric gate path",
    "redteam/__init__.py": "package metadata only, no arithmetic",
    "redteam/attacks.py": "attacker code, not a gate: RT-A deliberately "
                          "uses a DIFFERENT algorithm (Decimal-based real "
                          "sqrt) from the exact-integer kernel to "
                          "cross-check it from outside - see the module "
                          "docstring",
}

# Documented LINE-LEVEL exceptions within otherwise-trusted modules: a
# module can be mostly gate logic with a few isolated reporting-only float
# conversions. Listed by exact (path, lineno) so the exception can never
# silently widen to cover a future line - each entry names the reason.
EXEMPT_LINES = {
    ("horizon/beq.py", 59): "adversary_bound_float: a float rendering of "
                            "the exact Fraction `bound`, for certificate "
                            "readability only - the actual soundness "
                            "decision (meets = bound <= target) above this "
                            "line is exact Fraction comparison",
    ("horizon/beq.py", 60): "target_soundness_float: same as above, for "
                            "`target`",
}


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


def _scan(path, rel_path):
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    finder = FloatFinder()
    finder.visit(tree)
    return [v for v in finder.violations if (rel_path, v[0]) not in EXEMPT_LINES]


class TestFloatGuard(unittest.TestCase):
    def test_every_repo_python_file_is_classified(self):
        # every .py file under horizon/ and mnemesis/ must be either on the
        # trusted list (checked below) or on the documented exemption list -
        # a new file silently falling into neither would defeat the guard
        found = set()
        for pkg in ("horizon", "mnemesis", "redteam"):
            for fn in sorted(os.listdir(os.path.join(ROOT, pkg))):
                if fn.endswith(".py"):
                    found.add(f"{pkg}/{fn}")
        classified = set(TRUSTED_MODULES) | set(EXEMPT_MODULES)
        unclassified = found - classified
        self.assertEqual(unclassified, set(),
                         f"new module(s) not classified as trusted or "
                         f"exempt in tests/test_float_guard.py: {unclassified}")

    def test_trusted_modules_contain_no_floats(self):
        for rel_path in TRUSTED_MODULES:
            path = os.path.join(ROOT, rel_path)
            violations = _scan(path, rel_path)
            self.assertEqual(violations, [],
                             f"{rel_path} contains float-guard violations: "
                             f"{violations}")

    def test_exempt_modules_are_documented_and_exist(self):
        for rel_path, reason in EXEMPT_MODULES.items():
            self.assertTrue(reason, f"{rel_path} exemption has no reason recorded")
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel_path)),
                            f"exempt module {rel_path} no longer exists - "
                            f"remove its stale exemption entry")

    def test_exempt_lines_are_documented_and_still_contain_a_float(self):
        # a line-level exception that no longer matches a real violation
        # (e.g. the code around it changed) is stale and must be removed,
        # not left as unused cover for a future, different violation
        by_file = {}
        for (rel_path, lineno), reason in EXEMPT_LINES.items():
            self.assertTrue(reason, f"{rel_path}:{lineno} exemption has no reason")
            by_file.setdefault(rel_path, set()).add(lineno)
        for rel_path, linenos in by_file.items():
            path = os.path.join(ROOT, rel_path)
            with open(path) as f:
                tree = ast.parse(f.read(), filename=path)
            finder = FloatFinder()
            finder.visit(tree)
            found_lines = {v[0] for v in finder.violations}
            stale = linenos - found_lines
            self.assertEqual(stale, set(),
                             f"stale EXEMPT_LINES entries in {rel_path} "
                             f"(no longer match a float-guard violation): "
                             f"{stale}")


if __name__ == "__main__":
    unittest.main()
