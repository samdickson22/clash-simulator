# Public tower-state channel — training-only dev study

Built a detector-independent six-slot channel and integrated it with v4 perception and the persistent public tower model. On **8 disjoint training-split dev matches / 11,019 frames**, the recognizer averaged **1.376 ms/frame**, p95 **1.556 ms**, with **0/1,844 false-destroyed predictions on coherent alive truth**. Alive recall was **1,813/1,844 (98.32%)**; remaining observations were unknown. Accepted integer HP readings were **499/500 exact (99.8%)**.

This is an engineering channel, **not an L1 formal-gate result or L2 admission**. The current artifact has no destroyed King examples and therefore cannot establish King destruction. It also abstains on King HP numbers. These are remaining coverage gaps, not evidence that the towers are destroyed or that their HP is full. Princess destruction has only one independently audited positive dev crop, so its sensitivity is weakly measured.

## Data separation and provenance

- Frozen v4 membership: `../split.json`, SHA256 **`3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258`**. Read L1 PREREG/RUNBOOK and `validation_replay_v4.py` to establish the boundary. None of the 64 formal validation matches, heldout media/labels, sealed payloads, amendments or `noise-measured.json` were opened for this study.
- Study manifest: `study-manifest.json`, SHA256 **`3a8841322eda08329d0ee8e956b74257f9f2af62ec9d6b9f5bd831c22ed0f174`**. Rank available training cache episode names by SHA256 of `tower-channel-v1:episode`; first 24 fit, next 8 dev. Membership was checked before opening per-match payloads. Dev matches never entered sprite/glyph fitting or threshold tuning.
- Read-only inputs on **127x03**: `clasher-v4-cpu/matches` and `clasher-v4-cache`. The fitter used 5,541 coherent positive-HP tower samples from the 24 fit matches and 15 manually labelled fit rubble crops. Generated crops, full frames and audit sheets remain private ignored `runtime/` outputs; none are committed.
- Capture geometry: historical affine calibration SHA256 **`af06e029c50c3e2932f829a8891d6f6bdca654912d6beff512ab5864cc8c60d8`**. Only its public tile-to-pixel matrix is used. Native/public owner 0 is opponent at y=3/6.5; owner 1 is own at y=29/25.5. TileGrid's BLUE/RED names do not imply the live own/opp mapping.
- Final model SHA256 **`9d7f21fb7ee3ab53774056208e352a59d3f5fa5bcb42ebfe2309449bd8d7f014`**, recognizer source SHA256 **`84abdf95dd72e1f9b77f2849763026c973735243c96d9337930b8ef4cacb6410`**. `freeze.json` pins both before dev pixels were extracted. `fit-receipt.json`, `dev-result.json` and `truth-audit.json` carry input receipt/cache/truth hashes. No parameter changed after dev evaluation.

Native truth follows the tower diagnostic's public-anchor join: ordinary `owner`, `card_id=-1`, `x`, `y`, `hp`, `max_hp`, with exact same-tick rich `owner`, `cardId`, `x`, `y`, `hp`, `maxHp`; require `visibilityState=visible`, `deployRemainingMs=0`, and a snapshot at most five ticks before the frame's bracket midpoint. Tower identity uses the six fixed anchors and supported static HP catalog, not detector labels. An independent audit found no repeated rich ticks or duplicate ordinary tower candidates in these 32 matches; the direct joins therefore agree with the diagnostic's duplicate safeguards. Native fields enter fitting/scoring only. Missing native truth is masked, never labelled destroyed or visually unknown.

## Per-slot confusion

Native-positive-HP truth, scored after pixel inference. Columns are **predicted alive / destroyed / unknown**. No eligible native zero-HP observations occurred; the destroyed and unknown truth rows have **zero support**, not perfect accuracy.

