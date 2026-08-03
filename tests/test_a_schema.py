"""A: certificate schema validator gate. [SOUND]

Imports `scripts/validate_certificates.py` directly (it lives outside any
package) and asserts it exits 0 over the committed certificates.
"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATOR_PATH = os.path.join(ROOT, "scripts", "validate_certificates.py")


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_certificates",
                                                   VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCertificateSchema(unittest.TestCase):
    def test_validator_passes_over_committed_certificates(self):
        module = _load_validator()
        self.assertEqual(module.main(), 0)

    def test_validator_catches_a_broken_certificate(self):
        # negative control on the validator itself: a certificate missing
        # mandatory fields must produce a nonempty error list, not
        # silently validate
        import json
        import tempfile
        module = _load_validator()
        broken = {"certificate_version": "1"}  # nearly everything missing
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(broken, f)
            path = f.name
        try:
            errors = module.validate_certificate(path)
        finally:
            os.unlink(path)
        self.assertTrue(errors)
        self.assertTrue(any("missing mandatory field" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
