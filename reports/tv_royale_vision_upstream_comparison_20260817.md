# TV Royale semantic vision comparison — 2026-08-17

## Decision

Clasher should **not replace its extractor with either upstream project**.
Its current pipeline is already a deliberate hybrid:

- the fixed HUD geometry, card templates, grayscale-card treatment, and
  hand-transition heuristic come from the CS541 project;
- the two arena detectors and their visual vocabulary come from KataCR;
- Clasher adds confidence/missingness arrays, fail-closed enabled-card mapping,
  causal tracking, visible HP measurement, strict placement gates, replay- and
  archetype-disjoint splits, artifact hashes, and visual audits.

The best H100 pipeline keeps that composition but changes the execution model:
use small batched HUD classifiers, a persistent cross-game GPU detector service,
and a strict current-frame output contract. KataCR's richer offline association
logic can supervise labels, but neither KataCR's nor Clasher's external trackers
may become deployed policy inputs under the model-owned-state requirement.

This audit inspected local source at:

- CS541: `08aafd87cb3707b779804918cc65f4ae430d37ab`
  (2025-12-11);
- KataCR: `36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8`
  (2024-06-06);
- Clasher: the dirty `codex-enabled-deck-parity-handoff` worktree. No existing
  source was modified and no sustained benchmark ran.

## Comparison

| Capability | CS541 upstream | KataCR upstream | Clasher current |
| --- | --- | --- | --- |
| Input | Fixed 540x960 portrait UI; arena crop 428x683 | Splits arbitrary screenshot into clock, arena, HUD; detector configured at 896 | 540x960 replay rows, exact 428x683 crop, detector inference at 896x576 |
| Temporal rate | Capture requests 30 FPS, recorder polls at <=20 Hz and keeps changed frames only; rows have no timestamps | Vision at 10 FPS, offline state/action output at 5 FPS | Source is nominally 10 FPS; sparse cascade selects a median 129 detector frames/game |
| Arena detector | None | Two custom YOLOv8l-style detectors with 155 combined visual classes and team output; ByteTrack available | Reuses the same two pinned KataCR v0.7.13 weights, 43.70M parameters each; merges output with cross-model NMS |
| Hand/cards | CPU OpenCV template match against the replay-discovered deck | Five-slot JAX/Flax card classifier, but shipped model description is tied to Hog 2.6 and local classifier weights are absent | Cleaned CS541 template path, 161 templates, raw per-slot match confidence, ambiguous/moving slots fail closed; current visible Next icon baseline added. The published sidecar still promotes resolved hand IDs to confidence 1.0 |
| Own elixir | Eleven digit templates plus color-fill fraction | PaddleOCR for HUD elixir; deployed elixir-cost bubbles get a separate classifier | CS541 digit/fraction method retains its raw match score in `UIFrameState`, but the current sidecar does not propagate it and assigns observed elixir confidence 1.0 |
| Public clock | No active clock extractor | PaddleOCR of the clock crop, returns elapsed seconds | Strict OCR parse contract exists, but actual image-to-text clock detector is still missing; published replay globals currently use frame index |
| Own play event | Hand vacancy/replacement plus >0.8 elixir loss, backdated after later evidence | Hand vacancy plus deployed elixir bubble, cost match, OCR name, and elixir-mutation offset | Strict hand transition plus elixir evidence; simultaneous/gray/disabled/terminal ambiguity rejected; later evidence is label-only |
| Placement | Defines 18x32 quantization but checked-in source writes x=y=-1; referenced placement parquet is absent | Strongest upstream feature: bottom-center of deployed elixir-cost bubble mapped to 18x32 grid, with OCR/cost/hand cross-check | Two-frame agreement on new deployment-clock clusters; persistent-area spell centers; legal-side and action checks; 4,610 strict labels and visual grid audits |
| Entity tracking | None | ByteTrack IDs plus persistent side/class/bar memories | Lightweight identity/team/position causal tracker with confidence decay; strict runtime contract now forbids this external memory as deployed input |
| HP | None | Keeps 24x8 grayscale bar crops for units, not a numeric unit-HP fraction; OCR tower HP is primarily reward evidence | Measures normalized visible bar fill, associates it to data-derived valid bodies, and carries per-feature confidence; 56.495% entity-HP coverage |
| Status/effects | None | Detector vocabulary contains spells/effects, but policy state declares `num_state_classes=1`; shield/freeze/rage/slow/heal/clone state is not encoded | Area-effect entities are represented, but stun/slow/haste/stealth/effect progress and attack-state classifiers are still missing |
| Projectiles | None | Several spell/object classes such as fireball, axe, dirt and bomb are detected | Recognized spell/effect identities can become entities; no reliable projectile trajectory, target, attack clock, or remaining-duration extraction |
| Confidence | Thresholded match only; hand confidence parameters are ignored in favor of hard-coded 0.55/0.60 | Raw detector confidence exists, but semantic state drops calibrated per-field uncertainty; published validation ignores team-label accuracy | Entity identity and 32 entity fields carry confidence/missingness. HUD match scores exist, but resolved hand/elixir values are still promoted to 1.0 in the published sidecar. No heuristic is statistically calibrated yet |
| Current-client coverage | Card templates are current to the December-2025 checkout and include 161 images | Detector/labels stop at April-May 2024 | HUD templates cover the enabled deck cards, but the arena detector is still April-2024 and can miss newer/reworked visuals in November-2025 footage |
| Provenance/evaluation | No tests, checked-in extraction benchmark, game-level split, or reproducible placement source | No local tests; external metrics exist, but no current-client calibration and some required model artifacts are absent | Fixed hashes, production manifests, confidence validation, replay/deck/archetype/chronology isolation, and human-inspected grid/HP contact sheets |
| H100 readiness | Poor: serial OpenCV loops over candidates, no batching/CUDA | Partial: PyTorch detector is CUDA-capable, but `VisualFusion` executes OCR, two detector calls, five card calls, and elixir OCR sequentially per frame | Partial: detector accepts batches and CUDA, but extraction is still per-game/per-process and invokes the two models sequentially; cross-game batching is absent |

