# L1 results

L1 v0 fails acceptance. The offline collector, trained YOLO/HUD baseline, PublicVisionFrame inference and heldout scorer are implemented and executed. This model is not ready for L2 control. No official client, account, ladder or game-app network was used. No engine, gamedata, native probe/APK or protected evidence directories were edited.

## Dataset and pairing

Eight rendered P16 match traces, eight distinct seeds and sixteen distinct decks. Splits are 238 training frames, 86 validation frames and 171 heldout frames. The additional training-only Tesla match filled a missing owner/card combination before heldout evaluation. All 30 owner/body-or-tower classes have training examples, with a minimum of only six examples for the rarest class. HUD training covers all sixteen cards and all ten digits. C56 was not run.

There are 495 sanitized 540x1140 JPEGs totaling 51,500,427 bytes, or 51.50 MB. The full dataset occupies 52,943,269 bytes, or 52.94 MB, below the 3 GiB cap. All L1 PT checkpoints, including the smoke run, total 24,882,432 bytes, below 1 GiB. Raw PNGs existed only in memory.

The simulation was paused at every capture. All 495 before/after observe packets were identical, all JPEG hashes pass, and all frame IDs match their pairing ticks. The native launcher verified the pinned attestation and app-UID IPv4/IPv6 rejection rules before app launch. There was one emulator at a time. All owned launches were stopped; foreign processes were not signalled.

The fixed cadence is 40 ticks, or 2 seconds. Startup uses 1x speed to clear the intro, followed by 4x stepping. Only frames with visible clock glyphs are admitted. The red 0:30 warning required a segmentation correction; collection resumed at the untouched paused next tick with no repeated action. Its future policy sub-seed is recorded in `dataset/resume.jsonl`. Earlier intro-occluded attempts were quarantined and excluded.

| Episode | Split | Frames | Final native tick |
|---|---|---:|---:|
| l1-261004100 | train | 21 | 1012 |
| l1-261004101 | train | 20 | 1007 |
| l1-261004102 | train | 86 | 3600 |
| l1-261004103 | train | 85 | 3580 |
| l1-261004104 | validation | 86 | 3600 |
| l1-261004105 | heldout | 85 | 3580 |
| l1-261004106 | heldout | 86 | 3600 |
| l1-261004902 | train | 26 | 1200 |

Two main traces ended naturally; the others were time-capped. These are not eight full-game acceptance runs. Native identity, tile position and HP ratios are ground truth. Pixel boxes are approximate class extents around calibrated ground anchors, not exact sprite silhouettes. Occlusion/visibility is not individually certified, and hp-less spell/projectile phases are excluded from detector labels. Those limits prevent calling this a fully certified visible-object dataset. Accepted native play receipts are evaluation-only, never model events or inputs. Opponent hand/elixir/cycle and exact fractional own elixir are kept only in `evaluation_only/`; own-elixir training targets are the displayed integer.

There is no compositor fence in the existing probe. Paused observe equality, visible-clock readiness and visual checks support pairing; they do not independently prove every animation pose belongs to an exact render tick. Heldout clock OCR agrees with native timer labels on all 171 frames.

## Calibration

At JPEG resolution, pixel x = 28.54545 × tile x + 12.09091 and pixel y = 22.89474 × tile y + 237.18421. Four manually reviewed Princess-tower ground contacts fit the affine mapping. Two kings and a placed Tesla were held out.

Mean heldout residual is 0.04797 tile, maximum 0.08873 tile. Maximum pixel residual is 2.034 pixels. Manual landmark uncertainty is approximately four JPEG pixels, larger than the fitted residual. This is a sparse ground-anchor calibration, not a silhouette or broad dynamic-unit calibration. Native owners and coordinates are retained; the own player is 1.

## Training and heldout measurements

YOLOv8n was trained from scratch on MPS for 40 epochs, image size 416, batch 8. The selected checkpoint's validation mAP50 is 0.532 and mAP50-95 is 0.394 against weak boxes. Model selection used validation only. No model or threshold tuning followed heldout inspection. A final body-token naming correction was verified to leave every numeric prediction and quality gate unchanged. Training source hashes and a source archive accompany the model.

Best checkpoint SHA-256: `966c1c46f98e2a85270f3fd5c265052af38b4f1c3f0e88480ab21a3cf0e99ba2`.

| Measurement | Heldout result | Gate / interpretation |
|---|---:|---|
| Clock MAE | 0.000 s; 171/171 readings | Pass, <=1 s |
| Entity identity/owner recall | 1039/1636 = 63.51% | Missing bodies count as misses |
| Entity position within one tile, all truth | 1035/1636 = 63.26% | Below 90% |
| Crown-tower recall | 907/908 = 99.89% | Dominates aggregate success |
| Non-tower body recall | 132/728 = 18.13% | Fails useful unit coverage |
| Non-tower position within one tile | 128/728 = 17.58% | Misses included |
| Matched-entity mean position error | 0.0816 tile | Conditional on matching identity/owner within 3 tiles |
| Public play events | 18 TP, 50 FP, 135 truth | Precision 26.47%, recall 13.33% |
| Contract placement within one tile | 8/18 matched plays = 44.44% | Fail, >=90%; 117 additional plays missing |
| HP MAE, all available readings | 0.04474 on 602/1636 = 36.80% coverage | Numerical <=0.10 gate passes; missing-value gate fails |
| Crown-tower HP | MAE 0.02663; 565/908 = 62.22% coverage | King HP is unimplemented |
| Non-tower HP | MAE 0.32140; 37/728 = 5.08% coverage | Fails error and coverage |
| Own hand, per slot | 674/684 = 98.54% | Measured accuracy; no numeric own-hand threshold is defined in the contract |
| Own hand, all four slots correct | 161/171 = 94.15% | Full-hand accuracy |
| Own next card | 159/171 = 92.98% | Current-frame template reader |
| Own displayed integer elixir | 170/171 = 99.42%; MAE 0.01293 | Integer-label accuracy |
| Public status reader | No scored samples | Gate fails; not implemented |