| Slot | Truth alive → A / D / U | Truth destroyed | Truth unknown |
|---|---:|---|---|
| opp king | 310 / 0 / 0 | unmeasured | masked |
| opp left | 299 / 0 / 11 | unmeasured | masked |
| opp right | 297 / 0 / 13 | unmeasured | masked |
| own king | 308 / 0 / 2 | unmeasured | masked |
| own left | 292 / 0 / 2 | unmeasured | masked |
| own right | 307 / 0 / 3 | unmeasured | masked |

A separate **48-crop visual audit** used the last extracted ordinal of each dev match, labelled before opening inference output. Its rubric requires an upright structure for alive, collapsed stones with crossed broken timbers for destroyed, and unknown where an opaque transition hides the structure. It is separate from the native table; do not add their denominators because some crops overlap.

| Slot | Truth alive → A / D / U | Truth destroyed → A / D / U | Truth unknown → A / D / U |
|---|---:|---:|---:|
| opp king | 8 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| opp left | 8 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| opp right | 8 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| own king | 8 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| own left | 6 / 0 / 0 | 0 / 1 / 0 | 0 / 0 / 1 |
| own right | 8 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

See `dev-visual-labels.json` for exact episode/ordinal and annotation evidence, and `dev-visual-result.json` for scoring. The observed false-destroyed rate is **0%** on 1,844 native alive observations and **0/46** visually alive audit crops. This is not a guarantee of zero future errors: frames are correlated, only eight matches were evaluated, and destroyed-state support is particularly small. The full replay emitted 800 destroyed observations at own-left; those unlabelled frames are not treated as 800 independent ground-truth positives.

## HP numbers and bars

Integer `hp_known` means a complete accepted HP-number reading. A bar-only observation leaves `hp_known=false, hp=null` and supplies the separate `hp_fraction`. No max-HP value is inferred from a possibly damaged first observation. No bar absence or OCR zero can destroy a slot.

| Slot | Eligible alive | Integer reads / exact | Integer coverage | Bar reads | Bar error ≤5 percentage points |
|---|---:|---:|---:|---:|---:|
| opp king | 310 | 0 / 0 | 0% | 0 | unmeasured |
| opp left | 310 | 0 / 0 | 0% | 8 | 8 / 8 |
| opp right | 310 | 0 / 0 | 0% | 279 | 279 / 279 |
| own king | 310 | 0 / 0 | 0% | 0 | unmeasured |
| own left | 294 | 220 / 219 | 74.83% | 0 | unmeasured |
| own right | 310 | 280 / 280 | 90.32% | 0 | unmeasured |

Own-left accepted-number accuracy is **99.55%**, own-right **100%**. Across all princess observations, number coverage is **500/1,224 (40.85%)** and exact-reading coverage **499/1,224 (40.77%)**. Opponent number recognition abstained throughout this dev slice; no post-dev tuning was performed to improve it. The 287 accepted opponent bars had **100% within 5 percentage points**, mean absolute error **0.200 percentage points** against native HP divided by the public level-11 maximum. Native frame-time uncertainty can contribute to disagreements. The one accepted integer error was retained in the result; it was not tuned away.

## Runtime implementation and consumption

`src/clasher/live/tower_channel.py` reads only sanitized **540×1140 uint8 BGR** pixels, episode identity and public timestamp. The six screen centers come from capture geometry. Each slot has a 96×150 sprite crop and a 110×80 side-specific HP panel. Sprite features are 12×18 BGR averages, compared with four alive centroids and at most three rubble centroids per slot. Unknown/out-of-template crops abstain. The numerical JSON artifact is approximately 496 KiB; no raw image or large weight file is included.

Destruction requires a close **positive rubble-template match**, separation from alive templates, and three distinct consecutive observed frames no more than 600 ms apart. A blank crop, low HP number, empty bar, classifier rejection or detector dropout never establishes destruction. King rubble templates are empty because fit data supplied no King destruction examples. The sanitizer removes crown HUD regions, so no hidden/blanked HUD is read; king activation is not equated with King death. Template scores are similarity scores, not calibrated probabilities.

