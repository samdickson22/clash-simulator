# One full high-resolution YouTube match: extraction proof

Date: 2026-08-17  
Video: `hTG8dM4KtM4`  
Permission: `user_attested_channel_owner_approval` (2026-08-17)

## Outcome

The complete bounded pipeline ran successfully on one 320.353-second public
match, from original high-resolution acquisition through a neutral sequential
record and two private-safe actor trajectories. This proves the pipeline is
executable. It does **not** yet certify label accuracy or justify a 100/1,000-
game wave.

The decisive scaling result is 9.54 games/hour including download. The dual
April-2024 KataCR arena detector consumes 81.26% of semantic wall time and is the
dominant bottleneck. The requested >100 games/hour target cannot be reached on
this Mac by downloader or decoder tuning alone.

## Immutable source

- Public upload date: 2026-08-09, eight calendar days before acquisition.
- Exact client build: unknown; upload recency is not promoted to client-version
  proof.
- Source: 1182x2560, VP9 video-only, 320.353 seconds.
- Media: 184,451,016 bytes, SHA-256
  `89817c51cb83689e210b19b41444be6928483c915c5582b5ad144f05f00b4d5b`.
- Acquisition manifest:
  `datasets/external/tv_royale_youtube_fullmatch_20260817/hTG8dM4KtM4/manifest.json`,
  SHA-256
  `045b3da2bc2640126019675131ddfd2c13c797247102453ea8d00ad363925622`.
- Exact 10 Hz framehash index: 3,204 contiguous output PTS in time base
  `1/10`, SHA-256
  `ebbb0be0b39a234dc4294a0e5df0b0ca7d060e3b0230802289bd0b493e5b2d4d`.

No 13.544 GiB decoded frame dump was retained. Semantic inference consumed the
same FFmpeg `fps=10` output-PTS contract through a bounded pipe.

## Semantic artifacts

Semantic manifest:
`datasets/derived/tv_royale_youtube_fullmatch_semantic_hTG8dM4KtM4_20260817/manifest_masks_v3.json`,
SHA-256
`70b2c7e7a2144b1fcb77a76db2ad6d5f7c4aae856d1a9bb72400235ba9ef3644`.

The v3 manifest preserves the filtered v2 manifest as its hashed parent. V2
replaced only offline event labels after manual QA found duplicates and one-off
HUD identity errors. V3 replaced only actor masks/actor artifacts using the
shared `PublicActionMaskBuilder`; no video, detector, HUD, or OCR inference was
rerun.

| Artifact | Rows | SHA-256 |
|---|---:|---|
| Neutral 10 Hz sequence, filtered-event v2 | 3,204 | `6fc0a2e1a4040e29e5c233748425d2f88d90719d04091eaa292c1a777611d104` |
| Actor 0 input-only trajectory with public-mask contract v2 at 5 Hz | 1,602 | `db28af317e67cd03c44450f3463e92e71cbddbf0ffbd420b0ee0e974ee526ace` |
| Actor 1 input-only trajectory with public-mask contract v2 at 5 Hz | 1,602 | `62186f6841edeb9da97ee5b921b3fc372cb9d8ff1d3029053500a13bd6d192eb` |
| Offline actor-target sidecar v3 | 7 labels | `7025de467374d63f3f7d654b9b131608c0bbdf002858ab989814c6c62cef07e7` |
| Offline play/deployment labels, filtered-event v2 | 164 candidates | `b751e0a1d371c5a9950e33cf0f913bf24a9d90d1fa364d11be064fe34f094791` |

The semantic directory is approximately 15 MiB.

## What was actually extracted

- Public clock: 3,114/3,204 frames (97.19%). Native macOS Vision OCR runs on
  public clock crops at 2 Hz, with confidence-reduced propagation only within
  the same half-second. Missing anchors remain invalid.
- Both HUDs: ImageNet MobileNetV3-Small embeddings compare current-frame card
  crops against 2025 card-art templates; identities resolve into the typed
  current-client vocabulary. Public elixir comes from the continuous magenta
  fill bar.
- Complete current-frame HUD: player 0 on 491 frames (15.32%); player 1 on 450
  (14.04%). At the 5 Hz actor cadence this is 243 and 226 rows respectively.
- Longest complete+clock actor intervals: 10.0 seconds for player 0 and 4.2
  seconds for player 1.
- Independent strict actor-ready snapshots: 89 (2.78% of neutral frames).
- Arena detector: 89,009 raw detections; 25,801 received an unambiguous typed
  stable identity. The raw denominator includes bars, level badges, clocks,
  elixir bubbles, and emotes, so 28.99% is not entity recall.
- HP: 17,313 visible body/bar associations. These are noisy normalized public
  bar fills, not exact simulator HP.
