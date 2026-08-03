"""H4-B: binding, embedded cone certificates, standalone verification. [SOUND]"""
import hashlib
import unittest
from horizon.beacon import verify_beacon, xor_blocks
from horizon.beacon_sim import build_full_beacon, derive_block
from horizon.certificate import verify_certificate


class TestBeaconBinding(unittest.TestCase):
    def setUp(self):
        self.cert, self.reg = build_full_beacon()

    def test_beacon_verifies_pass(self):
        res = verify_beacon(self.cert, self.reg)
        self.assertEqual(res["verdict"], "PASS")
        self.assertTrue(all(w["spacelike"] for w in res["pairwise"].values()))
        self.assertEqual(set(res["cone_certificate_verdicts"].values()), {"PASS"})

    def test_each_block_bound_and_cone_cert_passes_independently(self):
        for b in self.cert["per_block"]:
            blk = bytes.fromhex(b["block_hex"])
            self.assertEqual(hashlib.sha256(blk).hexdigest(), b["block_sha256"])
            inner = verify_certificate(b["cone_certificate"], self.reg)
            self.assertEqual(inner["verdict"], "PASS", b["emitter_id"])

    def test_beacon_value_is_xor_of_blocks(self):
        blocks = [bytes.fromhex(b["block_hex"]) for b in self.cert["per_block"]]
        self.assertEqual(xor_blocks(blocks).hex(), self.cert["beacon_value_hex"])
        # and matches direct derivation from the frozen seed
        derived = [derive_block("H4-FROZEN-SEED-v1", b["emitter_id"])
                   for b in self.cert["per_block"]]
        self.assertEqual(xor_blocks(derived).hex(), self.cert["beacon_value_hex"])

    def test_verifier_is_standalone(self):
        import inspect
        import horizon.beacon as bm
        src = inspect.getsource(bm)
        self.assertNotIn("beacon_sim", src)
        self.assertNotIn("simulate", src)
        import horizon.certificate as cm
        self.assertNotIn("simulate", inspect.getsource(cm))

    def test_determinism(self):
        again, _ = build_full_beacon()
        self.assertEqual(self.cert, again)


if __name__ == "__main__":
    unittest.main()
