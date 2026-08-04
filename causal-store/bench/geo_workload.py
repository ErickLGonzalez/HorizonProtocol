#!/usr/bin/env python3
"""The sales pitch, quantified: coordination-free commits vs a total-order
baseline on a geo-distributed workload.

Model: N regions across the globe; each does writes. Under a total-order
protocol (Paxos/Raft/2PC style) EVERY write pays a wide-area round trip to
serialize. Under causal-store, only writes with genuine causal dependencies
coordinate; spacelike-independent writes commit locally.

We report: coordination-free rate, and modeled latency assuming a wide-area
round trip costs RTT_MS and a local commit costs LOCAL_MS.
"""
import sys, os, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from causalstore.store import CausalStore
from causalstore.ordering import GeometricOrdering
from causalstore.geometry import C_NM_PER_NS

# global regions, positions in nm along a line (light-ms apart), each ~thousands of km
REGIONS = {
    "us-east":   0,
    "us-west":   C_NM_PER_NS * 12_000_000,   # ~12 light-ms
    "eu-west":   C_NM_PER_NS * 28_000_000,
    "ap-south":  C_NM_PER_NS * 90_000_000,
    "sa-east":   C_NM_PER_NS * 40_000_000,
}
RTT_MS = 80.0     # typical inter-region wide-area round trip
LOCAL_MS = 0.05   # local commit

def run(n_writes=5000, n_keys=2000, seed="D0-BENCH-v1"):
    rng = random.Random(seed)
    s = CausalStore(GeometricOrdering())
    region_names = list(REGIONS)
    t = 0
    for _ in range(n_writes):
        region = rng.choice(region_names)
        pos = REGIONS[region]
        key = f"acct:{rng.randint(0, n_keys-1)}"
        t += rng.randint(1, 1000)  # ns advance; writes are effectively spacelike across regions
        s.write(key, str(rng.randint(0, 1_000_000)), region,
                {"time_ns": t, "pos_nm": [pos, 0, 0], "u_ns": 100})
    cf = s.coordination_free_rate()
    # modeled latency
    total = s.stats["total"]
    cf_writes = s.stats["coordination_free"]
    coord_writes = s.stats["coordinated"]
    causal_lat = (cf_writes * LOCAL_MS + coord_writes * RTT_MS) / total
    totalorder_lat = RTT_MS  # every write serializes
    return {
        "writes": total, "keys": n_keys, "regions": len(REGIONS),
        "coordination_free_rate": round(cf, 4),
        "coordinated_writes": coord_writes,
        "modeled_avg_latency_ms": {
            "causal_store": round(causal_lat, 3),
            "total_order_baseline": round(totalorder_lat, 3),
            "speedup_x": round(totalorder_lat / causal_lat, 1) if causal_lat else None,
        },
        "assumptions": {"wide_area_rtt_ms": RTT_MS, "local_commit_ms": LOCAL_MS},
    }

if __name__ == "__main__":
    import json
    r = run()
    print(json.dumps(r, indent=2))
