# Four-L40S TV Royale data pilot — 2026-08-24

## Decision

The Prime Intellect `4x L40S 48 GB / 46 vCPU / 288 GB RAM` shape is accepted
for bounded TV Royale extraction with **three independent extractors per GPU**.
It is not yet authorized for unattended bulk training-data production because
replay-disjoint automatic card-identity precision remains too low.

The pod was terminated after all owned artifacts were copied and hashed. The
run cost was **$3.60**, leaving **$7.55** in the personal Prime wallet.

## Throughput evidence

Exact source: `hTG8dM4KtM4`, 320.353 seconds, 3,204 semantic frames at 10 Hz.
Runtime: Python 3.12.13, Torch 2.10.0+cu128, torchvision 0.25.0+cu128,
OpenCV 5.0.0, Ultralytics 8.1.24.

| Shape | Matches | Outer wall | Aggregate games/hour |
|---|---:|---:|---:|
| one process per GPU | 4 | 196.324 s | 73.35 |
| two processes per GPU | 8 | 232.241 s | 124.01 |
| three processes per GPU | 12 | 270.074 s | **159.96** |

The 12-process arm preserved identical aggregate coverage in all 12 workers:
36,760 policy-facing entities, 52,251 filtered UI/support proposals, 17,312 HP
observations, 25,802 typed identities, and seven complete source actions. It
used about 9.4 GB per GPU. Larger batches were not useful: under the matched
four-way screen, batch 16 produced about 59–63 detector FPS per lane while
batch 32 produced about 54–57.

All four L40S devices produced the same detector digest
`1d3ee83114456744e7408b647cb6b71d91855028f2bf610967a98b113207afb3`
and 89,292 detections. This differs by three proposals from the prior x86 H200
runtime, so hardware/runtime drift remains a visual-audit gate before bulk use.

## New replay-disjoint data

Two additional native 1182x2560 public matches were acquired without cookies,
an account, or hidden endpoints. Channel-owner permission was previously
attested by the user.

| Video | Date | Duration | Bytes | Source SHA-256 |
|---|---|---:|---:|---|
| `i4WTQPAh0_E` | 2026-05-15 | 213.063 s | 138,690,318 | `28aeee8d06a6af87bed4313aaaebf9df7d86a14ca4b7600af57e0d4925b5003c` |
| `BL0s-x4E_ZQ` | 2026-02-24 | 320.888 s | 235,615,929 | `b32a3b8dc0b53f54c75a99aee973f1960226af43220ed0305577ad998a443b11` |

Both clocked, compact-mask packages passed every strict causal contract gate:

- contract reports: `f86e841e...b951708` and `8d148ee2...a5a151f`;
- exact public-mask recomputation: 5,342/5,342 rows, zero mismatch;
- offline-target counterfactual mask changes: zero;
- portable-clock coverage: 1,855/2,131 and 2,670/3,209 frames;
- simultaneous two-actor-ready snapshots: 72 and 16.

## Visual action audit

The original automatic complete-action outputs were not accepted from metrics
alone. Every one of the 14 candidates was inspected at native resolution with
-300 ms, exact-frame, and +300 ms hand/elixir/arena context.

Observed automatic precision on this candidate-conditioned set:

- play event: 13/14 = **92.86%**;
- card identity as emitted: 13/14 = **92.86%** overall, or **13/13** among
  visually confirmed real plays;
- deployment tile: 12/14 = **85.71%**.

The false play came from the overtime `x3` UI being mistaken for a deployment
marker. A later real Log play inherited the same false UI tile, so its card
identity was correct while its placement was rejected.

The audit itself needed a second correction pass. Enlarged native-HUD frames
proved that Dark Prince, Battle Ram, and the late Log were visible before their
plays; the original extractor was right and the first manual review was wrong.
A separate
cluster/cycle audit corrected three other initial human-review errors: the early
Tombstone has 0.978 cosine similarity to the later confirmed Tombstone, and
both apparent Fire Spirit plays are exact Skeletons-slot-to-Next transitions.
This is why the gold artifacts, not the first review notes, are authoritative.

The resulting candidate-bound manual gold contains 13 play/card labels and 12
placement labels:

- `i4WTQPAh0_E`: SHA-256
  `48b8ad94224ac23d69182503ea0a72aaadb25d28f08eaee5c55aa37d4c5107f8`;
