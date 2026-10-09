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

## Round 2

Round 1 remains the coordinator-accepted conservative L2-v4 tower component. Round 2 adds training-only destruction truth, more rubble support, public King activation, own-King HP and a public match-result interface. **Eight fresh training dev matches / 22,059 frames** contain **seven eligible princess destruction events; all seven were confirmed**. The persistent tower model recalled **13,212/13,581 destroyed observations (97.28%)**, with **0/74,179 false-destroyed living-princess observations** and no affected match. Current-frame rubble observations alone recalled **8,906/13,581 (65.58%)**; persistence is essential to the reported 97.28% result.

### Truth and fresh-dev separation

`round2-manifest.json` pins SHA256 **`6f74fdf6cf189c7f268dc9d1f73090eb7724c306d3cf68b858df2807d90bffae`**. The canonical repository split is `../split.json` (the frozen L1 membership file), with the unchanged **`3edbd25b…`** digest. Available training cache names were ranked by the identical `SHA256(tower-channel-v1:episode)` rule. After excluding all 24 round-1 fit and eight round-1 dev matches, the first eight remaining matches became fresh dev; the next 24 augmented the original 24 fit matches. All 56 episode memberships were checked before their payloads were opened. No formal validation match, heldout/sealed payload, amendment or `noise-measured.json` was read.

`truth_r2.py` verifies fenced complete ordinary object collections, fixed anchors, native IDs, positive integer HP and supported max HP. Identical repeated ordinary ticks are coalesced only when tower identities/HP agree; contradictions fail closed. A princess missing at capture start is masked. Destruction requires an earlier positive-HP witness, permanent disappearance through the remaining snapshots, two subsequent coherent snapshots with both Kings alive, and both disappearance/continuation ticks strictly before the receipt's terminal tick. Capture teardown, missing Kings and transient dropout cannot establish destruction. The interval `(last_positive_tick, first_absent_tick]` bounds the native death; truth inside that interval and at/after terminal is masked. These native labels exist only in the offline study, never in runtime inference.

Ordinary/rich collection keys and all rich player records were inspected across the fit/dev pool. **No stored crown, score or winner field exists** in these collections or in the stored HUD records; a crown cross-check is therefore unavailable. The collector source shows that it records `terminal.ended` from the native `obs.ended` flag. The endpoint audit found one King disappearance in this pool, fresh-dev episode `1975101267`, exactly at **tick 4554 with `terminal.ended=True`**. There are no continuing King-rubble positives. This corroborates terminal handling, but does not independently measure the three-crown count.

The 48 fit matches supplied **20 disappearance events and 1,575 stable rubble crops**, replacing the 15 manual fit annotations. Rubble samples start at least 20 ticks (one second) after first absence to avoid collapse/crown transitions. Eight fit-derived rubble centroids per princess slot share samples within each side. Round-1 alive templates and own-princess glyph templates remain intact; rubble distance/margin and three-frame confirmation requirements are unchanged.

`round2-freeze.json` records **2026-10-09T02:22:02Z**, recognizer SHA256 **`6070598b1dd02549b8b1b987fd55192f51611bad1b72101e2ab7f0d10a642571`**, candidate model **`8946523c…`**, manifest and truth/scoring source hashes **before any fresh-dev pixels were decoded**. Dev native labels were prepared separately without pixels. No source, visual template or threshold was tuned after dev. The sole deployment change is the predeclared per-family ≥99% accepted-number gate: opponent numbers are disabled. Deployed artifact SHA256 is **`09850226b90293ba70d0dfa0d6e16588a2cf297106a7bfc71a067ce81b941668`**. Exact per-match truth/cache receipts and event brackets are in `round2-truth-receipt.json`, `round2-fit-receipt.json` and `round2-dev-result.json`.

### Destruction recall, delay and false-destroyed bound

All **7/7** princess events were eventually confirmed before terminal. Mean confirmation latency is **2.629–2.786 seconds**, bounded using the confirmation frame's tick bracket and the death interval. Event-specific lower/upper bounds span **1.950–4.650 seconds**. The slowest event is opponent-left in `1975101276`: 4.500–4.650 seconds. This includes visual collapse/occlusion and the three distinct-frame confirmation delay; it is not merely classifier compute time. Seven events are limited sensitivity support; the one-sided 95% exact lower bound for event recall is about **65.2%**.

False destruction is **0/74,179 living princess observations** (and **0/118,065** across all living towers). The one-sided 95% exact binomial upper bound is **0.00404% per princess observation**, or **0.00254%** across all tower observations. Those bounds assume independent observations; adjacent frames are correlated. Treating each match as a unit gives **0/8 affected matches and a 31.23% one-sided 95% upper bound** on the probability of at least one false destruction in a match. Both granularities are reported so the frame count does not imply strong match-level safety evidence. The persistent latch also produced **zero living-princess frames incorrectly held destroyed**. Alive recall across six slots was **116,000/118,065 (98.25%)**.