- Independent verifier inventory: 18,761 typed tower observations, 618 typed
  effects, and 6 typed projectiles.
- Play/deployment candidates: 164 fail-closed public deployment-marker groups
  with positions after an unconditional same-player 1.5-second refractory.
  Seven also have one card identity from a unique before/after complete-hand
  disappearance, at least 100 stable same-player deck observations, and a
  closest public elixir drop matching the official public cost within 1.0.
  They therefore have complete card+tile play labels; 3 belong to player 0 and
  4 to player 1.
- Statuses and projectile targets: zero valid labels. These heads deliberately
  fail closed.

The 7 complete play labels are extraction candidates, not measured precision
or recall. A marker count is not automatically a ground-truth play count.

## Neutral and actor contracts

The neutral sequence stores absolute simulator-style world coordinates once.
Each row carries exact output PTS/time-base metadata, public clock/entities,
both private HUDs in an explicitly offline-only section, per-field confidence
and missingness, and offline temporal label evidence.

Each actor trajectory input contains only:

- the public neutral state;
- that actor's own hand/Next/elixir observations;
- per-head validity;
- a label-independent public mask built by the project's shared
  `PublicActionMaskBuilder` from current public entities, accepted own-HUD card
  identities/confidences, visible elixir, canonical deployment zones,
  nonblocked terrain, and supported visible blockers.

It contains no opponent HUD, raw frame, simulator state, exact simulator action
mask, or demonstrated-action-forcing input. Both actors share the same match
and split-group ID. All 243 complete-HUD player-0 actor rows and all 226
complete-HUD player-1 rows have a nontrivial mask. Across all actor rows, 1,215
player-0 rows and 1,283 player-1 rows have at least one non-noop action. The
masks expose 1,152,425 and 854,944 non-noop legal actions in aggregate,
respectively.

All seven filtered action labels align to a preceding 5 Hz actor row containing
the played card. Six are legal under the independently built public mask. One
Baby Dragon label at canonical tile `[16, 7]` is rejected by the visible public
mask and remains unforced; it must not enter masked action training without
further visual adjudication.

Targets live only in the hashed offline sidecar keyed by match, split group,
snapshot, and actor. Neither actor artifact contains `expert_action`,
`offline_label`, `offline_evidence`, opponent HUD fields, or private neutral
records.

Temporal hand disappearance and marker deduplication appear only in offline
label evidence. They are not actor inputs.

## Stage-by-stage throughput

All semantic heads ran locally on the M4 Pro using MPS where applicable.

| Stage | Wall seconds | Isolated games/hour | Share of semantic wall |
|---|---:|---:|---:|
| Download | 7.520 | 478.72 | outside semantic pass |
| Standalone exact 10 Hz decode reference | 27.170 | 132.50 | measured independently |
| Detector model load | 0.648 | - | 0.18% |
| HUD model load | 0.536 | - | 0.14% |
| Arena detector | 300.525 | 11.98 | 81.26% |
| Batched HUD card/elixir heads | 31.916 | 112.80 | 8.63% |
| Native clock OCR, including Swift compile | 8.818 | 408.25 | 2.38% |
| Serialization, HP/event association, other | 25.478 | 141.30 | 6.89% |
| Piped frame delivery charged in semantic run | 1.896 | - | 0.51% |
| Semantic total | 369.817 | 9.73 | 100% |
| Download + semantic total | 377.337 | **9.54** | - |

Peak resources:

- process RSS: 2,764,390,400 bytes;
- peak observed MPS allocation: 715,878,400 bytes;
- semantic process CPU time: 100.296 seconds.

The piped-read number is not an independent decode benchmark because FFmpeg is
backpressured by semantic inference. The 27.17-second standalone decode is the
valid decoder capacity measurement.

## Scaling implication

At the measured 9.54 games/hour:

- 100 games: about 10.48 hours;
- 1,000 games: about 104.82 hours;
- retained media: about 18.45 GB for 100 games or 184.45 GB for 1,000 games at
  this video's size;
- semantic outputs: roughly 1.5 GB for 100 or 15 GB for 1,000 at this match's
  output size.

Sequential acquisition can keep transient decoded storage bounded. Network is
not the bottleneck: this source downloaded in 7.52 seconds, while arena
inference used 300.53 seconds. A high-throughput GPU service should batch arena
frames across multiple matches and benchmark a distilled/current detector;
simply adding download workers would mostly create a queue.

## Validation

Independent semantic-contract verification passed:

- report:
  `reports/tv_royale_youtube_fullmatch_semantic_contract_masks_v3_contract2_hTG8dM4KtM4_20260817.json`;
