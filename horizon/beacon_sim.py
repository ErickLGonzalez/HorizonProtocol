"""Deterministic pseudo-entropy emitters for beacons. [HEURISTIC - located warning]

Located warnings:
  (1) blocks are deterministic pseudo-entropy, SHA-256(seed || emitter_id),
      not physical randomness; arrival times for the embedded cone
      certificates are computed, not measured;
  (2) `statistical_sanity` below is a SMOKE TEST, not a randomness
      certification; causal independence != statistical quality.

This module is the world model only. The trusted verifier
(`horizon.beacon.verify_beacon`) never imports it.
"""
import hashlib

from .beacon import (BLOCK_LEN, EMITTERS, SEED_H4, T_EMIT_NS,
                     build_beacon_certificate, emission_payload)
from .certificate import build_cone_certificate
from .events import make_event
from .simulate import broadcast
from .stations import demo_registry

# Three stations per emitter neighborhood (9 total), frozen offsets
# well under 1 km (1e12 nm) from each emitter.
_STATION_OFFSETS = [
    ((100_000_000_000, 0, 0), 3),   # 0.1 km
    ((0, 100_000_000_000, 0), 4),
    ((0, 0, 100_000_000_000), 5),
]


def station_specs(emitters: dict = None) -> list:
    emitters = EMITTERS if emitters is None else emitters
    specs = []
    for eid in sorted(emitters):
        pos = emitters[eid]
        for i, (off, delay) in enumerate(_STATION_OFFSETS):
            specs.append((f"STN-{eid}-{i}",
                          (pos[0] + off[0], pos[1] + off[1], pos[2] + off[2]),
                          delay))
    return specs


def build_registry(emitters: dict = None):
    return demo_registry(station_specs(emitters))


def derive_block(seed: str, emitter_id: str) -> bytes:
    """Block for emitter i = SHA-256(seed || emitter_id). Deterministic."""
    return hashlib.sha256(f"{seed}||{emitter_id}".encode()).digest()[:BLOCK_LEN]


def build_emission_entry(emitter_id: str, pos_nm, t_emit_ns: int,
                         registry, seed: str = SEED_H4,
                         block: bytes = None) -> dict:
    """One emitter's block + emission event + cone certificate."""
    blk = derive_block(seed, emitter_id) if block is None else block
    payload = emission_payload(emitter_id, hashlib.sha256(blk).hexdigest())
    event = make_event(payload, t_emit_ns, pos_nm)
    receipts = broadcast(event, registry)
    cone = build_cone_certificate(event, receipts)
    return {"emitter_id": emitter_id, "pos_nm": list(pos_nm),
            "t_emit_ns": int(t_emit_ns), "block_hex": blk.hex(),
            "cone_certificate": cone}


def build_full_beacon(seed: str = SEED_H4, emitters: dict = None,
                      t_emit_ns: int = T_EMIT_NS):
    """Honest beacon over the frozen emitters. Returns (beacon_cert, registry)."""
    emitters = EMITTERS if emitters is None else emitters
    registry = build_registry(emitters)
    entries = [build_emission_entry(eid, emitters[eid], t_emit_ns, registry,
                                    seed=seed)
               for eid in sorted(emitters)]
    return build_beacon_certificate(entries), registry


def statistical_sanity(beacon_value: bytes,
                       window=(96, 160)) -> dict:
    """[HEURISTIC] Byte-level bit-balance smoke test on the combined output.

    This is a smoke test, not a randomness certification; causal
    independence != statistical quality.
    """
    popcount = sum(bin(byte).count("1") for byte in beacon_value)
    lo, hi = window
    ok = lo <= popcount <= hi
    return {"tag": "HEURISTIC", "verdict": "PASS" if ok else "FAIL",
            "popcount": popcount, "window": [lo, hi],
            "warning": ("smoke test only, not a randomness certification; "
                        "causal independence != statistical quality")}