## Source evidence

### CS541

The semantic surface is only fixed-region hand/elixir extraction. The exact
arena, hand and elixir boxes are in
`datasets/external/CS541-Deep-Learning-Clash-Royale-Project/cr_detection/cr_element.py:20-39`.
Elixir uses digit templates and a color-pixel fractional estimate in
`cr_detection/cr_gamestate.py:30-43,75-85`; four hand slots use serial OpenCV
template matching and readiness-overlay synthesis in
`cr_detection/cr_gamestate.py:88-115`. The matcher loops over every candidate
on CPU in `cr_detection/cr_element.py:134-157`.

Deck discovery consumes the whole replay before earlier frames are classified:
`cr_detection/cr_dataset.py:53-70,75-106`. That is acceptable as offline label
support, but it is future-derived information and cannot be a live current-frame
input. The notebook's action heuristic also confirms a play from later hand
evidence and backdates it; it is an offline labeler, not a live sensor. Most
importantly, the checked-in table builder writes missing placement coordinates
(`x=y=-1`) in `cr_detection/main.ipynb:3983-4002`, and the placement parquet
referenced by `decision_model/train.py:90-95` is not present.

CS541 ships no unit detector or semantic entity state. `CRGameState` ends after
hand extraction at `cr_detection/cr_gamestate.py:116`; its movement highlight
is visualization-only background differencing
(`cr_detection/cr_dataset.py:139-171`). Its small decision checkpoints are not
a replacement perception layer: the default data path wraps each image as a
length-one sequence (`decision_model/dataset.py:216-229`), and the live bot does
not retain ConvLSTM state between calls.

### KataCR

KataCR's `VisualFusion` is the broadest upstream semantic extractor. It splits
the frame into three regions, runs PaddleOCR for time, the dual detector on the
arena, a five-card classifier, and PaddleOCR for own elixir
(`datasets/external/KataCR/katacr/policy/visualization/visual_fusion.py:30-65`).
The two detector class partitions are explicit in
`katacr/yolov8/detector1/data.yaml` and `detector2/data.yaml`; together they cover
155 April-2024 visual classes. The pinned Clasher copies are each 84 MiB. The
original combined inference path calls both models separately, concatenates
their predictions, applies NMS, and optionally tracks with ByteTrack
(`katacr/yolov8/combo_detect.py:31-70`).

The strongest component worth borrowing is action reconstruction. It remembers
the five visible card slots, detects a newly empty slot, detects an elixir-cost
bubble at the deployment, verifies the card by OCR or public cost, and maps the
bubble's bottom-center into arena cells
(`katacr/policy/perceptron/action_builder.py:72-131,133-220`). It also records an
offset to the earlier elixir mutation. That future-confirmed offset is valid as
an offline target only.