Each `TowerObservation` carries stable slot, current state, integer HP-known/value, similarity confidence, last positive observation timestamp, explicit destruction evidence and optional public bar fraction. Missing observations emit `unknown` with no current HP reading and retain only the earlier timestamp. Episode changes reset timestamps and confirmation state; duplicate/backwards timestamps fail closed. The optional `PublicVisionFrame.tower_observations` field defaults to empty for old producers. Parsing checks complete/unique slot membership, HP/state consistency, evidence and timestamp validity. Existing detector tracks are preserved by `PublicTowerAdapter`.

`perception_adapter.py` attaches the channel to both reference and vectorized v4 live perception; `perception.py` accounts for its time and includes it in event availability timestamps. Formal L1 decoder/runtime source files were not edited. `runtime.py` includes the numerical artifact (and any configured replacement) in provenance. Packaging includes the JSON artifact.

`PublicTowerModel.reconcile` consumes these observations using the same slot order as its geometry priors. When the channel is present, body class labels and body HP cannot replace slot identity/HP. It persists living slots through unknown observations. Accepted integer HP is normalized with the existing **declared public tournament-level-11** tower statistics (`tower_scaling.tower_stat`); a visible bar fraction is the fallback. This static maximum is an explicit model rule, not a runtime native measurement. No accepted measurement leaves the existing HP prior in place with low confidence. Public destruction latches a zero-HP slot until the next episode, even if subsequent body detections conflict. Zero-HP slots remain in the existing six-slot packet ABI.

`tower_packet_builder` activates automatically when a frame supplies the channel; older producers retain their existing behavior unless the prior-model option is explicitly enabled. Thus the v4 channel is actually consumed by the planner without requiring a second flag. `public_root.py` was read and its existing contracts left intact.

## Latency and compute

All fitting, extraction, inference and tests ran on **127x03**, CPU-only, under `nice -n 10`. Extraction/fitting/replay each used one process, OpenCV one thread, and BLAS/OMP one thread. Jobs were launched with `setsid`; the existing loss_review/perception jobs were not changed. No compute ran on 127x05 beyond file editing and lightweight repository operations. No GPU, roader, tailscale, crontab or Mac-mini access occurred.

Replay timed all six crops, classification, number/bar reading, confirmation and typed observation construction. Cache I/O is excluded. After the first 16 frames/match warmup, **10,891 measurements** gave mean **1.376 ms**, median **1.426 ms**, p95 **1.556 ms**, p99 **1.773 ms**, max **3.832 ms**. Typical latency meets the <2 ms target; it is not a worst-case bound under host scheduling.

## Tests and remaining work

Added eight tests in `tests/live_v4/test_tower_channel.py` for fixed identity, missing/occluded frames, last-observation retention, positive destruction confirmation and gap/episode reset, contradictory detector HP, persistent zero-HP destruction, evidence/transport validation, immutable raw body output, calibrated input dimensions, automatic packet consumption and serialized roundtrip. Existing tower-model zero-HP/identity/duplicate tests remain supported.

**75 tests passed, plus 6 subtests, in 34.19 seconds** on 127x03, including all eight new tests. `tests-receipt.json` records the command and tested source hashes. The selected suite is `tests/live_v4` excluding the five unrelated native S6 search-parity tests, plus `tests/test_rl_live_inference_contract.py`; it exercises perception, tracker, transport, supervisor, selection, timing, tower model and the serialized public boundary. SciPy 1.14.1/OpenCV needed for existing vision tests were provided in an isolated test environment; owner environments and running jobs were not modified. Native S6 search-parity tests were not rerun; no native engine code was changed by this work.

Open question for the coordinator: obtain training-only examples of **King destruction and legible active King HP**, plus broader princess destruction/occlusion support, before treating this as a complete L2-v4 tower-state solution. Opponent number coverage also needs a future fit-only revision and a fresh untouched dev slice. The current channel delivers conservative six-slot observations and persistence, but does not remove those coverage blockers.