### King activation, HP and match end

The cannon wake animation distinguishes sleeping/active King crops in fit data. `TowerObservation.king_active` is an optional public Boolean, separate from life state and HP. A dedicated 12×16 crop feature and six templates per wake state produce a value only when the nearest template passes distance and separation checks. The public model latches an observed activation through later unknown/sleeping observations and resets it with the episode.

Offline activation truth uses the public wake rule: a witnessed princess destruction or positive King HP loss activates that side's King. An untouched full-HP King with both full-HP princesses at capture start supplies a sleeping witness. Uncertain capture-start state is masked. Fresh-dev accepted accuracy was **40,392/40,393 (99.9975%)**, with **40,393/43,886 (92.04%) coverage**. Opponent King: **20,047/20,048** exact; own King: **20,345/20,345**. One early wake transition was classified sleeping. These are current-frame accepted readings, not a separately measured persistent activation accuracy.

| Number reader | Fresh-dev accepted / exact | Accepted accuracy | Eligible coverage | Deployment |
|---|---:|---:|---:|---|
| own princesses, original reader | 673 / 673 | 100% | 673 / 795 (84.65%) | enabled |
| own King, new reader | 136 / 136 | 100% | 136 / 447 (30.43%) | enabled |
| opponent princesses, candidate | 250 / 247 | 98.8% | 250 / 802 (31.17%) | **disabled** |
| opponent King | 0 / 0 | unmeasured | 0 / 447 | abstain |

Opponent glyphs use fit-only foreground and centered-number geometry plus separate numerical templates. Fit accuracy was 1,092/1,095 (99.73%), but fresh dev missed the ≥99% gate. The deployed channel continues to rely on opponent bars; **323/323 accepted bars** were within five percentage points on coherent HP truth. Own-King text uses the lower, visible number line; opponent-King numbers fall outside the sanitized arena and remain unread. Post-scoring recomputed family denominators from frozen labels to exclude unread opponent-King samples from own-princess coverage; predictions and the acceptance gate are unchanged. HP evaluation retains round 1's coherent same-tick ordinary/rich join and at-most-five-tick frame age, distinct from the denser complete-snapshot life-state labels.

King death is **never a rubble classification**. `public_root.PublicMatchResult` accepts a public result-screen observation with episode, timestamp, `(opponent, own)` crowns and confidence. `PublicTowerAdapter.observe(..., result=...)` and `TowerPacketBuilder.build(..., result=...)` route it into the existing public packet terminal flag. Three crowns establish destruction only of the losing King, with `public_match_result` evidence. Other terminal results end planning without inferring King death. The packet adapter retains terminal state for the episode; the planner returns wait before root reconstruction/search, and the public-root wrapper rejects terminal roots. Results with a wrong episode, future timestamp or impossible crowns fail closed. The pixel recognizer cannot emit King rubble destruction.

**Integration gap:** existing `public_root` and live runtime had no result-screen producer; the existing `terminal` packet argument was available but not fed by a public result observation. This round provides and tests the connected consumer path. The capture/runtime owner still needs to recognize a public result screen and supply `PublicMatchResult`; no native receipt/ended field may be substituted. The worker did not modify `selection.py`, `runtime.py`, formal L1 decoder/runtime or perception-owner files. Visual activation is available in public observations and model diagnostics; existing native search reconstruction still uses its declared HP/princess-loss activation rule.

### Compute and verification

Fit extraction used eight CPU workers; frozen dev replay used four. All jobs, including tests and final timing, ran on **127x03**, launched with **`setsid nice -n 10`**, with OpenCV/BLAS/OMP limited to one thread, and fewer than 24 task processes. No GPU or heavy 127x05 computation occurred. Existing jobs were untouched. Private images, raw frames and extracted arrays stay in ignored `runtime/`; the committed numerical model is below 5 MB.

Candidate replay timing was **2.223 ms/frame mean**, p95 **2.789 ms**, over 21,931 measurements. After disabling opponent OCR, a separate fit-only timing check on 551 reconstructed six-slot canvases measured **1.474 ms/frame mean**, p95 **1.716 ms**, p99 **1.753 ms**. This second measurement includes all channel work but excludes canvas assembly/I/O and uses one process; it is not another full dev replay. See `round2-benchmark.json`.

Ten new regressions cover interval truth, coherent duplicate handling, capture-start/terminal/dropout masking, public crown-result routing, result episode persistence, planner terminal no-op, activation validation/latching, per-family glyph geometry/abstention and serialized fields. The round-1 suite remains unchanged. Final regression receipt and publication status are recorded below and in `PROGRESS.md`.

