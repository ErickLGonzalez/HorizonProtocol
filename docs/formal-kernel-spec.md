# C1 Engineering Specification — Machine-Checked Admissibility Kernel

**Program:** HorizonProtocol · **Benchmark:** C1 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE

## 1. Objective

The entire HorizonProtocol security stack reduces to one predicate,
`causally_admissible` (`horizon/geometry.py`) - a total, integer, branch-free
function small enough to *prove* correct rather than merely test. This
benchmark discharges that proof with the Z3 SMT solver, and binds it to the
shipped code so the verified spec and the running function cannot diverge.
See `formal/README.md` for the artifact layout and how to run it.

## 2. Method

Each theorem is posed as: assert the NEGATION of the claim and ask Z3 for a
model over the theory of integers (and, for T1, one auxiliary real variable
standing in for an exact square root). `unsat` means no counterexample exists
over ALL integers - the claim is proven for every possible input, not merely
tested on samples, which is what distinguishes this from `redteam`'s
adversarial *testing* (RT1/H9): a proof rules out a whole infinite class of
counterexamples at once; a fuzz test samples a finite, however large, subset
of it.

## 3. Theorems

- **T1, faithfulness:** the exact-integer squared predicate `(c*dt)^2 >= D` is
  equivalent to the real light-cone condition `c*dt >= sqrt(D)` on every
  integer input, with no rounding gap. This is why the integer method is not
  an approximation of the physics but an exact realization of it.
- **T2, antisymmetry:** no two distinct events are each in the other's strict
  future. Honestly scoped (not overclaimed): for a "strict future" relation
  this reduces to the irreflexivity of `>` on timestamps alone and does not,
  by itself, exercise the spatial comparison - proven anyway as a sanity
  check on the predicate as written.
- **T3, null-cone exactness:** an event exactly on the light cone is
  admissible; one squared-nanometer beyond is not - the boundary is sharp,
  with no float epsilon or rounding tolerance anywhere.
- **T4, future monotonicity:** if an event is admissible, giving it more time
  keeps it admissible - the future cone only grows.
- **T5, min-light-time minimality:** the boundary-corrected search algorithm's
  witness is genuinely the smallest admissible integer `dt` - no smaller value
  is also admissible.

## 4. Erratum: a vacuous theorem that always reported PROVEN

An earlier version of T3 posed its claim as a self-referential integer
comparison (`X >= X` and `NOT(X >= X+1)`, the SAME expression compared to
itself on both sides) rather than relating the predicate to an
independently-constrained distance value. This is a tautology of integer
arithmetic, true for ANY speed constant or ANY predicate shape - confirmed
concretely that the original query reported `unsat` ("PROVEN") even when the
admissibility comparison was deliberately perturbed by an arbitrary integer
bias, i.e. it would have reported PROVEN for a broken kernel exactly as
readily as for the real one. Reporting "PROVEN" for a theorem that isn't
actually checking the claimed property is a worse failure mode than not
having the proof at all, since it manufactures false assurance.

Fixed: T3 now routes the squared distance through genuine free integer
position-difference variables, so the query's satisfiability genuinely
depends on the predicate being checked. `formal/tests/test_kernel_proof.py`'s
`test_biased_predicate_is_caught` regression-tests this directly by rerunning
T3 against a deliberately-broken predicate and asserting it now correctly
reports a counterexample - the check that would have caught the original bug.
See `formal/README.md` and `formal/kernel_proof.py`'s module docstring for the
full analysis, and `formal/kernel.dfy` for the analogous (not independently
Dafny-reverified in this environment - see its own comment) fix in the
companion spec.

## 5. Trust boundary: the one non-stdlib dependency

`z3-solver` (pip) is confined entirely to `formal/` - never imported by
`horizon/`, `redteam/`, `mnemesis/`, or any file under `tests/`. It is an
OPTIONAL extra: `scripts/run_formal.py` exits 2 ("SKIPPED", not "FAIL") when
`z3-solver` is not installed, and `scripts/run_all.py` does not count a
SKIPPED proof gate against the aggregate, so a fresh clone with no extra
installs still reaches `ALL HORIZON GATES GREEN` on the pure-stdlib path.
When `z3-solver` IS installed, the proof runs for real and must pass like any
other gate.

## 6. Registered falsifiers

- F1: any theorem reporting COUNTEREXAMPLE (`sat`) → the kernel disagrees with
  its own specification; the highest-severity defect this program can record,
  since it would mean the load-bearing predicate is not what it claims to be.
- F2: a theorem reporting PROVEN that is insensitive to the actual predicate
  being verified (the section 4 erratum class) → the proof provides no real
  assurance even though it appears to pass; must be caught by a sensitivity
  regression test, not merely reviewed by inspection.
- F3: `formal/tests/test_proof_matches_code.py` finding any input on which the
  proven predicate and `horizon.geometry.causally_admissible` disagree → the
  verified spec and the shipped code have diverged.
- F4: `z3-solver` (or any other non-stdlib import) appearing anywhere outside
  `formal/`, or `scripts/run_all.py`/the main `unittest discover tests`
  requiring it to pass → violates the stdlib-only discipline this exception
  was scoped to.

## 7. Claim scope

C1 certifies that `causally_admissible`'s exact-integer formulation is
equivalent to the real-number light-cone condition on every integer input,
that its boundary is sharp, and that its future cone is monotone and
minimally-bounded - each a mathematical fact about the arithmetic, proven,
not sampled. It is NOT a proof that the physical world behaves as light-cone
geometry predicts (that is physics, outside any formal method's scope), NOT a
proof that the surrounding protocol layers (receipts, ledgers, certificates)
are secure (RT1/H9's adversarial testing addresses that, empirically, not by
proof), and NOT a claim that this kernel is deployed or deployable as a
cryptosystem.