- SHA-256
  `0726c1eeb8ec8b604a84bd1104559dd36a5f19123da4864a50278c6dc836281a`;
- verified 3,204 neutral rows, 1,602 rows per actor, aligned hashes/time bases,
  89 strict actor-ready snapshots, privacy separation, 164 filtered marker
  groups, 7 complete card+tile labels, 243/243 eligible nontrivial player-0
  masks, and 226/226 eligible nontrivial player-1 masks;
- every strict verifier gate passed, including target-field absence from actor
  inputs, exact recomputation of all 3,204 masks with zero mismatches, and zero
  mask changes after injecting fake expert/future labels into all 3,204 source
  records;
- 11 local extractor, vocabulary, and mask tests passed; Ruff, focused mypy,
  and Swift compilation were clean.

## Visual QA

The six-frame early/mid/late/ambiguous audit manifest is
`reports/tv_royale_youtube_fullmatch_visual_audit_hTG8dM4KtM4_20260817/manifest.json`,
SHA-256
`e6f61adde7fbe6469b449d5e14fd2cd68890d3eebabca7af72434bae3dfca86b`.
Its contact sheet SHA-256 is
`a6ad1d0f8bd9b08a6c49b23480669d28a90b8707848a2e51a1a1e00fdf6e30aa`.
It shows the exact 18x32 logical grid, sprite boxes explicitly labeled as not
hitboxes, typed identity/HP labels, both HUDs, public clock, and any action tile.

Manual findings:

- The grid follows the arena's playable board rather than tower artwork, and
  the tower boxes correctly remain sprite boxes rather than 4x3/4x4 hitboxes.
- At PTS 330 the OCR value `147s` exactly agrees with the visible `2:27`.
- The selected top card is marked ambiguous/invalid instead of being silently
  accepted.
- The detector misses several clearly visible troops in reviewed frames. This
  is consistent with its stale April-2024 vocabulary and prevents a recall
  claim from raw coverage counts.
- A systematic HUD defect remains: the bottom cost-2 Barbarian Barrel/Knight-
  family image is repeatedly labeled `Barbarians` (official cost 5). The event
  cost-consistency filter prevents that family from becoming a play label, but
  the false identity still appears in some actor HUD inputs and masks. Thus a
  structurally complete HUD row is not automatically semantically correct.
- The filtered-event contact sheet
  `reports/tv_royale_youtube_fullmatch_eventfiltered_v2_qa_hTG8dM4KtM4_20260817.jpg`
  has SHA-256
  `330a7048a075cc278501104e24f4b3bb14d78509f8da83bfa4689ae2191da35b`;
  all seven retained card+tile labels are visually plausible. The rejected
  Baby Dragon mask mismatch remains excluded from masked action training.

This is why the result is an end-to-end execution proof, not a label-accuracy
certification.

## Decision before scaling

Do not launch 100 or 1,000 games yet. The one-match execution proof passed, but
three quality gates remain:

1. add a data-driven visible-cost head/gate so the repeated
   `Barbarians`/cost-2 mismatch and similar card-family confusions fail closed;
2. measure hand/Next/elixir, clock, team, HP, play-event, and tile accuracy
   against manually labeled frames rather than using coverage alone;
3. manually resolve or exclude the one Baby Dragon label rejected by the
   independent public mask; never force it legal from its target.

After those pass, optimize or replace the arena detector. It is the only stage
whose isolated rate is an order of magnitude below the 100-games/hour target.

## Cost-conditioned HUD and cached action recall follow-up

A HUD-only rerun (no arena detector) now keeps complete card-family score
tables in an offline-only artifact and reranks the actor-visible decision using
the printed cost from the same frame. It also exposes the already-observed
fractional elixir fill and current-frame affordability with explicit
missingness for uncalibrated grayscale and evolution heads.

- HUD manifest:
  `datasets/derived/tv_royale_youtube_fullmatch_cost_conditioned_hTG8dM4KtM4_20260817/manifest.json`,
  SHA-256 `02b0824bdd6f3b0d284d44582680680477349b5c4e20cb0ebc1d72731d5ee8e3`;
- mask manifest SHA-256
  `75301c1e527614d579c9dc77b63a7c32027f198e0109d4c9e549ccde1f3405f7`;
- strict verifier SHA-256
  `d58b7bbd644d415e828ce7c7e4f58b65c70a55a09bbc54d7e2b5d9a2ac66d59b`;
- current-frame printed-cost observations: 8,470 player-0 and 6,281 player-1
  hand/Next heads;
- strict neutral snapshots complete for both players: 22;
- eligible/nontrivial actor rows: player 0, 60/56; player 1, 409/409;
- all 3,204 masks recomputed exactly and remained unchanged under injected
  future/target labels.

