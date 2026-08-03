"""Attack implementations. [attacker code - not on the trusted path]

Every function here attacks a HorizonProtocol gate through ONLY its public
API (never importing or poking verifier internals), and returns a report
dict `{"attack": name, "trials": N, "bypasses": [...]}`. An empty
`bypasses` list is the pass condition; a nonempty one is a genuine,
reproducible finding, not a flaky test.

Uses `decimal.Decimal` for one deliberately-independent differential
check (RT-A) - this is the attacker cross-checking the kernel from
OUTSIDE using different arithmetic, not a security gate itself, so it is
exempt from the repository's no-float discipline (see
tests/test_float_guard.py's EXEMPT_MODULES entry for this package).
"""
import copy
import hashlib
import hmac
from decimal import Decimal, getcontext

from horizon.certificate import build_cone_certificate, verify_certificate
from horizon.events import canonical, make_event
from horizon.geo_fixtures import build_synthetic_consistent_capture
from horizon.geometry import C_NM_PER_NS, causally_admissible, dist2, min_light_time_ns
from horizon.ledger import CausalLedger
from horizon.measure import budget_witness, min_transit_time_ns_eff, verify_measured_certificate
from horizon.simulate import broadcast
from horizon.stations import demo_registry


# ---- RT-A: differential timing fuzz -----------------------------------------
def _independent_admissible(t1, p1, t2, p2):
    """A DIFFERENT algorithm from `causally_admissible`: real-number
    (high-precision Decimal) square root and comparison, rather than
    squaring both sides as exact integers. 60 significant digits vastly
    exceeds what's needed at interplanetary nm/ns scale (~22 digits), so
    this is effectively exact for every distance this repository uses."""
    getcontext().prec = 60
    dt = t2 - t1
    if dt < 0:
        return False
    d2 = dist2(p1, p2)
    lhs = Decimal(C_NM_PER_NS) * Decimal(dt)
    rhs = Decimal(d2).sqrt()
    return lhs >= rhs


def attack_timing_fuzz(rng, trials=5000):
    bypasses = []
    scales = (1_000, 1_000_000, 1_000_000_000, 10**14, 10**17)
    for _ in range(trials):
        scale = rng.choice(scales)
        p1 = (0, 0, 0)
        p2 = (rng.randint(1, scale), rng.randint(0, scale), rng.randint(0, scale))
        mlt = min_light_time_ns(p1, p2)
        offset = rng.randint(-1000, 1000)
        dt = max(0, mlt + offset)
        t1 = rng.randint(0, 10**12)
        t2 = t1 + dt
        kernel_verdict = causally_admissible(t1, p1, t2, p2)
        independent_verdict = _independent_admissible(t1, p1, t2, p2)
        if kernel_verdict != independent_verdict:
            bypasses.append({"t1": t1, "p1": p1, "t2": t2, "p2": p2,
                             "kernel": kernel_verdict, "independent": independent_verdict})
    return {"attack": "timing_fuzz_differential", "trials": trials, "bypasses": bypasses}