**Final regression: 85 tests passed, plus six subtests, in 28.73 seconds** on 127x03. This includes all 75 round-1 tests and ten new tests, using the same exclusions for the five unrelated native S6 parity tests. `round2-tests-receipt.json` records the isolated snapshot, tested file hashes and log digest.

The staged diff passed `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` and `git diff --cached --check`. Shared live files were staged hunk-by-hunk; only tower code/tests and this report directory were otherwise staged. No raw pixels or extracted arrays are published.

## Round 3

The public crown reader cuts mean princess destruction confirmation from **2.629–2.786 s to 0.814–1.007 s**, on the **same eight round-2 training dev matches / 22,059 frames**. Median delay fell from **2.150–2.350 s to 0.700–0.850 s**. **The p50 <0.5 s target is not met.** All **7/7** continuing princess destruction events remain confirmed; six now use `crown_increment_slot`, one retains the rubble fallback. No reader, threshold or attribution rule changed after the round-3 freeze/dev replay.

The new result producer recognizes positive **Match Over** text and routes it through `PublicTowerAdapter.observe` to the existing public terminal/three-crown consumer. An endpoint pixel audit gives **8/8 correct terminal-text classifications (2 positive, 6 negative)**. However, only **2/6 native-ended matches** expose that text before capture stops; the other four end during a scoring/collapse animation. **Win/loss/draw accuracy is unmeasured (0 legible full outcome screens)**. The typed observation and template matcher support those outcomes, but the deployed artifact has no fitted outcome-text templates and emits `outcome=None` for Match Over. This is a measured terminal producer and a latency improvement, **not completion of the full outcome-screen or sub-0.5-second goals**.

### Training boundary and fitting

`round3-freeze.json` pins the recognizer, adapter/root contract, deployed round-2 tower artifact, new score artifact, fitter, evaluator, truth source and unchanged `round2-manifest.json`. The split remains `../split.json`, SHA256 `3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258`. The canonical split is at v4 root; no alternative membership file was used. No formal validation, heldout/sealed payload, amendment, noise-measured file, or perception-owner data/code was opened or changed.

The availability audit decoded only all **48 existing fit-match endpoints and their 20 continuing disappearance windows**, checking training membership and receipt/cache/timing hashes before payload access. Six independently inspected frames in **fit episode 1975101330** label HUD scores 0/1/2 and the earlier three-icon scoring banner; its final frame labels Match Over. Exact ordinals/labels are in `round3-fit-receipt.json`, and source hashes/end ticks in `round3-pixel-audit.json`. The new numerical artifact is **360,768 bytes**, SHA256 `3dc37912484780227663c76754509abf450c4cc3ba40e9a7015619704dc8cf36`. Images, JPEG audit sheets and decoded arrays remain private ignored `runtime/r3` outputs.

Round-2 dev pixels never influenced this new fitting, crop selection, thresholds or attribution logic. Therefore the unchanged round-2 dev slice was eligible under the requested exception; no new dev carve was needed. Post-freeze dev endpoint inspection is recorded separately in `round3-result-audit.json`; it informed limitations only, never model/source tuning.

### Public crown evidence and attribution

`crown_counter.py` reads opponent/own scores from the public **right-edge arena HUD**, plus the **three-icon scoring banner**. Top HUD pixels remain masked. HUD counters can lag the early banner; simultaneous accepted reads use the larger count. Missing/unmatched crops abstain. The artifact supports HUD digits 0/1/2, own banner 1 and opponent banner 1/2; **three crowns and own banner 2/3 remain unsupported**, requiring fresh fit data before deployment. Fixed geometry is 540×1140 uint8 BGR. Numerical scores are template similarity, not calibrated probabilities.

A score is neither slot identity nor match end. The tower channel requires two distinct consistent crown observations, a one-crown increment, a recent positive living witness, no current positive HP/bar, and **exactly one eligible princess on the losing side**. A positively witnessed living King and both princesses supply a public zero-score baseline; a capture starting with an absent princess cannot establish it. Missing crops alone, ambiguous left/right slots, count jumps, stale witnesses, duplicate/backwards time and episode changes fail closed. Crown pending evidence expires after one second. Late scores are credited to previously confirmed rubble, preventing the same increment from destroying the other princess. The persistent model consumes the new evidence through its existing typed six-slot channel; no tower-model changes were required.

Against chronological native count labels derived from the unchanged offline princess truth, accepted crown readings are **745/821 exact (90.74%)**, with **0 counts ahead of witnessed destruction**. The 76 mismatches are lagging counts during scoring animation, not accepted overcounts; they remain in the denominator. No threshold was retuned to remove them. The reader accepted something in 447/22,059 frames; it is a transient-event aid, not a continuously complete scoreboard. Native labels are offline scoring inputs only.

