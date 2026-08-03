"""Event objects and canonical hashing.  [SOUND]"""
import hashlib
import json


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def event_hash(payload: dict) -> str:
    """SHA-256 over the canonical JSON encoding of the payload."""
    return hashlib.sha256(canonical(payload)).hexdigest()


def make_event(payload: dict, emit_time_ns: int, emit_pos_nm) -> dict:
    return {
        "payload_hash": event_hash(payload),
        "claimed_emit_time_ns": int(emit_time_ns),
        "claimed_emit_pos_nm": [int(x) for x in emit_pos_nm],
    }
