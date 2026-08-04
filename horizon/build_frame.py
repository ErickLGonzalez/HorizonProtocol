"""Build a tiered node registry (nm lattice + clock-uncertainty tier) for H8.

Reuses `horizon.geo_frame.GeoFrame` unmodified (the same real-geography ->
exact-nanometer-lattice transform H6 uses) - this module adds only the
TIMING TIER concept H8 needs on top of it (H6's registry has a flat per-node
`u_ns`; H8 additionally records which synchronization tier a node is
operating under, so the same registry can be re-evaluated at NTP/PTP/GNSS
tiers to demonstrate the APPARATUS_LIMITED -> ADMITTED transition, H8-D).
"""
import json
import os

from .geo_frame import GeoFrame

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "h8_nodes.json")

# Timing tiers: declared clock-uncertainty budget per synchronization class.
TIERS = {
    "NTP":  5_000_000,   # ~5 ms
    "PTP":     50_000,   # ~50 us
    "GNSS":     1_000,   # ~1 us
}


def load_registry(path=DATA):
    with open(path) as f:
        spec = json.load(f)
    fo = spec["frame_origin"]
    frame = GeoFrame(fo["name"], fo["llh"], spec.get("quantization_nm", 1))
    reg = {}
    for n in spec["nodes"]:
        reg[n["id"]] = {"pos_nm": list(frame.to_nm(n["llh"])),
                        "u_ns": TIERS[n["tier"]], "tier": n["tier"],
                        "llh": n["llh"]}
    return frame, reg, spec
