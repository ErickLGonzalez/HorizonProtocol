# H8-LIVE Report — Genuine Azure Multi-Region Capture

**Program:** HorizonProtocol · **Sprint:** H8-LIVE · **Date:** 2026-08-04  
**Claim class:** ENGINEERING_REFERENCE · **Empirical claim:** NONE  
**Verifier:** unmodified `horizon.capture_verify.verify_capture`

---

## 1. Regions and surveyed positions

Four Azure VMs in resource group `horizon-h8-live`, SKU `Standard_D2s_v3`
(Ubuntu 22.04). Surveyed LLH from Azure region published coordinates
(`position_source: azure-region-published`).

| node_id | Azure region | LLH (lat, lon, h_m) | role | ~distance from emitter |
|---|---|---|---|---|
| `us-east-1` | eastus | 37.3719, -79.8164, 90 | emitter | 0 km |
| `us-east-2` | centralus | 41.5908, -93.6208, 250 | intermediate | ~1273 km |
| `us-west-2` | westus2 | 47.2330, -119.8520, 100 | distant | ~3394 km |
| `eu-west-1` | **westeurope** | 52.3667, 4.8945, 80 | distant / intercontinental | ~6223 km |

**Region note:** North Europe (`northeurope`) returned `SkuNotAvailable` /
`QuotaExceeded` for every tried SKU. The intercontinental node was therefore
deployed to West Europe (Netherlands). Coordinates were updated to match the
physical region; they are not Ireland.

Public IPs at capture time (ephemeral, not security-sensitive):  
eastus `20.172.151.99`, centralus `130.131.232.163`, westus2 `20.51.107.131`,
westeurope `20.16.48.162`.

---

## 2. Clock synchronization

Both tiers used `chrony`. Measured uncertainty `u_ns` is **not** the tier
nominal: it is derived at capture time from chrony tracking as

```text
u_ns = max(1000, round(1e9 * (|root_dispersion| + |rms_offset| + |root_delay| + |last_offset|)))
```

and recorded per node in each capture's `measured_u_ns` / `clock_offsets_ns`,
and MAC-bound into each receipt body as `body.measured_u_ns`.
`scripts/verify_live.py` overlays only those authenticated measured values
into the registry before calling the unmodified verifier; missing or
unsigned uncertainty for a receipt contributor is a hard refusal (no
nominal-tier fallback).

### NTP tier

`chrony` pointed at common public NTP (`time.nist.gov`, `ntp.ubuntu.com`,
`time.google.com`) — Azure PHC deliberately disabled.

| node | stratum / ref | measured offset | measured u_ns |
|---|---|---|---|
| us-east-1 | 2 / time.google.com | +176 µs | ~5.0 ms |
| us-east-2 | 2 / time-c-b.nist.gov | −128 µs | ~25.1 ms |
| us-west-2 | 2 / time2.google.com | +33 µs | ~10.8 ms |
| eu-west-1 | 2 / time3.google.com | +395 µs | ~7.7 ms |

### PTP tier

`chrony` disciplined to `/dev/ptp_hyperv` (Azure host PHC). All four nodes
locked to `PHC0` stratum 1 before the committed PTP run.

| node | stratum / ref | measured offset | measured u_ns |
|---|---|---|---|
| us-east-1 | 1 / PHC0 | +2.3 µs | ~31 µs |
| us-east-2 | 1 / PHC0 | −2.7 µs | ~27 µs |
| us-west-2 | 1 / PHC0 | −5.1 µs | ~33 µs |
| eu-west-1 | 1 / PHC0 | +1.4 µs | ~118 µs |

---

## 3. Artifacts

| file | content |
|---|---|
| `data/h8_live_capture_NTP_1.json` | LIVE_CAPTURE, NTP tier, 4 receipts |
| `data/h8_live_capture_PTP_1.json` | LIVE_CAPTURE, PTP tier, 4 receipts (run 2, PHC-locked) |
| `certificates/h8_live_certificate.json` | primary (PTP) certificate |
| `certificates/h8_live_ntp_certificate.json` | NTP-tier certificate |
| `scripts/live_orchestrate.py` | quarantined multi-node orchestrator |
| `scripts/verify_live.py` | quarantined live verifier wrapper |

Capture channel: TCP port 9753, stdlib sockets only. Emitter stamps `t0_ns`
then broadcasts `bound_event_hash(payload_hash, t0_ns, p0_nm)` so receipts
authenticate the emission claim (erratum 2 of `capture_verify`).

