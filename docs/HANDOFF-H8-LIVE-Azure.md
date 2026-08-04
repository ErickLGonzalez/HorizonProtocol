# HorizonProtocol — Coding-Agent Handoff: Genuine Live Capture on Azure VMs (Sprint H8-LIVE)

**Repo:** github.com/ErickLGonzalez/HorizonProtocol (H8 overlay merged)
**Goal:** produce the program's **first non-synthetic cone certificate** — a
capture whose receipt timestamps were *measured on real, geographically separated
Azure VMs*, not computed or modeled. This converts H8's labeled `MEASURED_MODEL`
into `LIVE_CAPTURE` using the existing verifier unchanged.

**You are running on real infrastructure.** Unlike every prior sprint, this one
faces real clock error, real network jitter, and real route excess. The
engineering is 20% code and 80% honest measurement discipline. Read Section 5
(interpretation) before you run anything — the "expected" result is not a clean
PASS, and mistaking that for failure is the main risk.

---

## 0. Non-negotiables (unchanged from the H-series)

1. **Stdlib only.** Python ≥ 3.9. No pip installs in `horizon/`, `tests/`, or the
   capture path. Chrony/NTP config is OS-level, not a Python dependency.
2. **Exact integer lattice.** Positions in nanometers, times in nanoseconds, c =
   299,792,458 exact. You do not touch the gate arithmetic — it is machine-checked
   (see `formal/`). You supply *measured inputs* to it.
3. **The verifier is already written and correct.** `horizon/capture_verify.py`
   (`verify_capture`, `classify`) is the trusted path. Do NOT modify it. Your job
   is to feed it real receipts and record what it says.
4. **Quarantine holds.** The live capture path (`scripts/live_capture.py`,
   `signed_capture.measure_now`) is HEURISTIC and must never be imported by the
   verifier or by CI. Keep it that way.
5. **Honesty labels survive.** A live capture is marked `origin: LIVE_CAPTURE`
   with real ISO timestamps and the measured clock offsets. It is never presented
   as anything cleaner than it is.
6. **No push.** Deliver artifacts + a report; the repo owner commits.

---

## 1. Infrastructure to provision

**Minimum: 3 Azure VMs in genuinely separated regions** (4 is better — it lets
one node be the intermediate-distance case that demonstrates the tier
transition). Recommended mapping to the existing `data/nodes.json` node IDs so the
surveyed positions already exist:

| node_id in repo | Azure region | approx (lat, lon) | role |
|---|---|---|---|
| `us-east-1` | East US (Virginia) | 37.37, -79.82 | **emitter** (frame origin) |
| `us-east-2` | Central US / East US 2 | ~41.6, -93.6 | intermediate (~1000 km) |
| `us-west-2` | West US 2 (Washington) | 47.23, -119.85 | distant (~3700 km) |
| `eu-west-1` | North Europe (Ireland) | 53.34, -6.26 | distant (~5000 km) |

