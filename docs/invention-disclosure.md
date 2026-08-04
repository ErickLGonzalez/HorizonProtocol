# Invention Disclosure Document

**Not legal advice. Prepared to enable a patent attorney to assess eligibility
and draft claims. The inventor should verify all public-disclosure dates with
counsel before any further disclosure, as those dates may already constrain U.S.
and foreign filing options.**

---

## 1. Administrative

- **Working title:** Method and System for Certifying Distributed Event
  Provenance by Exact Light-Cone Consistency Under Measured Clock Uncertainty
- **Inventor:** Erick Gonzalez
- **Field:** distributed-systems security; network time/position attestation;
  event provenance verification
- **Related public disclosures (INVENTOR TO CONFIRM DATES WITH COUNSEL):**
  a public source repository (github.com/ErickLGonzalez/HorizonProtocol) and a
  manuscript intended for arXiv/journal submission describe the system. **These
  are prior public disclosures. In the U.S. a one-year grace period from the
  inventor's own disclosure may apply; most foreign jurisdictions apply absolute
  novelty and may already bar foreign filing. This is the first fact counsel
  must evaluate.**
- **Recommended immediate step:** a U.S. provisional application on the subject
  matter of Sections 4–6 below, filed before any further implementation
  disclosure, to secure a priority date and preserve options.

## 2. Problem addressed (the technical problem)

Distributed systems must decide whether a received event (a message, a telemetry
packet, a recorded datum) is consistent with having originated from the claimed
place and time, using nodes whose clocks are imperfectly synchronized. Existing
approaches fail in specific technical ways:

- Total-ordering consensus (e.g. blockchains) imposes a global order that does
  not physically exist between causally independent events, at high latency/energy
  cost.
- Timestamp systems that reason in floating-point with a fixed tolerance make the
  tolerance an attack surface and a source of cross-platform non-reproducibility.
- Systems that report a single accept/reject verdict cannot distinguish "this is
  physically impossible" from "the clock at this synchronization tier cannot
  resolve this geometry," and therefore either accept unresolvable events
  (false trust) or reject honest ones (false alarm).

The technical result sought: a reproducible, tamper-evident decision — for each
received event — of whether its measured arrival timing is consistent with the
speed-of-light causal geometry of its claimed origin, that (a) uses no floating
point in the security-critical decision, (b) is defined precisely relative to the
*measured* clock uncertainty at each node, and (c) explicitly distinguishes
physical impossibility from unresolvability.

## 3. Prior art the inventor is aware of (for the examiner's benefit)

- Position-based / relativistic cryptography: Chandran–Goyal–Moriarty–Ostrovsky
  (position verification; classical impossibility under collusion); Kent et al.
  (quantum tagging); Lunghi et al. (relativistic bit commitment).
- Distributed-systems time: Lamport clocks; vector clocks; conflict-free
  replicated data types (CRDTs); Google Spanner / TrueTime (bounded clock
  uncertainty exposed as an interval, commit-wait).
- Network timing: NTP, PTP (IEEE 1588); granted patents on network clock
  synchronization, time-source health monitoring, and precision synchronization.

**How the present invention differs (candidate points of novelty — for counsel to
test against a formal search):** none of the above (i) evaluates a *speed-of-light
causal-admissibility predicate in exact integer arithmetic on a nanometer/
nanosecond lattice*, (ii) derives an *apparatus-limited resolution band directly
from each node's measured clock uncertainty* and returns a distinct
unresolvability verdict, or (iii) decides rejection *solely against an absolute
in-vacuum light-time floor* while admitting under a medium-and-uncertainty budget.
The combination is the candidate invention.

## 4. Summary of the invention

A method and system for certifying distributed event provenance in which:

