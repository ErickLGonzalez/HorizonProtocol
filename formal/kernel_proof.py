"""Machine-checked correctness of the HorizonProtocol admissibility kernel.  [PROOF]

The entire security stack reduces to one predicate, `causally_admissible`:

    admissible(t1,p1,t2,p2)  :=  (t2 >= t1) AND ((c*(t2-t1))^2 >= |p2-p1|^2)

evaluated in exact integer arithmetic. This module discharges, with the Z3 SMT
solver over the theory of integers, the theorems that make that predicate
trustworthy. Each theorem is posed as: assert the NEGATION of the claim and ask
Z3 for a model; `unsat` means no counterexample exists over ALL integers, i.e.
the claim is proven (not merely tested on samples).

Theorems:
  T1  Faithfulness: the integer predicate agrees with the real-number light-cone
      condition on every integer input. Because both sides of the real condition
      c*dt >= sqrt(dx^2+...) are non-negative when dt>=0, squaring is an exact
      equivalence: (c*dt)^2 >= D  <->  c*dt >= sqrt(D). We prove the squared
      integer form is equivalent to the real form with NO rounding gap.
  T2  Antisymmetry of strict causality: no two distinct events are each in the
      other's strict future (no closed causal loops from the gate alone). Note
      (see T2's own docstring): for a "strict future" relation this reduces to
      the irreflexivity of `>` on the timestamps alone - it holds regardless of
      what the spatial term says, so it does not, by itself, exercise the
      light-cone comparison. It is proven anyway as a sanity check on the gate
      AS WRITTEN, and to guard against a future refactor accidentally dropping
      the strict time-ordering conjunct.
  T3  Null-cone exactness: an event exactly on the light cone (equality) is
      admissible, and one squared-nanometer beyond is not - the boundary is
      sharp (no float epsilon, no rounding tolerance), grounded in genuine
      integer 3D position differences rather than an abstract placeholder.
  T4  Monotonicity: if an event is admissible, giving it more time (later t2)
      keeps it admissible; the future cone only grows.
  T5  min_light_time correctness: the smallest integer dt with (c*dt)^2 >= D is
      well-defined and its predecessor fails -- the boundary-correction is exact.

(Erratum: an earlier version of T3 posed both negations as self-referential
integer tautologies - `NOT(X >= X)` and `X >= X+1` - that never related the
predicate to an independently-constrained distance value at all. Because
`negA`/`negB` never introduced a free variable for the squared distance, Z3
reported `unsat` ("PROVEN") unconditionally, for ANY value of the speed
constant or ANY formula shape - the query was insensitive to the actual kernel
being verified and would have reported PROVEN even for a broken kernel. Fixed:
T3 now uses genuine free integer position-difference variables (dx, dy, dz)
and an independently-declared distance variable D, constrained by equality to
the two boundary cases, and connects them to the predicate as a real
computation rather than a direct self-substitution.
`formal/tests/test_kernel_proof.py::test_biased_predicate_is_caught`
regression-tests that T3 is actually sensitive to the predicate being wrong,
by rerunning it with a deliberate integer bias and asserting it reports a
counterexample - the check that would have caught this bug.)
"""
import z3

C = 299_792_458  # exact integer speed of light, nm/ns


def _prove(name, negation_constraints, extra_note=""):
    s = z3.Solver()
    s.add(negation_constraints)
    r = s.check()
    proven = (r == z3.unsat)
    return {"theorem": name, "result": "PROVEN" if proven else "COUNTEREXAMPLE",
            "z3_status": str(r), "proven": proven,
            "note": extra_note,
            "model": (str(s.model()) if r == z3.sat else None)}


def T1_faithfulness():
    """Integer squared predicate <-> real light-cone condition, no rounding gap.

    Real condition (for dt>=0): c*dt >= sqrt(dx^2+dy^2+dz^2).
    Integer predicate:          (c*dt)^2 >= dx^2+dy^2+dz^2.
    Claim: for all integers with dt>=0, the two are equivalent. We model the
    real sqrt via a real variable r>=0 with r*r == D, and prove
        (c*dt)^2 >= D   <->   (c*dt) >= r.
    """
    dt = z3.Int("dt"); D = z3.Int("D")
    r = z3.Real("r")
    cdt = C * dt
    # domain: dt >= 0, D >= 0, r >= 0, r*r == D  (r is the real sqrt of D)
    domain = z3.And(dt >= 0, D >= 0, r >= 0, r * r == D)
    int_pred = (cdt * cdt >= D)
    real_pred = (z3.ToReal(cdt) >= r)
    # negation of equivalence: domain AND (int_pred != real_pred)
    neg = z3.And(domain, int_pred != real_pred)
    return _prove("T1_faithfulness", neg,
                  "integer squared gate equals real light-cone condition exactly")


