# TV Royale YouTube bulk-readiness gate

Date: 2026-08-17  
Decision: **one-video H200 smoke allowed; multi-video training extraction blocked**

## Proven and ready

- Permissioned high-resolution acquisition, exact 10 Hz PTS indexing, bounded
  one-video scratch, atomic publication, and resumable deterministic sharding.
- Linux/x86-64 H100/H200 package with public-mask contract v2, pinned source,
  weights, dependencies, vocabulary, verifier, and one-video smoke gate.
- Portable current-frame clock provider
  `tools/recognize_public_clock.py`, SHA-256
  `fd4975980ee960e98d490b5bab8d84ee3999c8c7278cc8421051b9ec15fba5a7`:
  535/535 accepted anchors exact on the retained replay, 120/120 exact in
  untouched temporal blocks, and 2,675/3,204 valid merged 10 Hz frames.  This
  proves the pinned 1182x2560 one-video smoke only; replay-disjoint evidence is
  recorded separately below.
- Label-independent public masks use contract v2.  All 3,204 retained-replay
  masks recompute exactly and remain unchanged after injected future/target
  evidence.
- The two active simulator-derived causal sidecars have been recomputed and
  migrated to v2.  Contract-v1 sidecars fail closed.
- Cached action reconstruction uses current public elixir drops, smoothed hand
  transitions, printed cost, cycle support, deployment markers, and each
  player's visible Next rotation.  None of this offline evidence enters the
  other actor's input.
- The retained replay now has separate current-frame HUD heads for printed cost,
  grayscale/disabled state, hero/evolution visual state, evolution readiness
  and progress diamonds, and both players' own Next.  Nineteen manually gold
  records produced zero wrong emissions; uncertain crops abstain.  Selected
  slots, disappearances, full family scores, and exact reviewed identity anchors
  remain offline-only, and both 1,602-row actor trajectories contain zero
  opponent-HUD/future/expert fields.

CUDA pins:
`datasets/source_metadata/tv_royale_youtube_cuda_pins_v2.json`, SHA-256
`76a6e326d63ea119dbd4c9e6d6cc1309d33dd1893c53be1a39de33e7ffcc740c`.

## Why bulk remains blocked

### 1. Current-client HUD variant recognition is not yet approved or calibrated

The client contains 14 typed hero hand-card variants and 41 evolution variants.
All are mechanics-bearing visible state and must not be collapsed to their root
family.  Exact technical art authority is now available for all 14 Hero HUD
portraits and all 41 Evolution portraits from the official client-15.546.41 CDN
fingerprint: all 69 source objects matched fingerprint SHA-1, all Hero textures
decoded to distinct 394x500 RGBA portraits, and every Evolution portrait opened
successfully.  This corrects the earlier conclusion that 13 Hero portraits were
technically missing.

The assets remain review-only.  Supercell owns the art, and its Fan Content
Policy restricts content connected to bots/automation; the audit therefore did
not persist individual decoded Hero textures, auto-label crops, or mark the
assets detector-training eligible.  Separate legal/operational approval is
required before using exact art as training data.  Even with such approval,
replay-disjoint recognition precision/coverage remains unmeasured.

The retained replay contains 19 repeated examples of a glowing cost-2
single-Barbarian portrait.  Exact ffmpeg 10 Hz decoding now proves the reviewed
sequence: the portrait is in the bottom player's visible Next slot at 30.8
seconds, rotates into an ordinary hand slot at 31.4 seconds, remains present
with four public elixir at 37.1 seconds, disappears as elixir falls to two at
37.2 seconds, and is followed by a friendly Barbarian Barrel rolling up the
left lane at 37.4--37.5 seconds.  Of the official cost-2 hero variants, only
`card_action:BarbLog_hero` token 100 has the matching rolling
`BarbLogProjectile`; `Goblins_hero` and `IceGolemite_hero` directly summon
different units.  That exact identity is therefore accepted for this reviewed
sequence.

This is not a general hero classifier.  The reviewed sequence cannot auto-label
other crops or create a new arena detector class.  Root-family or cost-only
relabeling remains forbidden.

Evidence:
`reports/current_client_hero_variant_hud_manifest_v1.json`, SHA-256
`89e05015df007da57045388b287add246c0a0d878631cc5fc77bcf087cf7e3b5`,
and `reports/barblog_hero_deployment_evidence_v1.json`, SHA-256
`4b1cf6977fc19ff69e9ddf7f92346372ed7229501b20a9286a53722bf98e03aa`.
Official-art authority:
`reports/current_client_variant_art_authority_15_546_41.json`, SHA-256
`1404525497a6cbdb7cadf9699b03b33f01940a7d71e7374d8ec3a4b5e93e5a90`.

### 2. Arena coverage is stale

The current typed vocabulary contains 315 arena detector targets.  The April
2024 detector has only 84 exact/explicit visual matches; 143 are root-family
review candidates that cannot be auto-labeled, and 88 are wholly missing (41
troops, five buildings, 22 projectiles, and 20 effects).

The first current-video proposal review exported only four accepted test-only
boxes: two Recruit and two Goblin Brawler examples.  Rejected family guesses
remain unlabelled.

Evidence:
`reports/current_client_detector_upgrade_manifest_v1.json`, SHA-256
`fa5a8faf38a5dd74c6e20dd7a1e8111f455e08ea7e16bd0baf38f9949b93f6a4`.