1. Each participating node has a **surveyed physical position** and a **clock**
   synchronized to a declared tier, with a **measured per-node uncertainty** `U`
   (e.g. obtained from the synchronization subsystem's own error estimate).
2. Positions are represented as **integers in a fine length unit** and times as
   **integers in a fine time unit**, chosen such that the speed of light is an
   **exact integer** in those units, so the causal test is exact integer
   arithmetic with **no floating point and no tolerance parameter** in the
   security-critical decision.
3. For a received event bearing a claimed origin (time `t0`, position `p0`) and a
   measured arrival (time `t_recv`, node position `p_node`), the system computes a
   **causal-admissibility decision** by comparing, in exact integers, the
   available propagation time against the squared spatial separation, and returns
   one of three verdicts:
   - **ADMITTED** — consistent with a physically possible signal path within the
     medium-speed and measured-uncertainty budget;
   - **REJECTED** — impossible even under the most favorable allowance, decided
     **solely against an absolute in-vacuum light-time floor** that no medium and
     no clock error can defeat, and accompanied by an **exact integer witness**;
   - **APPARATUS_LIMITED** — the measured clock uncertainty at this tier cannot
     resolve the geometry, determined by whether a perturbation of the measured
     arrival by ±`U` would change the admissibility outcome.
4. The system binds each measured arrival into a **signed receipt** and assembles
   the receipts for an event into a **verifiable certificate** that a third party
   re-checks from the certificate contents plus the public node registry alone,
   **without re-running the capture**, each verdict carrying its exact integer
   witness.
5. Optionally, verified events populate a **partial-order data structure** (a
   directed acyclic graph) in which a dependency edge is admitted only if it
   passes the same exact causal-admissibility test, and causally independent
   events are retained **concurrent** rather than force-ordered.

## 5. Detailed operation (enabling description)

**5.1 Exact lattice.** Represent position in nanometers and time in nanoseconds.
The speed of light is then exactly 299,792,458 (length-units per time-unit). For a
claimed origin event E0 = (t0, p0) and a receipt at node position p_node with
measured arrival t_recv, define the exact squared spatial separation
D = ‖p_node − p0‖² (integer) and the elapsed time dt = t_recv − t0. All subsequent
comparisons are integer.

**5.2 Two-floor decision (the core).** Two floors are computed, both exact:
- the **vacuum floor**: the minimum integer time for light in vacuum to span the
  separation (computed via integer square root with exact boundary correction);
  this is the *only* basis for REJECTED.
- the **medium/uncertainty allowance**: the arrival time adjusted by the measured
  clock uncertainty `U` in the claimant's favor and evaluated against an in-medium
  speed bound (an exact rational lower bound on signal speed in the physical
  channel, e.g. for optical fiber), for the ADMITTED determination.

A receipt is **REJECTED** only if, even after crediting the full measured
uncertainty `U` to the claimant, the arrival precedes the absolute vacuum floor —
i.e. it is impossible in any medium under any clock error within budget. This
guarantees no honest in-budget signal is ever rejected (a stated design
requirement).

**5.3 Apparatus-limited band.** The system determines whether the admissibility
outcome is robust to the measured clock error by testing whether perturbing the
arrival across a band of width proportional to `U` (in the exact premultiplied
units) would flip the verdict. If so, the verdict is **APPARATUS_LIMITED** — the
node's synchronization tier cannot resolve the geometry. This is what makes a
node with negligible signal flight-time (e.g. co-located) correctly report
"unresolvable" at coarse tiers, and what makes an intermediate-distance node
transition from unresolvable to admitted as synchronization tightens (e.g. from
millisecond NTP to microsecond PTP).

**5.4 Signed receipts and standalone certificate.** Each node signs its receipt
(event hash, node identity, surveyed position, measured arrival time, tier) with a
per-node key. The verifier checks signature authenticity, event binding, surveyed
position against the registry, and the two-floor causal decision, emitting a
certificate recording each verdict and its exact integer witness. A third party
re-verifies from the certificate and public registry alone.

**5.5 Empirical validation (reduction to practice).** The method was implemented
and run on physically separated networked computers in multiple geographic regions
across multiple continents, synchronized at two tiers (network time protocol and a
precision hardware clock). Verified certificates were obtained over intercontinental
paths; the apparatus-limited verdict behaved as specified across the two tiers,
including the predicted transition as synchronization tightened. This constitutes
an actual reduction to practice, not merely a paper design.

**5.6 Optional causal-ledger extension.** Verified events may be inserted into a
DAG in which an edge A→B is admitted only if B lies in A's exact future light cone
and strictly later; causally independent events are stored concurrent with
provenance and reconciled only by a later event in the causal future of all
conflicting candidates. (This extension may warrant separate claims per Section 7.)

## 6. Candidate independent-claim skeletons (for counsel to draft/refine)

*Illustrative only; not final claim language.*

**Claim A (method — verification).** A method of certifying provenance of an event
in a distributed system, comprising: at each of a plurality of nodes having a
surveyed position and a clock with a measured synchronization uncertainty,
measuring an arrival time of the event and generating a signed receipt binding the
event to the node's position, measured arrival time, and measured uncertainty;
representing positions and times as integers in units wherein the speed of light is
an exact integer; computing, in exact integer arithmetic, a causal-admissibility
decision comparing an uncertainty-adjusted elapsed time against a spatial
separation; classifying the receipt as rejected only when the arrival precedes an
absolute vacuum light-time floor after crediting the measured uncertainty, as
apparatus-limited when a perturbation of the arrival by the measured uncertainty
would change the decision, and as admitted otherwise; and assembling the receipts
into a certificate independently verifiable from its contents and a public node
registry without re-executing the measurement.

**Claim B (system).** A distributed system configured to perform Claim A, wherein
each node comprises a clock-synchronization subsystem reporting a measured
uncertainty used as said measured synchronization uncertainty.

**Claim C (data structure).** The method of Claim A, further comprising inserting
verified events into a directed acyclic graph wherein a dependency edge is admitted
only upon satisfying said exact causal-admissibility decision, and causally
independent events are retained as unordered concurrent entries with provenance.

**Dependent-claim ideas:** the exact units being nanometers/nanoseconds; the
in-medium speed bound being an exact rational; the vacuum floor computed by integer
square root with boundary correction; the per-node uncertainty obtained from a PTP
hardware clock; the transition of a verdict from apparatus-limited to admitted upon
tier change; the witness being an exact pair of integers re-checkable by a third
party.

## 7. Points of novelty to stress in prosecution (§101 strategy)

The application should, per current USPTO guidance, anchor eligibility in a
**concrete technical improvement to a technical field** (distributed-systems
security / network attestation), not in mathematics or efficiency:
- The decision is **tied to physical measurement** (measured clock uncertainty,
  surveyed position, measured arrival) — it is not a disembodied calculation and
  cannot be performed in the human mind (256-bit-scale exact integer arithmetic
  over continental geometry).
- The improvement is a **specific technical result**: a verification that never
  rejects an honest in-budget signal (two-floor design) and that explicitly
  reports unresolvability rather than guessing — solving a concrete false-trust/
  false-alarm failure of prior timestamp systems.
- The exact-integer lattice is an **unconventional implementation** that removes
  the tolerance parameter (an attack surface) — argue as the "significantly more"
  under Alice step two, framed as improving the reliability/security of the
  computer-implemented verification, analogous to the network-intrusion-detection
  example the USPTO treats as eligible.
- Avoid claiming the bare predicate/formula alone (most §101-exposed); always
  claim it within the measurement-and-certificate system.

## 8. Commercial applications (for value assessment)

Data-sovereignty attestation (proving data physically remained in a region);
tamper-evident event/content provenance (binding a recording's existence-event to
dispersed timing authorities); GPS-spoofing-resistant authentication for
infrastructure and vehicles; ordering/provenance in geo-distributed databases and
interplanetary/delay-tolerant networks.

## 9. What is NOT claimed (deliberately)

The underlying physics (causal-structure results, any law of nature) and the bare
mathematical predicate as such are not claimed and are treated as defensive
publication. Counsel should confirm this scoping and the disclosure-date analysis
before filing.

---

*Prepared as an enabling technical disclosure for patent counsel. The inventor
should (1) confirm all public-disclosure dates, (2) obtain a professional prior-art
search, and (3) consider a provisional filing on Sections 4–6 before further
disclosure. This document is not a legal opinion and does not itself establish
patentability.*
