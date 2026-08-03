"""H4-D: negative controls - timelike emitter, tamper, duplicates,
failing inner certificate. [SOUND]"""
import copy
import unittest
from horizon.beacon import T_EMIT_NS, verify_beacon, xor_blocks
from horizon.beacon_sim import (build_emission_entry, build_full_beacon,
                                build_registry)
from horizon.beacon import EMITTERS
from horizon.stations import demo_registry


class TestNegativeControls(unittest.TestCase):
    def setUp(self):
        self.cert, self.reg = build_full_beacon()

    def _with_extra_entry(self, entry):
        entries = copy.deepcopy(self.cert["per_block"])
        entries.append({"emitter_id": entry["emitter_id"],
                        "pos_nm": entry["pos_nm"],
                        "t_emit_ns": entry["t_emit_ns"],
                        "block_hex": entry["block_hex"],
                        "block_sha256": __import__("hashlib").sha256(
                            bytes.fromhex(entry["block_hex"])).hexdigest(),
                        "cone_certificate": entry["cone_certificate"]})
        blocks = [bytes.fromhex(b["block_hex"]) for b in entries]
        return {"type": "beacon_certificate", "version": "1",
                "per_block": entries,
                "beacon_value_hex": xor_blocks(blocks).hex()}

    def test_timelike_fourth_emitter_rejected(self):
        # E4 = E1 + (1000,0,0) nm, emitting 10 ms after T_EMIT: timelike to E1
        e4_pos = (EMITTERS["E1"][0] + 1000, EMITTERS["E1"][1], EMITTERS["E1"][2])
        extra_specs = [("STN-E4-0", (e4_pos[0] + 100_000_000_000, e4_pos[1], e4_pos[2]), 3)]
        reg = dict(self.reg)
        reg.update(demo_registry(extra_specs))
        entry = build_emission_entry("E4", e4_pos, T_EMIT_NS + 10_000_000,
                                     demo_registry(extra_specs))
        cert = self._with_extra_entry(entry)
        res = verify_beacon(cert, reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "pairwise_spacelike")
        self.assertEqual(res["witness"]["pair"], "E1|E4")
        self.assertTrue(res["witness"]["exact_witness"]["admissible"])

    def test_tampered_block_rejected(self):
        cert = copy.deepcopy(self.cert)
        blk = bytearray(bytes.fromhex(cert["per_block"][1]["block_hex"]))
        blk[0] ^= 0xFF  # flip one byte after binding
        cert["per_block"][1]["block_hex"] = bytes(blk).hex()
        res = verify_beacon(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "block_binding")
        self.assertEqual(res["witness"]["emitter_id"],
                         cert["per_block"][1]["emitter_id"])

    def test_duplicate_source_rejected(self):
        cert = copy.deepcopy(self.cert)
        cert["per_block"][2] = copy.deepcopy(cert["per_block"][0])  # E1 twice
        res = verify_beacon(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "distinct_sources")

    def test_failing_inner_cone_certificate_propagates(self):
        # reuse H1-E's FTL forgery: a receipt 1 ns earlier than light permits
        cert = copy.deepcopy(self.cert)
        rec = cert["per_block"][0]["cone_certificate"]["receipts"][0]
        sid = rec["body"]["station_id"]
        st = self.reg[sid]
        forged = st.sign_receipt(rec["body"]["payload_hash"],
                                 rec["body"]["recv_time_ns"] - st.proc_delay_ns - 1)
        cert["per_block"][0]["cone_certificate"]["receipts"][0] = forged
        res = verify_beacon(cert, self.reg)
        self.assertEqual(res["verdict"], "REJECTED")
        self.assertEqual(res["witness"]["gate"], "cone_certificate")
        inner = res["witness"]["inner_witness"]
        self.assertEqual(inner["gate"], "light_cone")
        self.assertFalse(inner["exact_witness"]["admissible"])


if __name__ == "__main__":
    unittest.main()