The glowing cost-2 standard-Barbarian portrait is not relabeled to the nearest
cost-2 template. Current-client authority makes `BarbLog_hero` a strong typed
hypothesis, but distinct hero art has not been proven. Its rows therefore fail
closed with `current_client_hero_or_variant_art_not_in_template_authority`.
Cost consistency is not identity correctness, especially for same-cost cards.
The 30/12 temporal cost calibration split is a same-replay diagnostic only;
replay-disjoint calibration is still required before promotion.

Exact FFmpeg 10 Hz sequence review corrects the prior slot-kind and identity
status. The glowing cost-2 single-Barbarian portrait is in player 0's Next at
30.8 seconds, in ordinary hand slot 1 at 31.4 through 37.1 seconds, gone at
37.2 seconds as displayed elixir drops from 4 to 2, and followed by a friendly
rolling Barbarian Barrel at 37.4-37.5 seconds. It is therefore a normal
hand-card variant, not an ability-control slot. Of the official cost-2 hero
candidates, only `card_action:BarbLog_hero` uses `BarbLogProjectile` and matches
the observed deployment. The identity is accepted for this reviewed test
sequence only. It remains ineligible for automatic labeling of other frames or
replays; 13 of 14 current hero variants still lack exact templates.

Cached causal action reconstruction now uses public elixir drops, smoothed hand
transitions, public cost, stable cycle support, deployment markers, and both
visible Next labels. Next rotation raises accepted identity labels from 53 to
56 and complete card+tile labels from 44 to 46. The Next evidence stays in the
offline target sidecar and never enters the other actor's trajectory.

All 107 action candidates were reviewed across nine contact sheets. The
candidate-conditioned one-replay gold diagnostic is
`reports/tv_royale_youtube_action_visual_gold_hTG8dM4KtM4_20260817.json`,
SHA-256 `e44fad5a73a6c8687f387c8440fdeec44b447a188141de4720e0c5426048c5a6`.
It records 107 visually supported play onsets, 55 supported identities, and 89
supported deployment markers. Against it, the cached labeler is 107/107 for
play onset, 54/56 for identity (96.43% precision and 98.18% recall), and 89/89
for the reviewed marker tiles. One formerly missing gold identity is the exact
reviewed `BarbLog_hero` play at 37.2 seconds; the cached labeler correctly leaves
it missing rather than guessing. The two false identity predictions remain
unsupported hero-art cases. These
figures are not held-out generalization or an independently sampled recall
estimate; the replay-disjoint gate remains open.

## Current-frame HUD semantic heads

The bounded high-resolution HUD-only pass adds separate current-frame heads for
variant visual state, evolution readiness, visible progress diamonds, printed
cost, grayscale disabled state, and own Next for both orientations. Exact card
identity remains separate: an evolution-ready frame does not silently become an
evolution identity, and an unproven gold portrait does not root-collapse to its
base card.

- HUD semantics manifest:
  `datasets/derived/tv_royale_youtube_fullmatch_hud_semantics_hTG8dM4KtM4_20260817/manifest.json`,
  SHA-256 `f8a0a0c0ee5d90f5040716eac5ff683ae78e9701991380ee7bb7c6ebec2cd42f`;
- 120-cell exact-PTS atlas SHA-256
  `b574e2a5fe6b69f3c16741195f434c9db3352b4180d5e54dc544404d18c7f171`;
- HUD gold verifier SHA-256
  `3e597372a51e8f97779935d81e8c3cc7c0f28f7b6e948a70e43b3ebb0c5b1528`;
- strict mask/actor verifier SHA-256
  `0ed91f2eb30c5e1f3b812ce3d2d8c330885cc198634e269c68f2081fabdbed83`.

On 19 manually reviewed exact 10 Hz crops, every emitted label was correct:
disabled 15/15, evolution-ready 4/4, progress diamonds 1/1, variant candidate
5/5, and selected/disappearing 3/3. Printed-cost precision was 9/9 with only
60% coverage (six grayscale/ambiguous crops failed closed). Variant-value
precision was 6/6 at 85.7% coverage. These are one-replay diagnostics, not
replay-disjoint calibration claims.

Selected/disappearing signals and four exact reviewed `BarbLog_hero` anchors
(Next 30.8s, hand 31.4s, pre-play 37.1s, played 37.2s) live only in offline
sidecars. Both 1,602-row actor artifacts contain their own current-frame Next
semantics and zero opponent HUD, full candidate-score, future-confirmed,
selected/transient, or expert-target fields. Training promotion remains blocked:
only 1 of 14 hero variants has a test-only exact reference, the other 13 remain
fail closed, evolution identities are not proven from frames alone, and all
thresholds still require replay-disjoint validation.