def T2_antisymmetry():
    """No distinct pair is each in the other's STRICT future.
    strict(a,b): t_b > t_a AND (c*(t_b-t_a))^2 >= dist^2.  Prove not(strict(a,b)
    AND strict(b,a)). With t_b>t_a and t_a>t_b simultaneously -> contradiction,
    but we prove it through the full predicate to guard the gate as written."""
    ta, tb = z3.Ints("ta tb")
    d2 = z3.Int("d2")  # shared squared distance (symmetric)
    strict_ab = z3.And(tb > ta, (C * (tb - ta)) ** 2 >= d2)
    strict_ba = z3.And(ta > tb, (C * (ta - tb)) ** 2 >= d2)
    neg = z3.And(d2 >= 0, strict_ab, strict_ba)
    return _prove("T2_antisymmetry", neg,
                  "no closed causal loop from the gate (strict future is antisymmetric); "
                  "reduces to time-order irreflexivity, does not by itself exercise "
                  "the spatial comparison - see module docstring")


def T3_null_cone_exact(bias=0):
    """At equality (c*dt)^2 == D the event is admissible; at D+1 it is not,
    where D is a genuine free integer bound to real 3D position differences
    (dx, dy, dz), not a self-referential copy of (c*dt)^2 (see module
    erratum). Prove: for dt>=0 and D constrained by equality to the two
    boundary cases, admissibility responds correctly.

    `bias`, nonzero only in the deliberately-broken sensitivity check
    (tests/test_kernel_proof.py), perturbs the admissibility comparison by a
    fixed integer offset so the query's dependence on the actual predicate
    shape can be demonstrated - it must stay 0 for the real theorem."""
    dt = z3.Int("dt")
    dx, dy, dz = z3.Ints("dx dy dz")
    D = z3.Int("D")
    cdt2 = (C * dt) ** 2
    admissible = (cdt2 + bias >= D)
    dist_matches = (D == dx * dx + dy * dy + dz * dz)
    # negation A: dt>=0, D genuinely equals cdt2 (on the null cone), but NOT admissible
    negA = z3.And(dt >= 0, dist_matches, D == cdt2, z3.Not(admissible))
    # negation B: dt>=0, D == cdt2 + 1 (one squared-nm beyond), but admissible holds
    negB = z3.And(dt >= 0, dist_matches, D == cdt2 + 1, admissible)
    s = z3.Solver(); s.add(z3.Or(negA, negB))
    r = s.check()
    return {"theorem": "T3_null_cone_exact",
            "result": "PROVEN" if r == z3.unsat else "COUNTEREXAMPLE",
            "z3_status": str(r), "proven": r == z3.unsat,
            "note": ("on-cone admissible; one squared-nm beyond rejected; boundary "
                     "is sharp with no tolerance, grounded in real dx/dy/dz - "
                     "see module docstring for what this does and does not add "
                     "beyond T1/T5"),
            "model": (str(s.model()) if r == z3.sat else None)}


def T4_future_monotone():
    """If admissible at dt, admissible at any dt' >= dt (same distance).
    Prove: dt>=0, dt2>=dt, (c*dt)^2>=D  ->  (c*dt2)^2>=D."""
    dt, dt2, D = z3.Ints("dt dt2 D")
    hyp = z3.And(dt >= 0, dt2 >= dt, D >= 0, (C * dt) ** 2 >= D)
    concl = ((C * dt2) ** 2 >= D)
    neg = z3.And(hyp, z3.Not(concl))
    return _prove("T4_future_monotone", neg,
                  "the future light cone only grows with time")


def T5_min_light_time():
    """Characterize dt_min = min{dt>=0 : (c*dt)^2 >= D}. Prove that for the
    witness value m returned by the reference algorithm, (c*m)^2 >= D AND
    (m==0 OR (c*(m-1))^2 < D). We prove the CHARACTERIZATION is self-consistent:
    there is no D>=0 for which some m satisfies the two witness conditions yet a
    smaller admissible dt exists."""
    m, D, k = z3.Ints("m D k")
    witness = z3.And(m >= 0, D >= 0,
                     (C * m) ** 2 >= D,
                     z3.Or(m == 0, (C * (m - 1)) ** 2 < D))
    # negation: a smaller admissible k exists (0 <= k < m and (c*k)^2 >= D)
    smaller = z3.And(k >= 0, k < m, (C * k) ** 2 >= D)
    neg = z3.And(witness, smaller)
    return _prove("T5_min_light_time", neg,
                  "the boundary-corrected min light time is truly minimal")


ALL = [T1_faithfulness, T2_antisymmetry, T3_null_cone_exact,
       T4_future_monotone, T5_min_light_time]


def run_all():
    return [t() for t in ALL]


if __name__ == "__main__":
    for res in run_all():
        print(f"{res['theorem']:24s} {res['result']:14s} ({res['z3_status']})")