---

## 4. Per-receipt verdicts (exact integer witnesses)

### NTP (`data/h8_live_capture_NTP_1.json`)

| node | verdict | dt_ns | u_ns | typical_floor_ns | vacuum_floor_ns | band_ns |
|---|---|---|---|---|---|---|
| us-east-1 | **APPARATUS_LIMITED** | 2 545 757 | 5 026 591 | 0 | 0 | 10 053 182 |
| us-east-2 | **ADMITTED** | 48 038 299 | 25 102 226 | 7 075 906 | 4 245 544 | 50 204 452 |
| us-west-2 | **ADMITTED** | 114 445 010 | 10 769 901 | 18 867 439 | 11 320 463 | 21 539 802 |
| eu-west-1 | **ADMITTED** | 135 541 165 | 7 690 696 | 34 595 139 | 20 757 083 | 15 381 392 |

Aggregate: **APPARATUS_LIMITED** (emitter co-located band).  
Headline: **eu-west-1 ADMITTED** — first intercontinental live receipt.

### PTP (`data/h8_live_capture_PTP_1.json`)

| node | verdict | dt_ns | u_ns | typical_floor_ns | vacuum_floor_ns | band_ns |
|---|---|---|---|---|---|---|
| us-east-1 | **ADMITTED** | 2 281 850 | 31 109 | 0 | 0 | 62 218 |
| us-east-2 | **ADMITTED** | 45 529 276 | 27 039 | 7 075 906 | 4 245 544 | 54 078 |
| us-west-2 | **ADMITTED** | 117 051 478 | 32 839 | 18 867 439 | 11 320 463 | 65 678 |
| eu-west-1 | **ADMITTED** | 121 957 404 | 118 222 | 34 595 139 | 20 757 083 | 236 444 |

Aggregate: **PASS**. Measured PHC `u_ns` is tens of microseconds on every node.

---

## 5. Tier transition — honest reading

H8-D's model predicted `us-east-2` APPARATUS_LIMITED (NTP) → ADMITTED (PTP)
under a **1.3× route-excess fiber model**. Live Internet RTTs are far larger
(~45–135 ms observed one-way stamp deltas vs ~7–35 ms fiber floors), so both
tiers place the intermediate and distant nodes **well above** the resolution
band → ADMITTED in both captures.

What *did* change with the tighter clock:

- Emitter (zero geometric floor): NTP **APPARATUS_LIMITED** (2.5 ms stamp
  delay inside a ~10 ms band) → PTP **ADMITTED** (same ~2.3 ms local
  processing delay now sits *outside* a ~62 µs band). That is the live
  analogue of the tier-resolution effect: the same physical delay is
  unresolved at NTP and resolved as "late but causal" at PTP.
- Distant / intercontinental ADMITTED holds at both tiers — the program's
  headline live result.

No honest receipt was REJECTED (falsifier F1 clear).

---

## 6. Authentication caveat

Receipts use the existing HMAC-SHA256 demo key derivation in
`horizon.signed_capture` (key = SHA-256 of a fixed prefix + `node_id`),
and the MAC covers `measured_u_ns` so a plaintext capture/MITM edit cannot
inflate the clock budget without forging the receipt. This proves the
plumbing and the H8-C spoof gate; it is **not** deployment-grade
authentication. Production target: independent per-VM Ed25519 private keys.

---

## 7. Limits (what this does and does not claim)

- Certifies that **real measured** multi-region timestamps are consistent
  with the causal geometry under the declared, measured clock budget.
- Does **not** claim evidence about physics, and does not claim the Internet
  path is near fiber light-time — measured RTTs show large route excess,
  which the gate correctly treats as ADMITTED rather than REJECTED.
- APPARATUS_LIMITED on the NTP emitter is correct behavior, not shortfall.
- Quarantine holds: `live_orchestrate.py` / `measure_now` are not imported
  by the verifier or CI.
- Existing H8 MEASURED_MODEL suite regenerated against the Azure
  coordinates and still passes unchanged in logic.

---

## 8. Reproduction sketch

```bash
# responders (started first)
python3 scripts/live_orchestrate.py --role responder --node-id us-west-2 --tier PTP

# emitter
python3 scripts/live_orchestrate.py --role emitter \
  --responders us-east-2:<ip> us-west-2:<ip> eu-west-1:<ip> \
  --tier PTP --run 1

python3 scripts/verify_live.py data/h8_live_capture_PTP_1.json
```
