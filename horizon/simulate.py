"""Deterministic propagation simulator (honest world model). [HEURISTIC]

Located warning: real deployments measure arrival times; this module
COMPUTES them as  t_recv = t_emit + min_light_time + proc_delay.
It exists so positive gates have an honest world to run in. It is not
part of the trusted verifier: verify_certificate never imports it.
"""
from .geometry import min_light_time_ns


def broadcast(event: dict, registry: dict) -> list:
    t0 = event["claimed_emit_time_ns"]
    p0 = tuple(event["claimed_emit_pos_nm"])
    receipts = []
    for sid in sorted(registry):
        st = registry[sid]
        t_recv = t0 + min_light_time_ns(p0, st.pos_nm) + st.proc_delay_ns
        receipts.append(st.sign_receipt(event["payload_hash"], t_recv))
    return receipts
