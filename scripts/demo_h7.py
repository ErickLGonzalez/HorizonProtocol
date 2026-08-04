#!/usr/bin/env python3
"""Deep-space authenticated telemetry demo: honest Mars probe vs Earth spoofer."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from horizon.deepspace import (EARTH_MARS_TYP_M, M_TO_NM,  # noqa: E402
                               light_time_table, one_way_light_time_ns)
from horizon.deepspace_protocol import verify_telemetry_packet  # noqa: E402
from horizon.events import make_event  # noqa: E402
from horizon.qubit_sim import honest_response, mismatched_response, score  # noqa: E402
from horizon.stations import demo_registry  # noqa: E402

print("Earth-Mars light-time budget (the security budget):")
for r in light_time_table():
    print(f"  {r['regime']:9s} one-way {r['one_way_light_time_s']/60:5.2f} min   "
         f"round-trip >= {r['round_trip_min']:5.2f} min")

d = EARTH_MARS_TYP_M * M_TO_NM
owlt = one_way_light_time_ns(EARTH_MARS_TYP_M)
p_mars = (d, 0, 0)
p_earth = (0, 0, 0)
link = {"u_ns": 0, "resolve_ns": 0}
beq = {"k": 73, "gap_num": 3, "gap_den": 4}

# a registry is TRUSTED caller state (station positions/keys), never read
# from the packet itself - exactly H1's cone-certificate model
registry = demo_registry([("EARTH-DSN-1", p_earth, 0)])
station = registry["EARTH-DSN-1"]
event = make_event({"telemetry": "h7-demo"}, 0, p_mars)


def packet(recv_time_ns):
    receipt = station.sign_receipt(event["payload_hash"], recv_time_ns)
    return {"event": event, "receipt": receipt}


print("\n1) Honest Mars probe: packet emitted at Mars, receipt signed by a")
print("   registered station, arrives after full light delay, quantum responses")
print("   correct, 73 committed qubits.")
pkt = packet(owlt + 1000)
r = verify_telemetry_packet(pkt, registry, link, beq, score(200, honest_response))
print(f"   -> {r['aggregate_verdict']}  ({r['meaning']})")

print("\n2) Earth-based spoofer forging a 'from Mars' packet: same claim, but the")
print("   signed receipt shows arrival far sooner than light from Mars allows.")
spoof = packet(owlt // 2)
r2 = verify_telemetry_packet(spoof, registry, link, beq, score(200, honest_response))
print(f"   -> {r2['aggregate_verdict']}  (light-cone witness: negative margin)")

print("\n3) Right timing, but adversary lacks the quantum credential (wrong-basis):")
r3 = verify_telemetry_packet(pkt, registry, link, beq, score(200, mismatched_response))
print(f"   -> {r3['aggregate_verdict']}")

print("\n4) Right timing and quantum credential, but the receipt was never signed")
print("   by a registered station (authentication in name only) - REJECTED before")
print("   any timing decision runs.")
forged = packet(owlt + 1000)
forged["receipt"]["mac"] = "0" * 64
r4 = verify_telemetry_packet(forged, registry, link, beq, score(200, honest_response))
print(f"   -> {r4['aggregate_verdict']}  (gate: {r4['timing']['witness']['gate']})")

print("\nThe latency IS the security budget: the same light delay that stops us")
print("locating the probe in real time also stops any adversary from forging its")
print("telemetry faster than light. Verdict class is CONDITIONAL(BE(Q)).")
