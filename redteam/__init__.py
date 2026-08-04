"""Independent red-team harness. [SOUND - attacker, not a gate]

Every REJECTED verdict elsewhere in this repository rejects an input the
system's own test suite constructed - cooperative forgeries. This package
is different: it is an independent attacker that tries to make gates
ADMIT/PASS without authorization, hitting ONLY the public verify_*/gate
functions (never importing verifier internals to "cheat" its way to a
pass - test_redteam_hygiene.py asserts this by source inspection). Zero
successful bypasses is the pass condition for every attack class; a
residual attack surface, where a tier genuinely cannot resolve an attack,
is reported as an explicit quantified number, never silently treated as
zero.

Deterministic: every attack class uses stdlib `random` seeded from a
frozen constant, so a red-team run is bit-reproducible.
"""
__version__ = "0.1.0"
BENCHMARK_ID = "RT1"
SEED = "REDTEAM-FROZEN-SEED-v1"