Per-event confirmation intervals, seconds:

| Training dev episode / destroyed slot | Before | After | New evidence |
|---|---:|---:|---|
| 1975101260 / opponent right | 2.15–2.35 | 0.40–0.65 | crown increment + slot |
| 1975101260 / own left | 2.20–2.35 | 0.70–0.80 | crown increment + slot |
| 1975101276 / opponent left | 4.50–4.65 | 0.55–0.85 | crown increment + slot |
| 1975101276 / opponent right | 2.00–2.20 | 2.00–2.20 | rubble fallback |
| 1975101267 / opponent right | 3.45–3.55 | 0.70–0.85 | crown increment + slot |
| 1975101267 / own left | 1.95–2.05 | 0.65–0.80 | crown increment + slot |
| 1975101295 / own left | 2.15–2.35 | 0.70–0.90 | crown increment + slot |

### False destruction and result-screen limits

The persistent latch yields **0/74,179 false-destroyed living-princess observations**, with the unchanged one-sided 95% exact upper bound **0.00404% per observation**. Across all towers it remains **0/118,065**. Correlation matters: **0/8 affected matches** gives a **31.23%** match-level upper bound. These small-sample bounds are not a safety guarantee, and reusing the slice does not add independent matches to round 2.

`result_screen.py` exposes `ResultScreenObservation(episode_id, timestamp_ms, outcome, crowns, confidence)`. Each crown may be unreadable (`None`); outcome is win/loss/draw only when explicitly matched, otherwise unknown. Positive terminal text needs two distinct frames no more than 600 ms apart. Equal crowns never establish a draw; scores may still animate when Match Over appears. Historical counts expire after 500 ms. Result observations persist only within their episode, and convert to the round-2 `PublicMatchResult`. A three-crown count can destroy only the opposing King; Match Over with unknown/partial scores ends planning without inventing King death. Both measured positive results had unreadable final counts and outcome.

Frozen replay emitted **0 false terminal observations in 21,933 eligible preterminal frames** and **19/87 accepted terminal frames**. Those terminal-frame counts are correlated repetitions within just two matches. Of the six native-ended matches, four stop during a scoring banner, including the King-end example, and supply no positive Match Over text. The two remaining captures hit the requested collection end tick with `terminal.ended=False`. The eight-endpoint visual audit is terminal-text accuracy, **not win/loss/draw accuracy**. `round3-dev-result.json` contains exact per-match observations, tick brackets, event intervals and provenance.

### Tests, compute, and runtime-worker handoff

Eight new tests cover positive crown attribution, ambiguity/absence, capture-start masking, stale/jump/episode handling, delayed-score credit, reader arbitration, typed serialization, end-text debounce/persistence, unknown scores/outcomes, all outcome labels and terminal packet routing. The isolated accepted round-2 regression snapshot plus owned round-3 changes passed **93 tests and six subtests**. After the final timestamp-validation/outcome-abstention clarification, the focused tower/result/transport suite passed **44 tests**; the final full frozen-source regression is recorded in `round3-tests-receipt.json`. Concurrent runtime/perception edits were excluded from that snapshot.

All audit/fitting/replay/test processes ran on **127x03**, CPU-only, detached with **setsid**, **nice 10**, single-thread OpenCV/BLAS/OMP, at most four replay workers plus their controller (and one test process). All caches stayed under `/mpac`. New crown + tower + result work averaged **3.499 ms/frame**, p95 **3.813 ms**, p99 **3.885 ms** over 21,931 measurements, excluding cache I/O. This includes the result reader and the deployed opponent-number-disabled channel. No heavy work ran on 127x05, and no other jobs were changed.

`selection.py` and `runtime.py` were not edited. Existing perception calls already invoke the adapter, so **no runtime behavior patch is needed for the new producer**. The runtime worker must add the new default artifact to provenance hashing with this exact patch in `provenance(config)`:

```diff
     files.append(Path(__file__).with_name('tower_channel_templates.json'))
+    files.append(Path(__file__).with_name('public_score_templates.json'))
```

For complete outcome/three-crown coverage, the capture owner needs **training-only post-match frames through the full result screen**, with emulator/UI progression continuing after native ended; the existing collector calls pause at native end and captures only another 0.7 seconds. Simply prolonging a paused screenshot stream does not demonstrate that the UI will advance. Request examples with explicit win/loss/draw text and final 0–3 crowns. Additional early-transition fit data and an untouched SHA-ranked dev carve are needed for a further attempt at p50 <0.5 s; do not tune on these dev frames.

Publication stages only owned hunks/new files, checks whitespace and the required staged secret scan, and pushes origin main. No raw frames, images or weights over 5 MB are included.