The canonical `scripts/evaluate_live_inference_contract.py` reproduced every metric and gate from the L1 scorer. Its exit code was 1 because acceptance failed. Frozen predictions were loaded before truth. Post-inference one-to-one association uses identity, owner and a three-tile matching radius; wrong identities, wrong owners, missed objects and unmatched events are not silently dropped. Full details are in `evaluation-final/metrics.json`, `evaluation/body-breakdown.json` and `evaluation-final/contract-check.json`.

Visual checks in `heldout-prediction-5.jpg` and `heldout-prediction-45.jpg` confirm tower localization and missed troops/retracted Teslas. The three spells have no detector, and Ice Spirit has no heldout body samples at this cadence.

## Throughput on the Apple M4 Pro

| Path | Samples | FPS | Mean latency | p99 latency |
|---|---:|---:|---:|---:|
| JPEG decode through PublicVisionFrame, first run during emulator startup | 171 | 22.68 | 44.09 ms | 75.81 ms |
| Final body-name-corrected rerun, emulator off | 171 | 39.90 | 25.06 ms | 40.82 ms |
| Final PNG adb capture through serialized PublicVisionFrame | 10 | 0.522 | 1915.53 ms | 2045.11 ms |
| Final raw RGBA adb capture through serialized PublicVisionFrame | 10 | 1.607 | 622.25 ms | 842.20 ms |

The model path passes 10 FPS; capture-inclusive paths fail. The two inference runs produce identical predictions after normalizing three body names; the runtime conditions differ. Timings use batch 1, explicit MPS synchronization and three warmup frames. Capture measurements use a paused offline scene, include sanitization/downscaling and exclude search/action execution. Other host jobs remained running. The earlier capture run measured 0.652 FPS PNG and 2.016 FPS raw; both runs fail the target. The final emulator startup required one restart of the same isolated app after a startup crash, followed by successful attestation. Raw transport improves throughput but does not meet the L2 400 ms end-to-end latency target even before search.

## Derived public state

The unmodified `srp-public/derived_public_state.py` was run on perceived opponent events and the perceived clock. The prior is the uniform fourteen-deck experimental population frozen before heldout capture, with no episode-to-deck assignment. The extra training support deck was not used to identify the heldout opponent.

Opponent elixir MAE is 5.25067 on 33/171 frames before posterior failure, versus the contract maximum of 0.5. Valid coverage is only 19.30%. Posteriors collapse at frame 460 of seed 261004105 and frame 1280 of seed 261004106 because the perceived play stream is inconsistent with every candidate hand/order. No truth repair or fallback hand is injected. Opponent hand is unresolved on all 171 frames: exact recovery 0%, conditional accuracy undefined. Cycle accuracy is 14.29% on 42 answered labels, with 1326 missing labels. These are failures, not evidence against the module on a correct public event stream.

## Gaps before L2

1. Improve non-tower identity/owner recall. Add balanced examples, meaningful small-unit resolution and independently reviewed sprite/visibility labels. The current weak-box validation score does not establish unit perception quality.
2. Capture at a much higher cadence and detect actual deployment/spell cues. New body tracks are not reliable play events; the 2-second cadence misses short-lived effects and allows units to move before placement is observed. Fireball, Log and Zap need visible-phase labels and readers.
3. Read damaged and healthy troop bars, shield states and King HP with verified association. Current aggregate HP error hides extremely low body coverage and poor body HP accuracy.
4. Add public-status perception and match lifecycle handling. Complete the input coverage gates before connecting the fair search player; the existing adapter's default 400 ms cadence is incompatible with this dataset's 2-second sampling.
5. Replace per-frame screencap with a tested faster local capture path and measure moving-match throughput. Raw capture alone remains below 10 FPS and above the L2 latency budget.
6. Re-evaluate derived state on accurate, deduplicated public events and sufficiently precise public time. Both present posteriors fail. Validate C56 visual forms and resource/cycle rules separately; the current collector and derived-state assumptions are P16 only.

## Files and verification

New code: `src/clasher/vision/{__init__,l1,l1_perception,l1_offline}.py`; `scripts/{collect_l1_rendered,audit_l1_dataset,train_l1_perception,infer_l1_perception,evaluate_l1_perception,run_l1_pipeline,benchmark_l1_capture}.py`; `tests/test_l1_vision.py`. Artifacts and documentation are under this L1 folder.

34 tests passed across the focused L1 suite and existing live-contract/perspective suites. Dataset audit passed all 495 receipts/hashes and verified seed/deck separation. Canonical scoring reproduced the failed acceptance result. Ownership, launch, firewall and stop evidence are in `emulator/`, `emulator-benchmark/` and `emulator-final/`. No owned emulator or long-running L1 job remains.