**Important:** the repo's `nodes.json` uses AWS-flavored coordinates. Update it
with the **actual Azure region coordinates** you deploy to (Azure publishes region
lat/long; or read the VM's cloud metadata). The surveyed position must match where
the VM physically is, or the gate is testing fiction. Record the source of each
coordinate in the capture metadata (`position_source: "azure-region-published" |
"metadata-service" | "manual"`).

**VM size:** smallest general-purpose SKU is fine (B1s/B2s). This is a timing
experiment, not a compute one.

**Networking:** the emitter must be able to reach each responder over a known
port. Use a simple TCP or UDP channel (stdlib `socket`). Open the chosen port in
each VM's Network Security Group. Prefer public IPs with NSG rules restricting
source to your other VMs' IPs.

---

## 2. The hard part: clock synchronization

Everything depends on the VMs sharing a time reference tighter than the geometry
you are trying to resolve. Continental light-travel is ~3–20 ms; **default Azure
NTP (~1–5 ms error) is comparable to the signal**, which is exactly why the honest
result at this tier is APPARATUS_LIMITED (Section 5). To get past that you must
tighten the clock.

**Tier ladder — do as many as feasible, record which tier each capture used:**

- **NTP tier (baseline, always do this).** Azure VMs sync to the Azure host time
  or `time.windows.com` / `ntp.ubuntu.com`. Install/verify `chrony`, point all
  nodes at the *same* stratum-1 sources, and record `chronyc tracking` output
  (the estimated error) into each node's `u_ns`. Declared U ≈ 2–5 ms.
- **PTP tier (the payoff, if the region supports it).** **Azure provides a
  precision host clock via PTP** on many modern VM SKUs, exposed as
  `/dev/ptp_hyperv` (Linux). Configure `chrony` to discipline the system clock to
  that PTP source. This can reach tens of microseconds. Declared U ≈ 20–50 µs.
  This is the tier that moves the intermediate node from APPARATUS_LIMITED to
  ADMITTED — the headline result.
- **Do not fake the tier.** `u_ns` must be the *measured* clock uncertainty from
  `chronyc tracking` / PTP status at capture time, not the tier's nominal value.
  Record both the nominal tier and the measured offset.

**Measure, don't assume:** immediately before and after each capture run, record
each node's clock offset estimate. If offset drifted more than U during the run,
discard and re-run. Log all of this into the capture metadata.

---

## 3. The capture protocol

The existing `scripts/live_capture.py` stamps a single node's receipt. You will
wrap it into a coordinated multi-node run. Build one new script,
`scripts/live_orchestrate.py` (stdlib only), that implements:

**Emitter side (runs on `us-east-1`):**
1. Construct a payload (e.g. `{"experiment": "H8-LIVE", "run": <n>, "nonce":
   <random>}`), compute its `event_hash` = SHA-256 of canonical JSON (reuse
   `horizon.events.event_hash`).
2. Record the emission time `t0_ns` = `time.time_ns()` at the instant of
   broadcast, and the emitter's surveyed position `p0_nm`.
3. Broadcast the `event_hash` (and t0 for reference) to each responder over the
   socket channel.

**Responder side (runs on each node incl. the emitter as its own responder):**
4. On receipt of the `event_hash`, immediately call `measure_now(node_id, pos,
   event_hash, tier)` → a signed receipt stamped with local `time.time_ns()`.
5. Return the signed receipt to the emitter (or write it to a shared collection
   point — a simple approach: each responder POSTs its receipt line back over the
   same socket; the orchestrator collects them).

**Collection:**
6. The orchestrator assembles the capture JSON:
   ```
   {
     "origin": "LIVE_CAPTURE",
     "captured_at": "<ISO8601 UTC>",
     "event_hash": "<hash>",
     "t0_ns": <emitter emission time>,
     "p0_nm": [<emitter position>],
     "c_eff": [3, 5],              // fiber lower bound; keep unless you justify another
     "route_excess_note": "measured RTTs recorded separately; c_eff accounts for medium",
     "tier_nominal": "NTP" | "PTP",
     "clock_offsets_ns": { "<node_id>": <measured offset from chronyc/ptp> },
     "receipts": [ <signed receipt per node> ]
   }
   ```
7. Write it to `data/h8_live_capture_<tier>_<runid>.json`. This is a committed
   artifact (the whole point is a durable, verifiable live record).

**Key correctness requirement:** `t0_ns` and each `recv_time_ns` must be on the
**same synchronized clock domain**. Because each is stamped on a different VM, the
synchronization from Section 2 is what makes the subtraction meaningful. Record
the per-node clock offset so the analysis (and any reader) can see the error
budget explicitly.

---

## 4. Verification (uses the existing verifier — do not modify it)

Build `scripts/verify_live.py` that:
1. Loads the live capture JSON and the node registry (`build_frame.load_registry`,
   after you update `nodes.json` with real Azure coordinates + measured `u_ns` per
   node from the clock-offset log).
2. Calls `verify_capture(capture, registry)` — the band is auto-derived from each
   node's `u_ns`, so no manual tolerance.
3. Prints and saves the per-receipt verdicts (ADMITTED / REJECTED /
   APPARATUS_LIMITED) with their exact integer witnesses, and the aggregate.
4. Emits `certificates/h8_live_certificate.json` mirroring the H8 certificate
   schema but with `capture_origin: "LIVE_CAPTURE"`, the measured `clock_offsets`,
   the tier, and the real `captured_at`.

**Signature integrity:** the responders sign with the same per-node key derivation
already in `signed_capture.py` (HMAC stand-in). For a real deployment note in the
report that Ed25519 with per-VM private keys is the production target; the HMAC
demo keys are shared-secret and only prove the plumbing. (Do not block the
experiment on this — but state it.)

---

## 5. Interpreting the result — READ BEFORE RUNNING

The honest, expected outcomes, so you recognize success:

- **NTP tier → mostly APPARATUS_LIMITED is a SUCCESS, not a failure.** At ~2–5 ms
  clock error, continental light-travel (3–20 ms) is only marginally resolvable
  and metro distances (~1–3 ms) are *not* resolvable. The verifier correctly
  reporting "the clock cannot resolve this geometry" is the discipline working
  exactly as designed. Do not tune U downward to force ADMITTED — that would be
  faking resolution the clock does not have.
- **The distant nodes (us-west-2 ~3700 km ≈ 12 ms fiber, eu-west-1 ~5000 km ≈
  28 ms fiber) may ADMIT even at NTP**, because their flight time exceeds the
  clock error. That is a genuine, real-measurement ADMITTED — the thing the whole
  program was building toward. **One real ADMITTED intercontinental receipt is the
  headline.**
- **The tier transition is the crown result.** Run the same geometry at NTP and
  then at PTP. The intermediate node (`us-east-2`, ~1000 km, ~5 ms fiber) should
  move APPARATUS_LIMITED (NTP) → ADMITTED (PTP). Demonstrating that *with real
  clocks* is the strongest possible outcome and directly validates the H8-D
  simulation against reality.
- **A REJECTED for an honest node means something is wrong** — most likely a clock
  offset larger than declared U (a node's clock is skewed beyond its budget), or a
  surveyed position that doesn't match the VM's real location. Investigate offset
  logs and coordinates before suspecting the gate. A true honest signal must never
  be REJECTED (that is falsifier F1).
- **A spoof control, if you run one:** stand up a 4th process co-located with the
  emitter but claiming a distant node's ID/position, signing with a key it does
  not legitimately hold → must be REJECTED at the signature gate (already proven
  in H8-C; reproducing it live is a nice-to-have).

---

## 6. Deliverables

1. `scripts/live_orchestrate.py` and `scripts/verify_live.py` (stdlib only,
   quarantined from the verifier path and CI).
2. Updated `data/nodes.json` with real Azure region coordinates and their source.
3. At least one committed `data/h8_live_capture_*.json` with
   `origin: LIVE_CAPTURE`, real timestamps, and measured per-node clock offsets.
   Ideally two: one NTP-tier and one PTP-tier over the same geometry.
4. `certificates/h8_live_certificate.json` from the real capture.
5. A short `docs/h8-live-report.md` recording: regions used, coordinate sources,
   sync method and measured offsets per node, per-receipt verdicts with witnesses,
   the tier-transition result if achieved, and an honest limits paragraph.
6. **Zero changes** to `horizon/capture_verify.py`, `horizon/geometry.py`, or any
   existing test. Confirm the existing H8 suite still passes unchanged.

## 7. Definition of done

- A cone certificate exists whose receipts were measured on ≥3 real Azure VMs in
  ≥3 regions, verified by the unmodified `verify_capture`.
- At least one intercontinental receipt is genuinely ADMITTED (real
  measurement, not model).
- The per-node measured clock offsets are recorded and each `u_ns` reflects the
  *measured* uncertainty, not a nominal guess.
- If PTP was available: the `us-east-2` (or nearest ~1000 km node)
  APPARATUS_LIMITED→ADMITTED transition is demonstrated across the NTP and PTP
  captures.
- The report states honestly what tier was reached, what resolved, what did not,
  and why — with APPARATUS_LIMITED framed as correct behavior, not shortfall.

## 8. Prohibited (firewall)

- Do not modify the verifier or the machine-checked kernel to make results look
  cleaner.
- Do not set `u_ns` smaller than the measured clock offset to force ADMITTED.
- Do not label a modeled or hand-adjusted capture `LIVE_CAPTURE`.
- Do not import the capture/orchestration path into the verifier or CI.
- Do not claim the HMAC-signed demo receipts constitute deployment-grade
  authentication (state Ed25519 as the target).
- Do not present any of this as evidence about physics; it certifies that real
  measured timings are consistent (or not) with the causal geometry under a
  declared clock budget.

---

### Quick-start command sketch (adapt to your orchestration choice)

```bash
# on each VM, once:
#   - install chrony, point at common NTP (and configure PTP /dev/ptp_hyperv if available)
#   - clone the repo, cd into it
#   - open the chosen socket port in the NSG

# emitter (us-east-1):
python3 scripts/live_orchestrate.py --role emitter \
    --responders us-east-2:<ip> us-west-2:<ip> eu-west-1:<ip> \
    --tier NTP --run 1

# each responder (started first, listening):
python3 scripts/live_orchestrate.py --role responder --node-id us-west-2 --tier NTP

# after collection, on any host with the capture JSON:
python3 scripts/verify_live.py data/h8_live_capture_NTP_1.json
# -> prints per-receipt verdicts + writes certificates/h8_live_certificate.json
```

*End of handoff. Invariants: measure the clock and record its error; feed real
timestamps to the unmodified verifier; let APPARATUS_LIMITED stand where the clock
cannot resolve; and never dress a measurement up as cleaner than it is.*