KataCR's state association is richer than its final policy features. It retains
bar IDs, side/class votes, a three-second bar history, and a 1.5-second deploy
history (`katacr/policy/perceptron/state_builder.py:44-79,198-220,285-345`). It
associates health bars and bodies, but returns bar image crops rather than a
calibrated numeric unit-HP fraction. The checked-in policy state documents only
identity, side, center and bar crops (`state_builder.py:1-18`); the configured
state class count is one, so declared freeze/rage/shield/etc. states are not
actually supplied to the policy. No velocity, current target, attack clock, or
projectile trajectory is built.

The upstream detector metrics are useful but not sufficient for our gate. The
v0.7.12 log reports precision 0.890, recall 0.797, AP50 0.843 and mAP50-95 0.676,
while its validator reduces the target class to `cls[:,0]` and therefore does
not validate team ownership. There is no held-out current-client calibration or
per-field uncertainty output. Required OCR/card/elixir classifier checkpoints
are also absent from this clone, so the complete upstream fusion path is not
locally reproducible as shipped.

### Clasher

Clasher deliberately loads KataCR's custom PyTorch detector and preserves class,
team and confidence (`scripts/import_tv_royale_placements.py:59-100,103-140`).
It sends image batches to each model at 896x576 with confidence 0.4 and NMS 0.6
(`scripts/extract_tv_royale_raw_cascade.py:144-176`). The production benchmark
measured only about 11.4 detector FPS on M4 CPU/MPS, versus 156-244 FPS for
decode/crop, proving the detector is the local bottleneck
(`reports/tv_royale_vision_benchmark_20260812.md:52-115`).

The public-state layer adds what upstream lacks: color-based HP fractions with
confidence, one-to-one same-team body association, causal identity/team motion,
and confidence-decayed missingness. The implementation is in
`src/clasher/rl/tv_royale_public_state.py:181-450` and
`src/clasher/rl/causal_vision.py:395-705`. The finished 1,000-game corpus has
29,722 decision rows, 262,240 visible entities, 56.495% HP coverage, 38.640%
motion coverage, and 121,137 tower-HP measurements
(`reports/tv_royale_data_quality_and_expansion_20260817.md:99-117`).

Spatial supervision is stricter than either upstream checkout. A non-spell
placement requires the same canonical tile from both adjacent deployment-clock
frames; persistent-area spells require one novel stable effect center. The
accepted location split contains 4,610 labels over 663 games and has no
replay/deck/held-out-archetype overlap
(`reports/tv_royale_data_quality_and_expansion_20260817.md:65-97`). Detection
boxes are always audited as sprite/UI bounds, never hitboxes
(`reports/tv_royale_vision_benchmark_20260812.md:117-138`).

Clasher still has critical gaps. The actual public timer is not OCR'd; status,
attack, and opponent-play classifiers are missing; the April-2024 detector is
stale; raw HUD confidence is not yet propagated into the published sidecar; and
`causal-vision-v1` is an external accumulator. The strict
`CurrentFramePublicSignals` contract now rejects externally supplied opponent
history and motion, while the project report explicitly reserves causal
tracking as an offline teacher
(`reports/causal_vision_current_frame_20260817.md:9-45,65-101`).

### Concrete inherited card-template defect

A bounded static audit compared every current `decks.json` card's CS541 filename
cost against Clasher's current data loader. The only mismatch was Cannon:
`cr_detection/cards/cannon-1.png` versus current public cost 3; the library also
contains `evo_cannon-3.png`. Because the cost is used to synthesize the gray
readiness overlay, unaffordable base-Cannon frames can be matched against the
wrong mask. Do not copy template filename costs into the exported model; take
costs from the authoritative current card snapshot during training, then encode
them in weights/buffers inside the model artifact.

## Leakage and packaging judgment

Use two explicitly different products:

1. **Offline teacher output.** It may use later frames to confirm which visible
   Next icon or play occurred, and it may use an external tracker to generate
   labels. Every such field must be marked `label_only`, retain its evidence
   frame, and be added only after train/validation split assignment.
2. **Deployed current-frame output.** It may contain only evidence visible in
   the current screenshot: current clock/HUD detections, current bodies/bars,
   deployment markers, card-name visuals, and status/attack onsets with raw
   confidence. Deduplication, cycle, opponent elixir, HP continuity, and timers
   must live inside the exported model's recurrent state.