# ---- RT-B: budgeted-gate boundary/margin attack -----------------------------
def attack_boundary_fuzz(rng, trials=3000):
    """Search near horizon.measure's two floors for any point where the
    verdict disagrees with the documented three-way partition, or where
    increasing dt_adjusted_ns ever moves the verdict "backwards"
    (ADMITTED -> APPARATUS_LIMITED -> REJECTED is not a legal transition
    as time increases)."""
    bypasses = []
    for _ in range(trials):
        p0 = (0, 0, 0)
        p1 = (rng.randint(1, 10**15), rng.randint(0, 10**14), rng.randint(0, 10**14))
        u_ns = rng.randint(0, 10**7)
        vac = min_light_time_ns(p0, p1)
        typ = min_transit_time_ns_eff(p0, p1)
        lo = max(0, vac - u_ns - 10**6)
        hi = typ + 10**6
        raw_dt = rng.randint(lo, max(lo, hi)) - u_ns
        w = budget_witness(0, p0, raw_dt, p1, u_ns)
        dt_adj = w["dt_adjusted_ns"]
        expected = ("REJECTED" if dt_adj < vac else
                   "APPARATUS_LIMITED" if dt_adj < typ else "ADMITTED")
        if w["verdict"] != expected:
            bypasses.append({"p1": p1, "u_ns": u_ns, "raw_dt": raw_dt,
                             "dt_adjusted_ns": dt_adj, "vacuum_floor_ns": vac,
                             "typical_floor_ns": typ, "got": w["verdict"],
                             "expected": expected})
    # monotonicity: nudging the raw receive time later must never move a
    # verdict "backwards" through ADMITTED -> AL -> REJECTED
    order = {"REJECTED": 0, "APPARATUS_LIMITED": 1, "ADMITTED": 2}
    for _ in range(trials // 5):
        p0 = (0, 0, 0)
        p1 = (rng.randint(1, 10**15), 0, 0)
        u_ns = rng.randint(0, 10**6)
        vac = min_light_time_ns(p0, p1)
        base = rng.randint(max(0, vac - 10**6), vac + 10**6)
        step = rng.randint(1, 10**5)
        w1 = budget_witness(0, p0, base, p1, u_ns)
        w2 = budget_witness(0, p0, base + step, p1, u_ns)
        if order[w2["verdict"]] < order[w1["verdict"]]:
            bypasses.append({"nonmonotone": True, "p1": p1, "u_ns": u_ns,
                             "t1": base, "t2": base + step,
                             "verdict1": w1["verdict"], "verdict2": w2["verdict"]})
    return {"attack": "budgeted_gate_boundary_fuzz", "trials": trials, "bypasses": bypasses}


# ---- RT-C: replay / forgery attack on cone certificates ---------------------
def _honest_h1_cert(seed_id):
    specs = [(f"STN-A-{seed_id}", (10_000_000_000_000, 0, 0), 0),
            (f"STN-B-{seed_id}", (0, 10_000_000_000_000, 0), 0),
            (f"STN-C-{seed_id}", (0, 0, 10_000_000_000_000), 0)]
    registry = demo_registry(specs)
    event = make_event({"rt": seed_id}, 0, (0, 0, 0))
    receipts = broadcast(event, registry)
    cert = build_cone_certificate(event, receipts)
    return cert, registry


def attack_forgery_fuzz(rng, trials=500):
    """Mutate an honest cone certificate many ways and assert none of the
    mutations is ever accepted as PASS by `verify_certificate`, hit only
    through its public signature."""
    bypasses = []
    for i in range(trials):
        cert, registry = _honest_h1_cert(i)
        mutated = copy.deepcopy(cert)
        mutation = rng.choice(["tamper_recv_time", "tamper_position",
                               "swap_station_id", "flip_mac_byte",
                               "tamper_payload_hash"])
        idx = rng.randrange(len(mutated["receipts"]))
        body = mutated["receipts"][idx]["body"]
        if mutation == "tamper_recv_time":
            body["recv_time_ns"] += rng.choice([-1, 1]) * rng.randint(1, 10**6)
        elif mutation == "tamper_position":
            body["station_pos_nm"][rng.randrange(3)] += rng.randint(1, 10**9)
        elif mutation == "swap_station_id":
            others = [sid for sid in registry if sid != body["station_id"]]
            if others:
                body["station_id"] = rng.choice(others)
        elif mutation == "flip_mac_byte":
            mac = bytearray(bytes.fromhex(mutated["receipts"][idx]["mac"]))
            mac[rng.randrange(len(mac))] ^= 1 << rng.randrange(8)
            mutated["receipts"][idx]["mac"] = mac.hex()
        elif mutation == "tamper_payload_hash":
            body["payload_hash"] = hashlib.sha256(
                f"forged-{i}".encode()).hexdigest()

        if mutated == cert:
            continue  # mutation was a no-op (astronomically unlikely); skip
        res = verify_certificate(mutated, registry)
        if res["verdict"] == "PASS":
            bypasses.append({"trial": i, "mutation": mutation})
    return {"attack": "cone_certificate_forgery_fuzz", "trials": trials,
           "bypasses": bypasses}


def attack_measured_certificate_forgery_fuzz(rng, trials=500):
    """Same idea, against H5/H6's measured-certificate verifier, plus a
    dedicated sweep attempting to smuggle forged node_params/u_ns/c_eff
    through the certificate itself (the class of bug fixed after the H5
    review - fuzzed here rather than only fixed-case-tested)."""
    bypasses = []
    honest_cert, registry, node_u_ns = build_synthetic_consistent_capture()
    trusted_params = {nid: {"u_ns": u} for nid, u in node_u_ns.items()}
    for i in range(trials):
        mutated = copy.deepcopy(honest_cert)
        idx = rng.randrange(len(mutated["receipts"]))
        body = mutated["receipts"][idx]["body"]
        mutation = rng.choice(["tamper_recv_time_early", "tamper_recv_time_late",
                               "forge_node_params", "duplicate_receipt"])
        if mutation == "tamper_recv_time_early":
            body["recv_time_ns"] -= rng.randint(1, 10**8)
        elif mutation == "tamper_recv_time_late":
            body["recv_time_ns"] += rng.randint(1, 10**8)  # must stay PASS - not a bypass by itself
        elif mutation == "forge_node_params":
            body["recv_time_ns"] -= rng.randint(10**6, 10**9)  # make it impossible
            mutated["node_params"] = {body["station_id"]: {
                "u_ns": rng.randint(10**9, 10**15),
                "c_eff_num": 1, "c_eff_den": rng.choice([1, 1000])}}
        elif mutation == "duplicate_receipt":
            mutated["receipts"][idx] = copy.deepcopy(
                mutated["receipts"][(idx + 1) % len(mutated["receipts"])])

        res = verify_measured_certificate(mutated, registry, trusted_params)
        if mutation in ("forge_node_params",) and res["verdict"] != "REJECTED":
            bypasses.append({"trial": i, "mutation": mutation, "verdict": res["verdict"]})
        if mutation == "tamper_recv_time_early" and res["verdict"] not in ("REJECTED", "APPARATUS_LIMITED"):
            bypasses.append({"trial": i, "mutation": mutation, "verdict": res["verdict"]})
        if mutation == "duplicate_receipt" and res["verdict"] == "PASS":
            bypasses.append({"trial": i, "mutation": mutation, "verdict": res["verdict"]})
    return {"attack": "measured_certificate_forgery_fuzz", "trials": trials,
           "bypasses": bypasses}


# ---- RT-D: causal ledger cycle / backward-time attack -----------------------
def attack_ledger_cycle_fuzz(rng, trials=2000):
    """Random events; try to force a 2-cycle (a->b and b->a both admitted)
    or a 3-cycle (a->b->c->a all admitted) into the ledger. Neither should
    ever be possible, since strictly-later-time is required for ANY
    admitted edge, making a directed cycle in admitted edges impossible
    by construction - fuzz-verify that construction holds."""
    bypasses = []
    for i in range(trials):
        ledger = CausalLedger()
        pts = []
        for j in range(3):
            t = rng.randint(0, 10**12)
            p = (rng.randint(0, 10**14), rng.randint(0, 10**14), rng.randint(0, 10**14))
            eid = f"E{i}-{j}"
            ledger.add_event(eid, t, p)
            pts.append(eid)
        a, b, c = pts
        r_ab = ledger.add_edge(a, b)
        r_ba = ledger.add_edge(b, a)
        if r_ab["verdict"] == "ADMITTED" and r_ba["verdict"] == "ADMITTED":
            bypasses.append({"trial": i, "kind": "2-cycle", "edge": [a, b]})

        ledger2 = CausalLedger()
        for j, eid in enumerate(pts):
            ledger2.add_event(eid, rng.randint(0, 10**12),
                              (rng.randint(0, 10**14), rng.randint(0, 10**14),
                               rng.randint(0, 10**14)))
        r1 = ledger2.add_edge(a, b)
        r2 = ledger2.add_edge(b, c)
        r3 = ledger2.add_edge(c, a)
        if all(r["verdict"] == "ADMITTED" for r in (r1, r2, r3)):
            bypasses.append({"trial": i, "kind": "3-cycle", "edges": [[a, b], [b, c], [c, a]]})
    return {"attack": "ledger_cycle_fuzz", "trials": trials, "bypasses": bypasses}


def run_all(seed: str):
    import random
    rng = random.Random(seed)
    return [
        attack_timing_fuzz(rng),
        attack_boundary_fuzz(rng),
        attack_forgery_fuzz(rng),
        attack_measured_certificate_forgery_fuzz(rng),
        attack_ledger_cycle_fuzz(rng),
    ]
