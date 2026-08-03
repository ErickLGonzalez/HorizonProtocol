#!/usr/bin/env python3
"""Deep-space authenticated telemetry demo: honest Mars probe vs Earth spoofer."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from horizon.deepspace import (EARTH_MARS_TYP_M, M_TO_NM,  # noqa: E402
                               light_time_table, one_way_light_time_ns)
from horizon.deepspace_protocol import verify_telemetry_packet  # noqa: E402
from horizon.qubit_sim import honest_response, mismatched_response, score  # noqa: E402

print("Earth-Mars light-time budget (the security budget):")
for r in light_time_table():
    print(f"  {r['regime']:9s} one-way {r['one_way_light_time_s']/60:5.2f} min   "
         f"round-trip >= {r['round_trip_min']:5.2f} min")

d = EARTH_MARS_TYP_M * M_TO_NM
owlt = one_way_light_time_ns(EARTH_MARS_TYP_M)
link = {"u_ns": 0, "resolve_ns": 0}
beq = {"k": 73, "gap_num": 3, "gap_den": 4}

print("\n1) Honest Mars probe: packet emitted at Mars, arrives after full light delay,")
print("   quantum responses correct, 73 committed qubits.")
pkt = {"t0": 0, "p_src": [d, 0, 0], "t_recv": owlt + 1000, "p_dst": [0, 0, 0]}
r = verify_telemetry_packet(pkt, link, beq, score(200, honest_response))
print(f"   -> {r['aggregate_verdict']}  ({r['meaning']})")

print("\n2) Earth-based spoofer forging a 'from Mars' packet: same claim, but the")
print("   packet reaches the verifier far sooner than light from Mars allows.")
spoof = {"t0": 0, "p_src": [d, 0, 0], "t_recv": owlt // 2, "p_dst": [0, 0, 0]}
r2 = verify_telemetry_packet(spoof, link, beq, score(200, honest_response))
print(f"   -> {r2['aggregate_verdict']}  (light-cone witness: negative margin)")

print("\n3) Right timing, but adversary lacks the quantum credential (wrong-basis):")
r3 = verify_telemetry_packet(pkt, link, beq, score(200, mismatched_response))
print(f"   -> {r3['aggregate_verdict']}")

print("\nThe latency IS the security budget: the same light delay that stops us")
print("locating the probe in real time also stops any adversary from forging its")
print("telemetry faster than light. Verdict class is CONDITIONAL(BE(Q)).")
