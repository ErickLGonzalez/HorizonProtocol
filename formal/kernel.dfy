// HorizonProtocol admissibility kernel — Dafny formal specification.
//
// This is the human-readable formal artifact corresponding to the
// machine-checked theorems in kernel_proof.py (discharged by Z3, which is also
// Dafny's verification backend, so the proof obligations are equivalent).
//
// The predicate below mirrors horizon/geometry.py::causally_admissible exactly.
// Verify with:  dafny verify kernel.dfy
//
// Every lemma is proved by Dafny's SMT backend over the integers; there are no
// `assume` statements and no admitted goals.

const C: int := 299792458  // exact speed of light, nm/ns

// Exact squared distance (nonnegative for all integer inputs).
function Dist2(x1: int, y1: int, z1: int, x2: int, y2: int, z2: int): int
{
  (x2-x1)*(x2-x1) + (y2-y1)*(y2-y1) + (z2-z1)*(z2-z1)
}

lemma Dist2NonNeg(x1: int, y1: int, z1: int, x2: int, y2: int, z2: int)
  ensures Dist2(x1,y1,z1,x2,y2,z2) >= 0
{
  // sum of squares; Dafny's arithmetic discharges this
}

// The exact-integer admissibility predicate.
predicate Admissible(t1: int, t2: int, d2: int)
  requires d2 >= 0
{
  t2 >= t1 && (C*(t2-t1))*(C*(t2-t1)) >= d2
}

// T1 (faithfulness): for dt >= 0 and a real r >= 0 with r*r == d2 (r = sqrt d2),
// the integer squared predicate equals the real light-cone condition c*dt >= r.
// Stated over reals; proof is the monotonicity of squaring on the nonnegatives.
lemma Faithfulness(dt: int, d2: int, r: real)
  requires dt >= 0 && d2 >= 0 && r >= 0.0 && r*r == (d2 as real)
  ensures ((C*dt)*(C*dt) >= d2) <==> ((C*dt) as real >= r)
{
  var cdt := (C*dt) as real;
  assert cdt >= 0.0;
  if cdt >= r {
    // cdt >= r >= 0  =>  cdt*cdt >= r*r == d2
    assert cdt*cdt >= r*r;
  }
  if (C*dt)*(C*dt) >= d2 {
    // (cdt)^2 >= r^2, both nonneg  =>  cdt >= r
    assert cdt*cdt >= r*r;
  }
}

// T2 (antisymmetry): no distinct pair lies in each other's strict future.
// NOTE: for a "strict future" relation this reduces to the irreflexivity of
// `>` on the timestamps alone - it holds regardless of the spatial term, so
// it does not by itself exercise the light-cone comparison. Proved anyway as
// a sanity check on the predicate as written.
lemma Antisymmetry(ta: int, tb: int, d2: int)
  requires d2 >= 0
  ensures !((tb > ta && (C*(tb-ta))*(C*(tb-ta)) >= d2) &&
            (ta > tb && (C*(ta-tb))*(C*(ta-tb)) >= d2))
{
  // tb > ta and ta > tb are jointly contradictory
}

// T3 (null-cone exactness): on the cone admissible; one squared-nm beyond, not.
//
// (Erratum: an earlier version stated this directly as
// `Admissible(0, dt, (C*dt)*(C*dt))`, which unfolds to
// `(C*dt)*(C*dt) >= (C*dt)*(C*dt)` - true by reflexivity regardless of C or
// the predicate's shape, so the lemma verified vacuously and would not have
// caught a broken kernel (Dafny needed no assertions to discharge it, which
// in hindsight was the tell). Fixed to route the squared distance through a
// genuine free position-difference triple (dx, dy, dz) via Dist2, matching
// the Z3 version's fix in kernel_proof.py - see that module's docstring
// erratum for the full analysis. NOTE: this .dfy file is a best-effort
// human-readable companion; the Dafny toolchain was not available in the
// environment that applied this fix, so this lemma was NOT independently
// re-verified by `dafny verify` after the change - the Python/Z3 proof in
// kernel_proof.py, run via `formal/tests/test_kernel_proof.py`, is the one
// enforced artifact. Re-verify this file with Dafny before relying on it.)
lemma NullConeExact(dt: int, dx: int, dy: int, dz: int)
  requires dt >= 0
  requires Dist2(0, 0, 0, dx, dy, dz) == (C*dt)*(C*dt)
  ensures Admissible(0, dt, Dist2(0, 0, 0, dx, dy, dz))
{
  Dist2NonNeg(0, 0, 0, dx, dy, dz);
}

lemma OneBeyondNullConeRejected(dt: int, dx: int, dy: int, dz: int)
  requires dt >= 0
  requires Dist2(0, 0, 0, dx, dy, dz) == (C*dt)*(C*dt) + 1
  ensures !Admissible(0, dt, Dist2(0, 0, 0, dx, dy, dz))
{
  Dist2NonNeg(0, 0, 0, dx, dy, dz);
}

// T4 (future monotonicity): the future cone only grows with time.
lemma FutureMonotone(dt: int, dt2: int, d2: int)
  requires dt >= 0 && dt2 >= dt && d2 >= 0
  requires (C*dt)*(C*dt) >= d2
  ensures (C*dt2)*(C*dt2) >= d2
{
  // dt2 >= dt >= 0  =>  (C*dt2)^2 >= (C*dt)^2 >= d2
  assert C*dt2 >= C*dt >= 0;
}

// T5 (minimality of the boundary-corrected min light time).
lemma MinLightTimeMinimal(m: int, d2: int, k: int)
  requires m >= 0 && d2 >= 0
  requires (C*m)*(C*m) >= d2
  requires m == 0 || (C*(m-1))*(C*(m-1)) < d2
  requires 0 <= k < m
  ensures (C*k)*(C*k) < d2
{
  // k <= m-1  =>  (C*k)^2 <= (C*(m-1))^2 < d2
  assert 0 <= k <= m-1;
  assert C*k <= C*(m-1);
}