The current tree already records the biggest known hazards: a sidecar can retain
an exact simulator action mask/history, and a demonstrated expert action can be
forced legal in its own input mask. Those paths must remain excluded from the
live contract (`reports/causal_vision_current_frame_20260817.md:65-84`).

## What to borrow

### From CS541

- fixed, cheap HUD ROIs;
- grayscale/readiness-aware card recognition;
- hand vacancy plus elixir-drop cross-check;
- whole-replay deck discovery only as an offline audit aid;
- later slot refill as a label for the previously visible Next icon.

Do not borrow its serial all-template loop, row-level split, future-derived live
deck restriction, missing placement provenance, or nominal ConvLSTM memory.

### From KataCR

- the broad arena/body/bar/effect vocabulary and custom team-aware detector;
- deployment elixir-bubble bottom-center as an independent placement cue;
- OCR/card-cost cross-check for deployment identity;
- bar/body association and ByteTrack IDs as offline teacher signals;
- detector-side synthetic data generation concepts for rare/effect-heavy units.

Do not expose its Python card/bar/deploy histories to the policy, treat bar
crops as exact HP, rely on April-2024 coverage, or accept detector confidence as
calibrated.

### Clasher advantages to retain

- one versioned confidence-aware schema shared with degraded simulator data;
- fail-closed enabled-card taxonomy rather than generic unknown entities;
- strict two-frame spatial agreement and no invented projectile-spell aim point;
- replay/deck/archetype/chronology isolation;
- exact artifact hashes, raw deletion after validation, and visual grid/HP gates;
- the explicit separation between current-frame runtime evidence and offline
  hindsight labels.

## Recommended merged H100 pipeline

1. **Central ingestion service.** Download several replay parquets concurrently,
   verify LFS SHA-256, and decode PNG rows in a CPU worker pool. Raw frames are
   PNG blobs, so NVDEC will not help; use enough CPU/libpng workers to feed the
   GPU and retain bounded one-to-several-game scratch.
2. **Cheap HUD pass.** Keep fixed crops, but replace per-template Python loops
   with small batched classifiers for four hand slots, Next, integer/fractional
   elixir, and the visible clock. Train Next on the existing 7,919
   future-confirmed labels. Return score margins and calibrated probabilities.
3. **Persistent arena detector service.** Load the detector once, aggregate
   selected frames across many games into dynamic batches, use CUDA AMP, and
   keep one lightweight stream/state namespace per replay. Benchmark the current
   dual model first; then test a distilled single detector only if held-out
   precision/recall and rare-class coverage remain intact.
4. **Refresh the visual vocabulary.** Annotate November-2025 and fresh 2026
   frames for every enabled/reachable unit, evolution, tower troop, deployment
   marker, bar, projectile, and visible status/effect. Old KataCR weights may be
   teacher initialization, not ground truth.
5. **Dual placement evidence.** Combine Clasher's two-frame deployment-clock
   agreement with KataCR's elixir-bubble bottom-center/OCR/cost cue. Accept a
   label when independent cues agree; retain single-cue rows at lower confidence
   for audit, not strict location training.
6. **Current-frame semantic heads.** Add calibrated heads for opponent card-play
   identity/onset, visible status onset, attack animation, shield, and spell/
   projectile/effect identity. Output no remaining timer or hidden state.
7. **Offline teacher association.** Run ByteTrack/bar association and adjacent-
   frame fusion only in the label path. Store evidence provenance and never
   serialize accumulated state into the live input archive.
8. **Acceptance gate.** On replay-disjoint, arena-diverse, current-client manual
   labels, report per-class precision/recall, team accuracy, HP MAE/coverage,
   clock error, play-event precision/recall/duplicate/timestamp error, status
   onset metrics, and placement tile error. Render grids and boxes for every
   canary before scaling.
9. **Scale only after a 25-game H100 canary.** The local reference is 95.835
   trustworthy games/hour with median 33.027 s extraction and 19.166 s download
   (`reports/tv_royale_data_quality_and_expansion_20260817.md:148-169`). Once
   extraction falls below roughly 22 s/game, network is the bottleneck; add
   download concurrency rather than increasing detector batch indefinitely.

No H100 throughput multiplier is claimed until this exact cross-game pipeline
is benchmarked. The acceptance target is better semantic accuracy at at least
100 games/hour, not maximum raw FPS.
