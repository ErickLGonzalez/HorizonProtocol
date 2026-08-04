#!/usr/bin/env python3
"""Run D0 gates, emit certificates/d0_certificate.json, exit 0 iff green."""
import hashlib, json, os, platform, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "bench"))
from geo_workload import run as bench

GATES = [
    ("D0-A","tests.test_d0a_ordering","SOUND","L2 ordering contract: geometric/logical/hybrid"),
    ("D0-B","tests.test_d0b_store","SOUND","coordination-free commit + conflict retention"),
    ("D0-C","tests.test_d0c_backend","SOUND","persistence behind swappable interface; no DB dependency"),
    ("D0-D","tests.test_d0d_benchmark","SOUND","coordination-free advantage real + deterministic"),
    ("D0-E","tests.test_d0e_float_guard","SOUND","exactness boundary: ordering/geometry contain no floats"),
    ("D0-F","tests.test_d0f_geometry_hash","SOUND","vendored geometry kernel hash-matches horizon/geometry.py"),
]

def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()

def main():
    results, all_pass = [], True
    for gid, mod, tag, desc in GATES:
        p = subprocess.run([sys.executable,"-m","unittest","-v",mod],
                           cwd=ROOT, capture_output=True, text=True)
        ok = p.returncode == 0; all_pass &= ok
        results.append({"gate":gid,"description":desc,"soundness_tag":tag,
                        "result":"PASS" if ok else "FAIL"})
        print(f"{gid}: {'PASS' if ok else 'FAIL'} - {desc}")

    benchmark = bench()
    src = {}
    for dp,_,files in os.walk(os.path.join(ROOT,"causalstore")):
        for fn in sorted(files):
            if fn.endswith(".py"):
                fp=os.path.join(dp,fn); src[os.path.relpath(fp,ROOT)]=sha(fp)

    cert = {
        "certificate_version":"1","benchmark_id":"D0","program":"causal-store",
        "claim_class":"ENGINEERING_REFERENCE","execution_tier":"BENCHMARK",
        "promotion_allowed":False,"empirical_claim":"NONE",
        "adversary_model":("not applicable - this is a performance/correctness "
                           "engineering benchmark, not an adversarial security gate; "
                           "the only decision under adversarial pressure (the light-cone "
                           "admissibility test in geometry.py) is the machine-checked "
                           "HorizonProtocol kernel, whose adversary model is recorded "
                           "against H1-H9, not re-litigated here"),
        "thesis":("performance-first: spacelike-independent writes commit without "
                  "coordination; only genuine causal dependencies serialize. Targets "
                  "geo-distributed transaction latency where wide-area consensus round "
                  "trips dominate."),
        "l2_contract":"before(a,b) / concurrent(a,b) / witness(a,b); event clock geometric or vc",
        "interop_note":("engine depends ONLY on the L2 ordering contract and the "
                        "StoreBackend contract; a memory/database layer plugs in later "
                        "WITHOUT the engine importing it (in-memory backend ships for testing)"),
        "benchmark":benchmark,
        "heuristic_warnings":[
            {"location":"bench/geo_workload.py",
             "warning":"latency is MODELED from RTT/local-commit assumptions, not measured on real wide-area links; real deployment must measure"},
        ],
        "unit_convention": {"position": "nanometers (int)", "time": "nanoseconds (int)",
                            "c": 299792458, "c_units": "nm/ns (exact integer)"},
        "gates":results,"aggregate":"PASS" if all_pass else "FAIL",
        "source_hashes":src,"python_version":platform.python_version(),
    }
    out = os.path.join(ROOT,"certificates","d0_certificate.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(cert, open(out,"w"), indent=2, sort_keys=True)
    print(f"\nAGGREGATE: {cert['aggregate']}")
    print(f"coordination-free rate: {benchmark['coordination_free_rate']:.1%}")
    print(f"modeled speedup vs total-order: {benchmark['modeled_avg_latency_ms']['speedup_x']}x")
    print(f"certificate written: {out}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
