"""Causal-disjointness independence beacons. [SOUND]

Combine entropy blocks only when their emission events are pairwise
spacelike separated (both causal directions inadmissible, decided
exactly), each block bound by hash to its emission event, and each
emission event carrying an H1 cone certificate that independently
verifies PASS.

FIREWALL: this module certifies independence BY CAUSAL STRUCTURE only.
It never certifies statistical randomness quality; the byte-balance
smoke test lives in the HEURISTIC world-model module, not here.

Trusted path: this module imports only the H1 kernel (`geometry`,
`events`, `ledger`, `certificate`). It never imports a world-model
module; test H4-B asserts this.
"""
import hashlib

from .certificate import verify_certificate
from .events import event_hash
from .geometry import admissibility_witness
from .ledger import CausalLedger

# ---- frozen parameters (H4) -------------------------------------------------
E1 = (0, 0, 0)
E2 = (50_000_000_000_000, 0, 0)
E3 = (0, 50_000_000_000_000, 0)
EMITTERS = {"E1": E1, "E2": E2, "E3": E3}
T_EMIT_NS = 1_000_000
BLOCK_LEN = 32
SEED_H4 = "H4-FROZEN-SEED-v1"
MIN_SOURCES = len(EMITTERS)  # frozen construction requires all 3 independent emitters


# ---- pairwise spacelike gate ------------------------------------------------
def pairwise_spacelike_witnesses(emissions: dict) -> dict:
    """For every unordered pair of emission events, both directed
    admissibility witnesses plus the ledger's concurrency verdict.

    emissions: {emitter_id: {"time_ns": int, "pos_nm": tuple}}.
    Uses CausalLedger.concurrent as the authoritative predicate.
    """
    ledger = CausalLedger()
    for eid in sorted(emissions):
        ledger.add_event(eid, emissions[eid]["time_ns"], emissions[eid]["pos_nm"])
    out = {}
    ids = sorted(emissions)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ea, eb = emissions[a], emissions[b]
            w_ab = admissibility_witness(ea["time_ns"], ea["pos_nm"],
                                         eb["time_ns"], eb["pos_nm"])
            w_ba = admissibility_witness(eb["time_ns"], eb["pos_nm"],
                                         ea["time_ns"], ea["pos_nm"])
            out[f"{a}|{b}"] = {
                "witness_forward": w_ab,
                "witness_backward": w_ba,
                "spacelike": ledger.concurrent(a, b),
            }
    return out


# ---- binding and combination ------------------------------------------------
def emission_payload(emitter_id: str, block_sha256_hex: str) -> dict:
    return {"emitter_id": emitter_id, "block_sha256": block_sha256_hex}


def xor_blocks(blocks: list) -> bytes:
    """XOR combination of equal-length byte blocks."""
    if not blocks:
        raise ValueError("no blocks to combine")
    n = len(blocks[0])
    out = bytes(n)
    for blk in blocks:
        if len(blk) != n:
            raise ValueError("block length mismatch")
        out = bytes(x ^ y for x, y in zip(out, blk))
    return out


def build_beacon_certificate(entries: list) -> dict:
    """entries: [{emitter_id, pos_nm, t_emit_ns, block_hex, cone_certificate}]."""
    per_block = []
    blocks = []
    for e in entries:
        blk = bytes.fromhex(e["block_hex"])
        blocks.append(blk)
        per_block.append({
            "emitter_id": e["emitter_id"],
            "pos_nm": [int(x) for x in e["pos_nm"]],
            "t_emit_ns": int(e["t_emit_ns"]),
            "block_hex": e["block_hex"],
            "block_sha256": hashlib.sha256(blk).hexdigest(),
            "cone_certificate": e["cone_certificate"],
        })
    return {"type": "beacon_certificate", "version": "1",
            "per_block": per_block,
            "beacon_value_hex": xor_blocks(blocks).hex()}


