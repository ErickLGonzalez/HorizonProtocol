# formal/ — Machine-Checked Admissibility Kernel

The entire HorizonProtocol security stack reduces to one predicate,
`causally_admissible`. This directory proves it correct.

## Contents
- `kernel_proof.py` — five theorems discharged by the Z3 SMT solver over the
  integers (T1 faithfulness, T2 antisymmetry, T3 null-cone exactness, T4 future
  monotonicity, T5 min-light-time minimality). Each is posed as an unsat query:
  `unsat` = no counterexample over ALL integers = proven.
- `kernel.dfy` — the human-readable Dafny formal spec of the same theorems.
  The Dafny toolchain is not available in this repository's environment, so
  this file has NOT been independently re-verified by `dafny verify` since the
  T3 fix described below - treat it as a best-effort companion to the
  enforced, CI-runnable Z3 proof, not as an independently machine-checked
  artifact in its own right, until someone with a Dafny installation reverifies it.
- `tests/test_kernel_proof.py` — runs the Z3 proof as a test (all PROVEN), plus
  a sensitivity regression test (see erratum below).
- `tests/test_proof_matches_code.py` — binds the proof to the shipped code two
  ways: the proven T1 predicate must equal `horizon.geometry.causally_admissible`
  on a boundary-concentrated, multi-magnitude SAMPLE (honestly not exhaustive -
  see its own erratum note), and `horizon.geometry.min_light_time_ns`'s actual
  return value must satisfy T5's witness conditions on the same sample (T5
  itself proves only that ANY value satisfying those conditions is minimal,
  never that this specific function produces one).

## The load-bearing theorem
T1 (faithfulness): the exact-integer squared predicate `(c*dt)^2 >= |dp|^2` is
*equivalent* to the real light-cone condition `c*dt >= sqrt(|dp|^2)` on every
integer input, with no rounding gap. This is why the integer method is not an
approximation of the physics but an exact realization of it.

## Erratum: a vacuous theorem that always reported PROVEN

An earlier version of T3 (null-cone exactness, in both `kernel_proof.py` and
`kernel.dfy`) posed its claim as a self-referential integer comparison -
`X >= X` and `NOT(X >= X+1)` where `X` was the SAME expression on both sides,
never an independently-constrained distance value. Both are tautologies of
integer arithmetic, true for ANY value of the speed constant or ANY predicate
shape - concretely verified (see the commit history) that the original query
reported `unsat` ("PROVEN") even when the admissibility comparison was
deliberately perturbed by an arbitrary integer bias, i.e. it would have
reported PROVEN for a broken kernel exactly as readily as for the real one.

Fixed: T3 now routes the squared distance through genuine free integer
variables (`dx, dy, dz` via `Dist2`/an independently-declared `D`), so the
query's satisfiability genuinely depends on the predicate being checked.
`tests/test_kernel_proof.py::test_biased_predicate_is_caught` regression-tests
this directly: it reruns T3 with a deliberate integer bias and asserts it now
correctly reports a counterexample - the check that would have caught the
original bug, and that guards against a future regression to a similarly
vacuous formulation.

T2 (antisymmetry) is honestly, not silently, a modest theorem: for a "strict
future" relation it reduces to the irreflexivity of `>` on timestamps alone
and does not, by itself, exercise the spatial light-cone comparison. It is
proven anyway as a sanity check on the predicate as written, not withheld, but
should not be read as a non-trivial result about the geometry the way
T1/T4/T5 are.

## Run
```
pip install z3-solver     # the ONE non-stdlib dependency in this repository,
                          # confined to this offline proof artifact - never
                          # imported by any runtime/verifier/test path outside
                          # formal/, and never required for scripts/run_all.py
                          # or the main `unittest discover tests` to pass
python3 kernel_proof.py
python3 -m unittest discover formal/tests
```
`scripts/run_formal.py` runs the same proof and test suite, emitting
`certificates/formal_certificate.json`. It is included as an OPTIONAL,
non-fatal step in `scripts/run_all.py`: if `z3-solver` is not installed, it is
reported as SKIPPED rather than failing the aggregate, preserving the
stdlib-only guarantee for anyone who clones the repository without installing
the optional extra. See `docs/formal-kernel-spec.md` for the claim scope and
registered falsifiers.
