# H8 Engineering Specification — Genuine Multi-Node Capture

**Program:** HorizonProtocol · **Benchmark:** H8 · **Tier:** BENCHMARK ·
**Claim class:** ENGINEERING_REFERENCE · **Promotion:** none · **Empirical claim:** NONE

## 1. Objective

Produce cone certificates from MEASURED (not computed, not synthetic-fixture)
timestamps across real, geographically separated nodes, with signed receipts and
tiered clock uncertainty. This is the program's first contact with real timing.

## 2. Signed capture (A2)

Each node signs `(event_hash, node_id, node_pos_nm, recv_time_ns, tier)` with a
per-node key (HMAC-SHA256 stdlib stand-in; Ed25519 is the deployment target).
Without the key a co-located adversary cannot forge a receipt - this makes the
spoof control (H8-C) meaningful. The key is derived deterministically from
`node_id` (DEMO ONLY, exactly `horizon.stations.demo_registry`'s pattern) - a
real deployment issues independent, unpredictable per-node keys. The live path
(`measure_now`, `scripts/live_capture.py`) reads real system time, is
non-deterministic, and is never imported by the verifier. Gates run against
COMMITTED captures for determinism.

## 3. Honest measurement model

Committed captures (`MEASURED_MODEL`) apply: fiber speed `c_eff = 3/5` (matching
`horizon.measure`'s frozen conservative bound), route excess 1.3x straight-line,
and a deterministic per-node clock error within the tier's `U_ns`. Real arrivals
are therefore LATER than vacuum light time. `scripts/live_capture.py` is the
on-ramp to replace the model with genuine measurements.

## 4. The budgeted gate: two floors, two different jobs (SOUND)

`horizon/capture_verify.py` classifies each receipt using two exact-integer
floors, reused rather than reimplemented:

- `vacuum_floor_ns` (`horizon.geometry.min_light_time_ns`) is the ONLY floor
  that can ever justify REJECTED - nothing, in any medium, travels faster than
  this.
- `typical_floor_ns` (`horizon.measure.min_transit_time_ns_eff`, at the same
  frozen `c_eff = 3/5` H5/H6 use) is the declared, ordinary real-medium
  expectation.

Unlike `horizon.measure`'s certificate gate - which only needs "is this
consistent with SOME legitimate path," treating the whole gap between the two
floors as one undifferentiated APPARATUS_LIMITED band - H8 additionally asks a
narrower question the tier-transition gate (H8-D) depends on: is THIS tier's
clock precise enough to confidently place the arrival at-or-after the
conservative bound, or could ordinary jitter of size `u_ns` explain the whole
discrepancy? That is answered by a band of width `2*u_ns` centered on the
(adjusted) arrival, derived from the same nanosecond quantities - never a
squared one (section 4a). This is what lets a co-located node (zero flight
distance, both floors zero) correctly read APPARATUS_LIMITED at every tier
rather than trivially ADMITTED, and what lets a real intermediate node move
from APPARATUS_LIMITED to ADMITTED as the tier tightens. Whichever question is
being asked, REJECTED is decided ONLY by the absolute vacuum floor - never by
the conservative bound or its band.

```
dt_adjusted_ns = (recv_time_ns - t0_ns) + u_ns
REJECTED           if dt_adjusted_ns < vacuum_floor_ns
APPARATUS_LIMITED  if |dt_adjusted_ns - typical_floor_ns| <= 2*u_ns  (and not REJECTED)
ADMITTED           otherwise
```

### 4a. Erratum: c_eff is a lower bound on real-medium speed, not a ceiling - and it is trusted caller input, never the capture's own claim

An earlier version of `capture_verify.classify()` reimplemented the budgeted
decision from scratch as a single SQUARED margin (`(c_eff*eff)^2 - dist^2`)
against a single `c_eff`-derived floor, with no reference to the absolute
vacuum floor at all. Two bugs followed directly from reimplementing gate math
that `horizon.measure` had already solved correctly once:

1. **c_eff misused as a ceiling.** Any receipt landing outside the derived
   band around the conservative `c_eff` floor was REJECTED - including a
   genuine, honest signal that happened to travel faster than the
   *conservative* `3/5` bound but still well below vacuum `c` (`c_eff` is a
   declared LOWER bound on real-medium speed, not the fastest anything can
   travel). Concretely: a 475 km signal genuinely travelling at `0.8c` (real,
   honest, comfortably sub-vacuum) was REJECTED outright at PTP/GNSS-tier
   clock precision by the old `classify()` - a real, in-budget signal,
   REJECTED. This is exactly the failure mode `horizon.measure`'s own
   docstring already documents fixing once for H5 (registered falsifier F1
   exists precisely to catch it: "a real in-budget signal REJECTED -> gate/
   budget defect"). Fixed: REJECTED is now decided ONLY against
   `vacuum_floor_ns`, which no real signal, however fast, can ever beat.

2. **c_eff read from untrusted input.** `verify_capture` read `c_eff` directly
   from the `capture` object being classified (`capture["c_eff"]`) rather than
   from a TRUSTED caller-supplied parameter - the exact trust-boundary
   violation `horizon.measure`'s own docstring warns against: "if its own
   claimed ... speed bound were used to classify its own receipts, a forger
   could simply declare ... a superluminal `c_eff`." Fixed: `verify_capture`
   now takes `c_eff_num`/`c_eff_den` as trusted caller input (default:
   `horizon.measure`'s frozen `3/5` bound, matching H8's own declared model),
   exactly like `verify_measured_certificate`'s `node_params`. A `c_eff`
   recorded inside a `capture` blob is provenance only, describing what model
   generated the data - never fed into the classification decision.

`tests/test_h8e_trust_boundary.py` regression-tests both: a declared
superluminal `c_eff` inside a capture has zero effect on any verdict, and a
genuine `0.8c` signal is ADMITTED (not REJECTED) at a sufficiently precise
tier, while a genuinely-impossible arrival is still REJECTED where the tier
can resolve it.

## 5. Tiers and the resolution finding

Tiers: NTP (U≈5 ms), PTP (U≈50 µs), GNSS (U≈1 µs). Consequences, all
demonstrated over the same real-geography registry (`data/h8_nodes.json`):

- A co-located node (zero flight distance) is APPARATUS_LIMITED at EVERY tier
  - no time-of-flight means no distance attestation, at any clock precision.
  Correct physics, not a defect (and, per section 4, not something a plain
  two-floor comparison alone can express, since both floors are zero).
- An intermediate node (us-east-2, ~475 km, ~2.6 ms fiber flight) is
  APPARATUS_LIMITED at NTP (5 ms clocks cannot resolve it) and ADMITTED at PTP
  (50 µs clocks resolve it) - the tier transition (H8-D).
- Distant nodes (>3000 km) are ADMITTED at all tiers (flight >> clock error).

## 6. Gates

- H8-A: signed receipt round-trip; any tamper breaks the signature; committed
  capture replays identically; ≥3 real nodes at real separations.
- H8-B: honest capture yields only ADMITTED / APPARATUS_LIMITED (no spurious
  REJECTED for a real in-budget signal); at least one node is APPARATUS_LIMITED.
- H8-C: rogue-key spoof (co-located adversary claiming a distant node) REJECTED
  at the signature gate.
- H8-D: APPARATUS_LIMITED→ADMITTED transition across tiers; verifier imports no
  live-capture path.
- H8-E: trust-boundary and real-fast-signal regression coverage for the
  section 4a erratum.

## 7. Registered falsifiers

- F1: a real in-budget signal REJECTED → gate/budget defect.
- F2: a co-located spoof ADMITTED at a tier whose U should resolve it → security defect.
- F3: capture non-determinism on replay of a committed dataset.
- F4: any raw measured time presented as a vacuum-light result (must carry c_eff).
- F5: `capture_verify.classify`/`verify_capture` REJECTING any receipt on a
  basis other than the absolute vacuum floor, or reading `c_eff` from the
  untrusted `capture` object rather than trusted caller input → reintroduces
  the section 4a erratum.

## 8. Claim scope

Certifies that the signed-capture + budgeted-gate pipeline executes and
satisfies its gates over a physically-consistent measurement model, and
provides the live on-ramp. It is NOT yet a genuine live-capture result (that
requires provisioning real hosts and running `scripts/live_capture.py`); the
committed captures are a labeled stand-in. Not a deployed system, not a
security proof, not evidence about physics.