# ---- standalone verifier ----------------------------------------------------
def verify_beacon(beacon_cert: dict, registries: dict) -> dict:
    """Independently re-verify a beacon certificate from its contents plus
    the public station registry. Gates, in order:

      min_sources -> distinct_sources -> block_binding ->
      pairwise_spacelike -> cone_certificate -> beacon_value

    Verdict PASS, or REJECTED with the violated gate and witness
    (propagating inner cone-certificate witnesses).
    """
    per_block = beacon_cert.get("per_block", [])

    # Gate: minimum source count (a certificate combining fewer than the
    # frozen construction's independent emitters gives no independence
    # guarantee - a single source trivially has an empty pairwise set and
    # would otherwise pass every later gate)
    if len(per_block) < MIN_SOURCES:
        return {"verdict": "REJECTED",
                "witness": {"gate": "min_sources",
                            "required": MIN_SOURCES, "got": len(per_block)}}

    # Gate: distinct sources
    ids = [b["emitter_id"] for b in per_block]
    if len(set(ids)) != len(ids):
        return {"verdict": "REJECTED",
                "witness": {"gate": "distinct_sources", "emitter_ids": ids}}

    # Gate: block binding (block hash and event payload binding)
    for b in per_block:
        blk = bytes.fromhex(b["block_hex"])
        h = hashlib.sha256(blk).hexdigest()
        if h != b["block_sha256"]:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "block_binding",
                                "emitter_id": b["emitter_id"],
                                "recomputed_sha256": h,
                                "claimed_sha256": b["block_sha256"]}}
        expected_payload_hash = event_hash(
            emission_payload(b["emitter_id"], b["block_sha256"]))
        ev = b["cone_certificate"]["event"]
        if ev["payload_hash"] != expected_payload_hash:
            return {"verdict": "REJECTED",
                    "witness": {"gate": "block_binding",
                                "emitter_id": b["emitter_id"],
                                "detail": "cone-certificate event does not "
                                          "bind this block",
                                "recomputed_payload_hash": expected_payload_hash,
                                "event_payload_hash": ev["payload_hash"]}}
        if (ev["claimed_emit_time_ns"] != b["t_emit_ns"] or
                tuple(ev["claimed_emit_pos_nm"]) != tuple(b["pos_nm"])):
            return {"verdict": "REJECTED",
                    "witness": {"gate": "block_binding",
                                "emitter_id": b["emitter_id"],
                                "detail": "emission coordinates mismatch "
                                          "between block entry and event"}}

    # Gate: pairwise spacelike (both directions inadmissible)
    emissions = {b["emitter_id"]: {"time_ns": b["t_emit_ns"],
                                   "pos_nm": tuple(b["pos_nm"])}
                 for b in per_block}
    pairwise = pairwise_spacelike_witnesses(emissions)
    for pair, w in pairwise.items():
        if not w["spacelike"]:
            admissible_dir = ("forward" if w["witness_forward"]["admissible"]
                              else "backward")
            return {"verdict": "REJECTED",
                    "witness": {"gate": "pairwise_spacelike", "pair": pair,
                                "admissible_direction": admissible_dir,
                                "exact_witness": w["witness_" + admissible_dir]},
                    "pairwise": pairwise}

    # Gate: every embedded cone certificate independently verifies
    cone_verdicts = {}
    for b in per_block:
        res = verify_certificate(b["cone_certificate"], registries)
        cone_verdicts[b["emitter_id"]] = res["verdict"]
        if res["verdict"] != "PASS":
            return {"verdict": "REJECTED",
                    "witness": {"gate": "cone_certificate",
                                "emitter_id": b["emitter_id"],
                                "inner_witness": res.get("witness")},
                    "pairwise": pairwise}

    # Gate: beacon value recomputes
    recomputed = xor_blocks([bytes.fromhex(b["block_hex"]) for b in per_block])
    if recomputed.hex() != beacon_cert["beacon_value_hex"]:
        return {"verdict": "REJECTED",
                "witness": {"gate": "beacon_value",
                            "recomputed_hex": recomputed.hex(),
                            "claimed_hex": beacon_cert["beacon_value_hex"]}}

    return {"verdict": "PASS", "pairwise": pairwise,
            "cone_certificate_verdicts": cone_verdicts,
            "beacon_value_hex": recomputed.hex()}
