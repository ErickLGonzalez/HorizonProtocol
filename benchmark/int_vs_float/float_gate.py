"""Faithful floating-point light-cone gate - the comparison control.

This is deliberately NOT a strawman. It implements the same predicate as
`horizon.geometry.causally_admissible` the way an engineer without the
exact-integer discipline would naturally write it: positions/times cast to
float64 (or float32, as a second control), `c` as a float, `c*dt` and
`sqrt(dx^2+dy^2+dz^2)` computed with the standard library's `math.sqrt`
(libm), compared with a conventional relative tolerance `eps`. Every
elementary float32 operation is rounded through IEEE-754 binary32 via
`struct` (stdlib only - this repository has exactly one non-stdlib
dependency, `z3-solver`, confined to `formal/`; this module does not add a
second one), so float32 behavior is genuinely emulated per-operation
rather than only at storage.

Inputs are accepted in the SAME integer nanometer/nanosecond units as
`horizon.geometry.causally_admissible`, then converted to the
meters/seconds a float implementation would naturally use - this ensures
both gates are compared on IDENTICAL inputs, with the float gate exercising
its own mantissa the way a real one would.

`order` and `algorithm` let a caller reproduce two real sources of
cross-platform floating-point divergence without needing multiple physical
architectures:
  - IEEE-754 addition is not associative, so summing dx^2+dy^2+dz^2 in a
    different order (as a different compiler, instruction scheduler, or
    SIMD lane assignment might) can change the rounded result.
  - `math.hypot` uses a different (more accurate, overflow-avoiding)
    internal algorithm than a naive sum-of-squares-then-sqrt, standing in
    for "a different libm implementation computed this."
These are real, standard-library-observable effects, not synthetic noise -
see docs/int-vs-float-results.md section on Test 2 for the honest
limitation this is standing in for (no multi-architecture rig available
here).
"""
import math
import struct

C_M_PER_S = 299_792_458.0  # exactly representable in float64 (< 2**53); NOT
                            # exactly representable in float32 (> 2**24) -
                            # see docs/int-vs-float-results.md
NM_PER_M = 1_000_000_000
NS_PER_S = 1_000_000_000

# Reasonable, standard tolerances - not tuned to make either gate look
# better or worse. float64: ~1e7x the machine epsilon (2.22e-16), a
# generous real-world safety margin. float32: ~10x its machine epsilon
# (1.19e-7), the same style of margin scaled to the coarser format.
DEFAULT_EPS = {"float64": 1e-9, "float32": 1e-6}

_ORDERS = {"xyz": (0, 1, 2), "zyx": (2, 1, 0)}


def _f32(x):
    """Round a Python float through IEEE-754 binary32 (stdlib struct only)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _cast(x, precision):
    return _f32(x) if precision == "float32" else float(x)


def _mul(a, b, precision):
    return _cast(a * b, precision)


def _add(a, b, precision):
    return _cast(a + b, precision)


def _div(a, b, precision):
    return _cast(a / b, precision)


def _distance_m(dx, dy, dz, precision, order="xyz", algorithm="sumsq"):
    """Straight-line distance in meters, float-native (sqrt, no exact form)."""
    coords = (dx, dy, dz)
    idx = _ORDERS[order]
    if algorithm == "hypot":
        ordered = tuple(coords[i] for i in idx)
        return _cast(math.hypot(*ordered), precision)
    total = _mul(coords[idx[0]], coords[idx[0]], precision)
    for i in idx[1:]:
        total = _add(total, _mul(coords[i], coords[i], precision), precision)
    return _cast(math.sqrt(total), precision)


def admissibility_witness_float(t1_ns, p1_nm, t2_ns, p2_nm, precision="float64",
                                 eps="default", order="xyz", algorithm="sumsq"):
    """Float analogue of horizon.geometry.admissibility_witness - same inputs
    (integer nm/ns), float-native computation, for certificates/examples."""
    if eps == "default":
        eps = DEFAULT_EPS[precision]
    dt_ns = t2_ns - t1_ns
    dt_s = _div(_cast(dt_ns, precision), _cast(NS_PER_S, precision), precision)
    dx = _div(_cast(p2_nm[0] - p1_nm[0], precision), _cast(NM_PER_M, precision), precision)
    dy = _div(_cast(p2_nm[1] - p1_nm[1], precision), _cast(NM_PER_M, precision), precision)
    dz = _div(_cast(p2_nm[2] - p1_nm[2], precision), _cast(NM_PER_M, precision), precision)
    c = _cast(C_M_PER_S, precision)
    if dt_s < 0:
        lhs = None
        dist = _distance_m(dx, dy, dz, precision, order, algorithm)
        admissible = False
    else:
        lhs = _mul(c, dt_s, precision)
        dist = _distance_m(dx, dy, dz, precision, order, algorithm)
        tol = eps * max(1.0, abs(lhs), abs(dist))
        admissible = (lhs + tol) >= dist
    return {
        "precision": precision, "eps": eps, "order": order, "algorithm": algorithm,
        "dt_s": dt_s, "c_m_per_s": c, "lhs_c_dt_m": lhs, "rhs_dist_m": dist,
        "admissible": admissible,
    }


def causally_admissible_float(t1_ns, p1_nm, t2_ns, p2_nm, precision="float64",
                               eps="default", order="xyz", algorithm="sumsq"):
    """Float verdict for the same predicate as
    horizon.geometry.causally_admissible, given identical integer nm/ns
    inputs. See module docstring for what `precision`/`eps`/`order`/
    `algorithm` vary and why."""
    return admissibility_witness_float(t1_ns, p1_nm, t2_ns, p2_nm, precision,
                                        eps, order, algorithm)["admissible"]


def causally_admissible_float64_naive(t1_ns, p1_nm, t2_ns, p2_nm, eps=None):
    """Minimal, uninstrumented float64 gate: no per-operation casting
    through `_cast`, no order/algorithm knobs - straight-line code the way
    a production engineer would actually write this for speed. Used ONLY
    for the Test 3 speed line in run_int_vs_float.py.

    `causally_admissible_float` above is deliberately instrumented (every
    elementary op routed through `_cast` so float32 can be emulated
    per-operation, plus order/algorithm parameters) so Test 1/2 can probe
    precision, summation order, and sqrt algorithm. That instrumentation
    is Python-level function-call overhead that has nothing to do with
    floating-point arithmetic itself; timing it as "the float gate's
    speed" would unfairly inflate float's measured cost relative to a
    real engineer's implementation. This function is that real
    implementation, minus the probes.
    """
    if eps is None:
        eps = DEFAULT_EPS["float64"]
    dt_s = (t2_ns - t1_ns) / NS_PER_S
    if dt_s < 0:
        return False
    dx = (p2_nm[0] - p1_nm[0]) / NM_PER_M
    dy = (p2_nm[1] - p1_nm[1]) / NM_PER_M
    dz = (p2_nm[2] - p1_nm[2]) / NM_PER_M
    lhs = C_M_PER_S * dt_s
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    tol = eps * max(1.0, abs(lhs), abs(dist))
    return (lhs + tol) >= dist