### 3. Accuracy is still one-replay diagnostic evidence

The cost-conditioned HUD pipeline structurally passes with 22 simultaneous
two-player-ready snapshots and zero mask leakage.  Its current replay gold
contains 107 visually supported play onsets, 55 supported identities, and 89
supported deployment markers.  The cached labeler is 107/107 onsets, 54/56
identity predictions (96.43% precision, 98.18% recall), and 89/89 reviewed
marker tiles.

These figures are candidate-conditioned and same-replay.  They do not measure
recall over an independently sampled timeline and do not prove generalization
to other layouts, themes, compression settings, decks, heroes, or evolutions.

### 4. Portable clock precision passed; layout expansion has not

The provider now rejects normalized template margins below the minimum support
observed on the original exact 1182x2560 calibration source. The threshold was
selected without replay-disjoint labels. Exact-source output remains
byte-identical at 535 anchors. On 120 hash-verified frames from ten different
videos, a confident macOS Vision teacher supplied 108 labels and the repaired
provider accepted 57, all 57 exact (100% observed accepted accuracy, 52.778%
teacher-conditioned coverage). The prior `0:09` to `0:00` false acceptance is
now rejected.

This is a precision repair, not a native-layout expansion. The retained canary
pixels are low-resolution format-18 sections. Native 886x1920 and 888x1920
sources remain fail-closed until direct native-resolution held-out evidence is
available. A single bounded 886x1920 acquisition retry for `iW_07-RIjJk` on
2026-08-18 again returned `VideoUnavailableException`; the downloader exited
and left zero partial files. No retry storm or alternate identity path was used.
Bulk mode therefore remains disabled.

Evidence:
`reports/tv_royale_portable_clock_precision_repair_20260817.md` and
`reports/tv_royale_portable_clock_precision_repair_20260817.json`, SHA-256
`7ac656cd9b09fd2d16740d248f1e4ba644d8edda0dfa408778fd22475b149916`.

## H200 execution ladder

### Stage 0: exact retained-replay smoke

Allowed immediately when a compatible H200 is available.  It must:

1. pass pinned runtime/device/source/weight/vocabulary/clock preflight;
2. reproduce stable detector digests across all benchmark repetitions;
3. publish the full neutral sequence, two input-only actor trajectories,
   offline-only target sidecar, v2 masks, and zero-failure verifier report;
4. report detector and end-to-end throughput without promoting any label; and
5. copy all completed hashes/telemetry off the ephemeral worker before teardown.

### Stage 1: replay-disjoint ten-video canary

Allowed only after Stage 0.  Outputs remain quarantined and cannot train a
policy.  The ten videos must remain whole split groups.  This stage builds
authoritative/current review sets and measures the following predeclared gates:

| Gate | Required result |
|---|---:|
| Portable clock | >=80% anchor coverage, >=99.5% accepted accuracy, zero illegal monotonic transitions |
| Hand/Next identity | >=99% precision and >=70% per-slot coverage on replay-disjoint manual gold |
| Printed cost | >=99.5% precision where accepted; mismatch always fails closed |
| Own elixir | mean absolute error <=0.25 elixir on manually read frames |
| Hero/evolution state | every retained training row has authoritative typed art/state; rows with unknown variants are excluded and never root-collapsed |
| Play onset | >=99% precision and >=80% recall on independently sampled complete timelines |
| Card given play | >=98% precision and >=75% recall |
| Deployment tile | >=95% within one tile and no orientation error |
| Team/side | >=99% accuracy |
| Entity center | median <=0.5 tile, p95 <=1.0 tile |
| Arena class | >=95% precision and >=85% recall for every sufficiently represented enabled/current class |
| Privacy/causality | zero target/future/opponent-private actor fields; counterfactual masks unchanged |
| End-to-end rate | >=100 completed average game-equivalents/hour after pipeline overlap |

Any denominator below 30 examples is reported as insufficient, not passed.
Hero/evolution and rare-card gates cannot pass vacuously.  Insufficient variants
remain excluded from training, but they do not permanently block a separately
reported common-card subset once every other common-subset gate passes and the
split manifest proves no excluded row leaked back in.

### Stage 2: detector/HUD update

Train only on accepted current-client annotations plus old-class rehearsal.
Entire source videos/tracks remain in one split.  The retained `hTG8dM4KtM4`
replay is test-only.  Promotion requires the Stage-1 gates and no material
old-class retention regression.

### Stage 3: 100-game pilot

Only a Stage-2 winner may produce a 100-game corpus.  Re-audit random,
high-uncertainty, crowded, hero/evolution, early, overtime, and final frames.
No policy training occurs if any leakage, orientation, hero-art, or label
precision gate regresses.

### Stage 4: 1,000 games

Allowed only after the 100-game pilot passes and its train/validation/test
split manifests prove replay, deck, archetype, chronology, and source-video
isolation.  Scale adds workers only while GPU utilization exceeds 80% and a
prepared-frame queue grows; otherwise fix CPU/HUD/acquisition supply first.

## Current decision

Use the H200 first for measurement and annotation mining, not bulk extraction or
long policy training.  Fast output from the present April-2024 detector would
amplify known hero/current-card errors.  The bulk gate remains code- and
evidence-blocked until the replay-disjoint canary passes.  In particular, the
current frozen clock is valid for the exact retained-replay smoke but has now
failed the broader replay-disjoint expansion gate; bulk mode must remain
disabled.
