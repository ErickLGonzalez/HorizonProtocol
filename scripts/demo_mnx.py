#!/usr/bin/env python3
"""End-to-end demo: two divergent observers write, conflict, and resolve."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mnemesis.memory import CausalMemory, GeometricOrdering  # noqa: E402


def clk(t, x=0):
    return {"time_ns": t, "pos_nm": [x, 0, 0]}


m = CausalMemory(GeometricOrdering())
print("Two observers 1 light-second apart write the same key concurrently:\n")
rA = m.put("mission_status", "GO", "earth", clk(0, 0))
rB = m.put("mission_status", "HOLD", "mars", clk(0, 299_792_458_000_000_000))
g = m.get("mission_status")
print(f"  read -> {g['status']}")
for c in g["candidates"]:
    print(f"    candidate: {c['value']!r} from {c['observer']}")
print("\n  Neither silently wins. Both retained with provenance.")
print("  Resolution requires an observer in the causal future of BOTH:\n")
res = m.resolve("mission_status", rA["wid"], "control",
                clk(2_000_000_000, 0))
g2 = m.get("mission_status")
print(f"  after resolution -> {g2['status']}: {g2['value']!r}")
print("\n  The overwrite that could not have 'seen' the other write was refused;")
print("  the resolution that causally follows both was admitted.")
