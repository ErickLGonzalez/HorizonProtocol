"""HorizonProtocol — trust rooted in causal structure.

H-series reference implementation. Stdlib-only.

Exact-unit convention (the "nanometer/nanosecond lattice"):
  * positions are integers in NANOMETERS
  * times are integers in NANOSECONDS
  * the speed of light is then EXACTLY the integer
        C_NM_PER_NS = 299_792_458
    because c = 299,792,458 m/s = 299,792,458 nm/ns.
All security-critical light-cone gates are evaluated in exact integer
arithmetic: no floats appear anywhere in an admissibility decision.
"""
__version__ = "0.1.0"
BENCHMARK_ID = "H1"