- `BL0s-x4E_ZQ`: SHA-256
  `4b8ca6ee4a8b1e6905c49f6e778057a835ab603b0d4d29e19dadeb74413dde52`.

These labels are valid as a tiny calibration/holdout set, not as meaningful
training volume and not as a full-match recall claim.

The pre-existing HUD identity backend was then evaluated on strictly pre-play
crops from both new replay-disjoint matches. Across 39 crops and nine card
classes, its top candidate was correct **39/39**. The unchanged single-frame
confidence gate accepted 34/39 crops with **34/34** precision and produced a
valid event label for 12/13 events. For offline extraction, all three pre-play
frames unanimously selected the correct identity for **13/13** events, so the
offline path can recover the remaining event without weakening the live
single-frame threshold. Evaluation SHA-256 values:

- `i4WTQPAh0_E`: `b4c5457b409ae220e341e878036c06937c5f516f2953fe8b48a5e93a379d898c`;
- `BL0s-x4E_ZQ`: `4a5d6406d3b9682f3dd086cf81db935c53d3bace63572d346a82f6d2ea291fd6`.

That 13-event result was still candidate-conditioned, so a second deterministic
sample selected 24 different events across both players and four time bins. The
unconstrained three-frame consensus was visually correct on only **20/24**
root-card families. Every error named a card outside that player's visible
eight-card deck. A source-video-bound reviewed deck-closure gate rejected all
four errors and retained **20/20** correct root families. It now yields 113
identity labels, 93 with an independent placement, across the two matches.
This is a precision result, not training promotion: exact evolution/hero state
and replay-disjoint deck inference remain open. Machine-readable audit:
`replay_disjoint/cycle_identity_stratified_audit_20260824.json`.

## Bottleneck optimization

Single-frame ImageNet MobileNet embeddings were rejected as the event detector:
they merged multiple card artworks and background frames. A fixed spatial LAB
representation over the card's interior art produced useful review galleries,
but a full-sequence scan proved that a cluster ID is not a safe global card ID:
selected, grayscale, hand, and Next states can split one card and occasionally
contaminate another cluster. The reviewed cluster join gets 13/13 gold events
right only in its narrow event-state scope; it must not label every occurrence
of those clusters.

Reusable active-learning artifacts:

- `i4WTQPAh0_E` 16-cluster gallery manifest SHA-256
  `8b26876484faef3b23766f4463fe87a25c8289e7122465af0af6734bb99dde1e`;
- `BL0s-x4E_ZQ` 16-cluster gallery manifest SHA-256
  `67448e595472ace0cb04185d9f64744584240b7c9f2d7529e02cfae06ee79883`.

The accepted event-timing prototype instead compares artwork directly across
time: the pre-play public Next card must enter exactly one public hand slot and
that slot's previous artwork must disappear. A separate public elixir drop of
at least 0.5 is mandatory. Deployment markers can attach a location afterward,
but cannot create a play. On the tiny reviewed gate this found all **13/13**
real plays within 0.7 seconds. Full-match output remains diagnostic: 50
elixir-confirmed transitions for `i4WTQPAh0_E` and 97 for `BL0s-x4E_ZQ` have
not all been visually labeled, so precision is not yet claimed. Exact outputs:

- `i4WTQPAh0_E` cycle artifact SHA-256
  `be92309a62c4081cce0d9edbf4b5150280d5623e242be0e8ed6c660b009a4d1a`;
- `BL0s-x4E_ZQ` cycle artifact SHA-256
  `028490dc9803a8235e21539e51df7fbc61617d9e870a1693893c2b7edf3ff11b`.

## Next gate

Do not launch a 1,000-game wave yet. First:

1. add exact evolution-ready/hero-state labeling on top of the now-clean
   root-family gate;
2. validate reviewed deck inference and the 20/20 precision result on 10–25
   additional replay-disjoint matches;
3. require at least 95% automatic identity precision, at least 95% placement
   precision, and zero target-conditioned mask leakage;
4. then resume the accepted 12-process L40S shape or use the school server's
   128 physical CPU cores if its approved VPN/jump-host path becomes available.

The Cal Poly `f35` machine could not be reached from the Mac because TCP/22
timed out before authentication. No tunnel, sudo action, driver change, or
school-machine job was attempted.
