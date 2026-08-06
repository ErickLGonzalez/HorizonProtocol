# SP-1 Engineering Specification — Occultation (partition/reconnect in space)

**Program:** HorizonProtocol · **Sprint:** SP-1 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none ·
**Empirical claim:** NONE · **Builds on:** SP-0 (`Worldline`,
`causally_admissible_wl`, PR #11, merged) and MNX1's causal substrate
(`mnemesis/memory.py`, merged — see docs/mnemesis-convergence.md).

## 0. Why this is the Earth partition, in space

The #548 federated measurement (recorded in `docs/sp0-spec.md`'s section 0,
conclusion #2) showed: on a healthy link reorder ≈ 0, but across a
partition→reconnect it hit 0.845/0.989 — and the causal substrate held
false-supersession at 0 through it. An occultation is that same event with
a physical cause:

- **Earth partition:** link dropped (firewall/network split); both sides
  kept writing; reconnect delivered a burst of causally-old writes out of
  order.
- **Space occultation:** the ship passes behind a body; line-of-sight is
  physically blocked; both sides keep writing during blackout; when the
  ship re-emerges, the backlog arrives — and because of light-travel
  delay, even the first post-occultation signal reports events that are
  already old by the one-way light time.

SP-1 is not a new mechanism — it is the #548 partition/reconnect with (a)
occultation geometry deciding *when* the link is down, and (b) the
worldline + light-delay deciding *how stale* the reconnect burst is. The
substrate's job is unchanged: order by causal lineage, never by arrival,
and never false-supersede.

**Terminology mapping (handoff vocabulary → this repo's actual API):** the
handoff describes "the causal substrate's order contract (`may_supersede`)"
and CONTESTED/STALE verdicts. This repo's concrete embodiment of that
contract (MNX1, already merged) is `mnemesis.memory.CausalMemory.put(...,
supersedes=[...])`, which validates each claimed supersession via
`ordering.before(pred, w)` — that check *is* this repo's `may_supersede`
gate. A rejected claim (`verdict == "REJECTED"`,
`reason == "supersedes_non_ancestor"`) is this repo's form of "STALE,
never SUPERSEDE." `CausalMemory.get()` returning `{"status": "CONFLICT",
"candidates": [...]}` is this repo's form of "CONTESTED, retained, never
force-picked." SP-1 reuses this machinery unmodified — see
docs/mnemesis-convergence.md for the full mapping table.

## 1. What was built (additive, on top of SP-0)

### 1.1 Occultation geometry (`horizon/occultation.py`)
`is_link_down(t_ns, endpoint_a, endpoint_b, body, radius_nm)`: given two
worldlines (e.g. ship and ground station) and an occulting body (its own
`Worldline` center + integer `radius_nm`), the link is DOWN at `t_ns` iff
the minimum distance from the body's center to the straight segment
between the two endpoints' evaluated positions is `<= radius_nm`. Exact
integer test, no float, no sqrt, no division — compare squared quantities,
the same discipline as `horizon.geometry`:

```
AB = B - A, AC = C - A, ab2 = AB.AB, ac_ab = AC.AB
  ab2 == 0            -> compare AC.AC              (A, B coincide)
  ac_ab <= 0          -> compare AC.AC               (clamped to A)
  ac_ab >= ab2         -> compare BC.BC               (clamped to B)
  else (0 < ac_ab < ab2, ab2 > 0):
      AC.AC * ab2 - ac_ab**2  <=  r_nm**2 * ab2       (interior; no division)
```

`occultation_interval(t_lo, t_hi, endpoint_a, endpoint_b, body, radius_nm)`
finds the contiguous `[t_enter, t_exit]` within `[t_lo, t_hi]` during which
`is_link_down` is True, via exact integer bisection directly on that
boolean predicate (not a closed-form root solve — the pointwise test is
piecewise, so the boundary is located by search, not algebra; every query
along the way is still the exact test, so the result is exact regardless).

### 1.2 Light-delay delivery (`horizon/light_delay.py`)
`delivery_time_ns(t_emit, emitter, receiver, occultation=None)`: a signal
emitted by a moving node (`emitter`, e.g. the ship) at `t_emit` and
received by a stationary node (`receiver`, e.g. the ground station,
modeled as a `FixedWorldline`) arrives at `t_emit +
min_light_time_ns(p_emit, p_receive)` — reusing
`horizon.geometry.min_light_time_ns` (frozen, unmodified, imported) for
the exact ceil(dist/c). If `occultation` (an inclusive `(t_enter, t_exit)`
pair) is given and `t_emit` falls inside it, line-of-sight was down at the
moment of emission, so the signal cannot leave until it reopens: delivery
becomes `max(t_emit + light_time_at_emission, t_exit +
light_time_at_exit)`.

### 1.3 Composing with the substrate (reused, not rebuilt)
Each write carries a causal clock — `{"time_ns": t_emit, "pos_nm":
emitter.position_at(t_emit)}` — its TRUE emission event, stamped
regardless of when it is later delivered/processed. Writes are fed into
`mnemesis.memory.CausalMemory(GeometricOrdering())` — completely
unmodified — in *delivery* order (the order they actually arrive), but
each supersession claim is validated against the write's *causal* clock,
never its arrival time. `tests/test_sp1_occultation.py`'s SP1-D shows this
holds up across the occultation: a valid cross-node supersession is
admitted, a genuinely concurrent blackout pair is rejected in both
directions and retained as `CONFLICT`, and an asymmetric valid
supersession is recognized only in the correct direction.

## 2. The toy fixture (SP1-A..D) and its closed form

To keep SP1-A..D hand-verifiable, the ship flies a straight line offset in
`y` at a fixed `x`-distance `Dx` from the ground station (at the origin);
the occulting body sits at `(Dx, 0, 0)` with radius `r`. Because the ship
is offset in `x` from the ground-body axis, the closest point on the
ground-ship segment to the body always lands in the segment's *interior*
(never clamped to an endpoint) for the whole flyby, which collapses
`is_link_down`'s interior-projection branch to a clean threshold on
`y(t)^2`:

```
down(y)  <=>  y^2 * (Dx^2 - r^2)  <=  r^2 * Dx^2
```

`docs/../tests/test_sp1_occultation.py`'s `_closed_form_ymax` solves this
exactly for the largest `Y` satisfying it (via `math.isqrt` plus a
correction loop, the same style as `min_light_time_ns`), independent of
`occultation_interval`'s bisection search — SP1-A asserts the two methods
agree exactly, at both the toy scale (`Dx = 500` light-ns, ship at 0.1c)
and the interplanetary scale (SP1-E, Earth-Mars distance, ~Mars radius).

**Honest nuance — occultation vs. the kernel's necessary condition.**
`is_link_down` models a specific communication channel (the direct
line-of-sight segment) being blocked. The frozen kernel's light-cone test
(`causally_admissible`) is a *necessary*, not sufficient, condition for
causal influence in flat spacetime — the same scope limit that holds
throughout H1–H9 (a claimed "supersedes" edge is validated as not
*physically impossible*, not as proof a real signal actually arrived via
this specific channel). Consequently a pair can be `causally_admissible`
even while `is_link_down` was True at both endpoints' emission times (the
kernel doesn't know about the body, only about flat-spacetime reachability
by *some* path). SP1-D's asymmetric test
(`test_asymmetric_post_reconnect_supersession_respects_direction`) hits
exactly this: `ground@4750` (emitted during the toy blackout) is a valid
causal ancestor of `ship@6000` per the kernel, even though the *direct*
channel between them was still occulted at 4750. This is not a defect —
occultation and light-delay together determine when a message can actually
*arrive* through this channel (`light_delay.py`'s job); the kernel decides
what is *possible in principle* (its job, unchanged since H1). SP-1
composes both, it does not conflate them.

## 3. Tests (`tests/test_sp1_occultation.py`)

- **SP1-A:** `occultation_interval` matches the independent closed-form
  reference exactly, at both the toy and interplanetary scales; the
  interval boundary is exact (`is_link_down` flips exactly at `t_enter`/
  `t_exit`); `is_link_down`'s four branches (interior, clamped-to-A,
  clamped-to-B, degenerate) are each hand-verified with small integer
  vectors; a direct AST scan confirms zero floats in
  `occultation.py`/`light_delay.py` (F1).
- **SP1-B:** writes emitted outside `[t_enter, t_exit]` are delivered at
  the plain `t_emit + light_time`; writes emitted inside are delayed to
  `max(naive, t_exit + light_time_from_exit)`, always `>= t_exit`.
- **SP1-C:** a schedule of ship- and ground-authored writes straddling the
  toy occultation window is fed through `delivery_time_ns`; the resulting
  reorder (delivery order vs. emission order) is nonzero and EMERGES from
  composing the interval computed in SP1-A with the delivery function from
  SP1-B — nothing here hand-picks an arrival order (F2). A concrete
  instance is named: `ship@3400` (blackout) is emitted before `ground@4000`
  but arrives strictly after it.
- **SP1-D (the headline):** feeding the same schedule's writes through
  `CausalMemory`/`GeometricOrdering` (unmodified): a valid cross-node
  supersession across the gap is `ADMITTED`; a genuinely concurrent
  blackout pair (`ship@4700`/`ground@4750`, confirmed spacelike both
  directions against the kernel directly) is `REJECTED` in both directions
  and retained as `CONFLICT`, never force-picked; an asymmetric valid
  supersession is recognized only in the causally-correct direction (F3).
- **SP1-E:** the occultation geometry itself is exact at interplanetary
  scale (Earth-Mars distance, ~Mars radius — same closed-form
  cross-check as SP1-A); a post-occultation reconnect signal, built from
  the merged #10 benchmark's exact on-cone boundary vector so it evaluates
  the ship's `LinearWorldline` exactly to that point at the arrival event,
  is checked with `causally_admissible_wl` against the *evaluated*
  position — admitted exactly on the cone, rejected 1 nm past it (ties to
  SP0-D / #10).

## 4. Registered falsifiers

- **F1:** any float/sqrt in occultation or light-delay geometry → exactness
  defect. Checked by `tests/test_float_guard.py` (both modules now in
  `TRUSTED_MODULES`) and SP1-A's direct AST scan.
- **F2:** reorder in the reconnect burst that is *injected* rather than
  emergent from occultation-interval + light-delay → honesty defect (same
  rule as #544/#548). Checked by SP1-C computing reorder purely by
  composing SP1-A's interval with SP1-B's delivery function over a fixed
  emission schedule — no arrival order is set by hand.
- **F3:** any false-supersession across the occultation (a stale backlog
  write clobbering a newer one) → the substrate's core guarantee broke.
  Checked by SP1-D against ground truth computed directly from
  `causally_admissible` for every claim.
- **F4:** occultation interval or delivery time disagreeing with exact
  integer/rational reference → geometry defect. Checked by SP1-A/SP1-B's
  closed-form and direct-recomputation cross-checks.
- **F5:** the frozen kernel or the SP-0 wrapper modified → scope violation.
  Checked by `git diff --stat horizon/geometry.py horizon/worldline.py`
  showing zero changes — SP-1 adds two new files only.

## 5. What SP-1 does NOT do (deferred)

- **SP-2:** the trajectory-uncertainty envelope → `APPARATUS_LIMITED`
  (position known only as of last contact minus light time; a growing
  cone that collapses on new signal). SP-1 assumes the ship's worldline is
  known exactly; SP-2 makes it uncertain.
- **SP-3:** proper-time divergence between ship and ground clocks
  (relativistic), ordered by substrate lineage despite divergent clocks.

SP-1 establishes that the ship stays causally correct across a physical
blackout; SP-2 handles not-knowing-where-it-is between contacts; SP-3
handles the clocks themselves diverging.

## 6. Reproduction

```bash
python3 -m unittest tests.test_sp1_occultation -v
python3 -m unittest discover -s tests   # full suite
git diff --stat horizon/geometry.py horizon/worldline.py   # both empty
```
