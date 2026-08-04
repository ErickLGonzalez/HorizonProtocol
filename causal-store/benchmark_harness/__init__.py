"""benchmark_harness — a fair, reproducible comparison harness for
causal-store's coordination-free commit path against best-in-class
geo-distributed systems, per docs/benchmark-harness-spec.md.

Distinct from `causalstore` (the engine under test) and from
`bench/geo_workload.py` (the D0 benchmark's own MODELED micro-benchmark):
this package drives a neutral, ground-truth-labeled trace through ANY
number of adapters (see adapters/base.py) and reports latency/throughput
curves plus a correctness verdict - it does not itself decide any
admissibility question.
"""
__version__ = "0.1.0"
