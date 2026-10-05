# L1 progress

2026-10-04: Read workspace rules, survey, inference contract, adapters, reference launcher, transport, rendered Tesla capture and touch layout. Existing worktree is extensively dirty; only new L1 files will be written. One emulator planned; none running at preflight. Disk free 16 GiB. Dataset cap 3 GiB and model cap 1 GiB. Existing C56 workers, Stage 4 and watchdog processes are foreign and will remain untouched. Native dual HUD requires masking the opponent HUD before training/inference. Same-tick observe equality alone is insufficient without checking rendered scene freshness.

Offline launch succeeded with the existing launcher and detach wrapper. Owned emulator PID 46718, emulator-5580, probe 26789, read-only AVD, 3072 MiB / 2 cores. Launcher verified IPv4 and IPv6 UID 10208 REJECT rules and disabled Wi-Fi/data before starting the app; pinned attestation passed. Initial native-render capture at tick 200 has identical before/after observe packets and a visually valid arena. JPEG is 540x1140; PNG remained in memory. Full preflight evidence is diagnostic only and will not enter training. Existing 540x960 HUD coordinates do not fit this renderer.

Calibration saved: four Princess-tower ground contacts fit an affine transform, two kings and one deployed Tesla held out. Mean 0.04797 tile, max 0.08873 tile residual; manual uncertainty about 4 JPEG pixels. This is ground-anchor calibration, not exact sprite-box certification. Generator implemented with per-frame pause/state equality, sanitize-before-resize, in-memory PNG conversion, JPEG hashes, episode-disjoint seeds/decks, disk guard and separate evaluation-only private truth/event receipts. Seven P16 matches launched via detach, collector PID 53235. Three spells are excluded from body targets until their visible phases are certified; approximate body boxes are explicitly marked weak labels.

2026-10-04 11:54:08: Collected l1-261004100 train: 90 paired JPEGs, 66 accepted plays; dataset JPEG bytes 9155538.

Perception implementation now has a YOLO body reader, train-only HUD template bank, digit OCR, learned elixir-bar calibration, existing HP-bar measurement reuse, causal body tracking and PublicVisionFrame validation. No native imports or truth reads occur in its inference module. Body-only play cues will miss spells and can confuse newly acquired tracks with deployments; evaluation will count those errors rather than injecting accepted native actions into perception.

Found a collection validity issue during image QA: intro overlays hide the clock/HUD through tick 160, but native actions were already accepted. Stopped only owned collector PID 53235 and quarantined that run as rejected-intro-dataset. It is not training/evaluation evidence. Corrected collection warms up without plays to tick 200/220, verifies visible clock glyphs before accepting labels, alternates the fixed cadence phase between matches to cover all clock digits, and uses complementary first two training decks to cover every P16 card for both seats. Emulator remains owned and isolated.

Further readiness checks failed closed before any v2/v3 labels were saved: presentation-time intro persists even after fast native advance to tick 200. Added bounded repeated captures while keeping the exact tick paused, allowing the intro to drain before any action. Native integer elixir shown in the HUD is now the training target; exact fractional own elixir is evaluation-only. Earlier rejected runs are excluded. Current launch is collect-v4.log.

Paused waiting did not clear the accelerated intro, and v4 rejected all frames. Corrected warmup to the visually proven 1x path through tick 200/220, then switch to 4x only after warmup. No native/APK changes. Collection remains gated by actual visible clock glyphs, not just ready/tick metadata.

2026-10-04 12:02:12: Collected l1-261004100 train: 21 paired JPEGs, 16 accepted plays; dataset JPEG bytes 2206020.

The 1x intro warmup succeeded. Current collector PID 65604 is producing valid frames. Seven privacy/scoring/calibration tests passed. Pixel inference has its own strict media-only input manifest and cannot open labels through its API. Evaluation runs after predictions are frozen, scores missed entities/events and abstentions, invokes the unmodified derived-state module on perceived plays/clock, and records posterior collapse rather than repairing it with truth. A uniform 14-deck experimental population prior is frozen before heldout capture; it supplies no episode assignment.

2026-10-04 12:03:06: Collected l1-261004101 train: 20 paired JPEGs, 16 accepted plays; dataset JPEG bytes 4326312.

2026-10-04 12:06:38: Collected l1-261004102 train: 86 paired JPEGs, 71 accepted plays; dataset JPEG bytes 13279180.

32 tests pass, including the existing live contract and perspective sanitizer suites plus eight L1 privacy/pairing/scoring checks. Training-only HUD smoke covers all P16 cards and all ten clock digits. Elixir now uses digit templates with the bar as fallback. Started a two-epoch YOLOv8n MPS smoke using only the first two training episodes; this smoke is not heldout evidence. ML commands block external connections and keep Ultralytics settings under L1.

Two-epoch MPS smoke completed with finite losses and local 6.2 MB checkpoints. Its zero mAP is expected at this initialization check and is not acceptance evidence. Started a four-training-frame pixel-inference smoke to validate serialization and timing boundaries before heldout inference. Collector has completed three training matches; the third reached the scheduled tick limit.

Pixel-inference smoke completed and emitted canonical PublicVisionFrame JSON. Four training frames measured 38.7 FPS after warmup, but the model had no detections after two epochs; this is plumbing evidence only. Full 40-epoch training and heldout inference/evaluation are queued behind a successful dataset audit in owned detached pipeline PID 74543. Final performance will use the trained model and separately include adb capture cost.

Collection paused safely at training match 4, tick 3020: the visible timer turned red at 0:30, so white-only glyph segmentation rejected it. Inspected the screenshot and added red glyph support. Resumed exactly at the untouched paused next frame with no duplicate actions/frames; the future scripted-policy sub-seed is recorded in dataset/resume.jsonl. Owned resumed collector PID 78203. Earlier pipeline exited when collection stopped and is being relaunched against the new owned collector.

2026-10-04 12:16:09: Collected l1-261004103 train: 85 paired JPEGs, 64 accepted plays; dataset JPEG bytes 22030991.

2026-10-04 12:19:45: Collected l1-261004104 validation: 86 paired JPEGs, 71 accepted plays; dataset JPEG bytes 31022908.

Main training collection finished at 212 frames and validation at 86; heldout collection is active. Training body-label audit found all owner/card combinations except bottom-seat Tesla. Queued a separate training-only seed 261004902 with Tesla priority and a 1200-tick cap, merged only after confirming deck separation. The original heldout set is unchanged. Owned pipeline PID 84239 will collect this support match on the same emulator before training. A prior resume launch disappeared without an exit trace; its replacement is wrapped to record exit status, with active collector child PID 80295 under owned wrapper 80292.

Training now refuses to start if any of the 30 owner/body-or-tower classes has zero support. Model manifests pin source hashes and Torch version. All 33 focused and existing contract/privacy tests pass after red-clock coverage was added. Heldout collection is still running; no heldout metrics have been inspected or used for training choices.

2026-10-04 12:23:11: Collected l1-261004105 heldout: 85 paired JPEGs, 71 accepted plays; dataset JPEG bytes 39851895.

2026-10-04 12:26:40: Collected l1-261004106 heldout: 86 paired JPEGs, 64 accepted plays; dataset JPEG bytes 48813032.

2026-10-04 12:26:47: Starting support

Main collector exited 0. Main dataset: 469 paired frames, 48,813,032 JPEG bytes, splits 212 train / 86 validation / 171 heldout. The support collection is now running. Planned resource release: stop the owned emulator after support/audit, train on MPS, then relaunch one isolated instance for capture-inclusive timing. No foreign process controls are used.

2026-10-04 12:28:00: Collected l1-261004902 train: 26 paired JPEGs, 18 accepted plays; dataset JPEG bytes 2687395.

2026-10-04 12:28:00: Completed support

2026-10-04 12:28:00: Merged independent training-only Tesla coverage. Heldout frames and labels unchanged.

2026-10-04 12:28:00: Starting audit

2026-10-04 12:28:01: Completed audit

2026-10-04 12:28:01: Starting train

Final dataset audit passed: 495 frames, 51,500,427 JPEG bytes, 238 train / 86 validation / 171 heldout; 495 verified pairing/hash receipts, zero hidden-clock frames, eight disjoint seeds and sixteen distinct decks. Bottom-seat Tesla now has 25 body labels. All 30 body/tower classes have training support. Main MPS run started for 40 epochs. Owned emulator PID 46718 was stopped through its verified emulator-5580 console after collection; stop receipt saved. No emulator is needed during training.

At epoch 15/40, validation mAP50 is 0.28874 and class-averaged recall 0.25453 against weak boxes. These are validation diagnostics, not heldout gates. All training sources were hash-verified and archived in model/producer-source.zip. Current checkpoint disk use remains below 0.1 GiB, including smoke artifacts and optimizer states.

Training at epoch 29/40: validation mAP50 0.44222, class-averaged recall 0.42031. Final heldout scoring has not started. Report definitions now include exact opponent-hand recovery over all frames, with unresolved hands counted as not recovered, in addition to conditional accuracy and posterior-collapse coverage. Native owner IDs are retained; own player is seat 1.

2026-10-04 12:42:38: Completed train

2026-10-04 12:42:38: Starting infer

Forty training epochs completed on MPS. Selected-model validation: mAP50 0.532, mAP50-95 0.394, class-averaged recall 0.525 on 86 validation frames / 870 weak boxes. These are not heldout acceptance numbers. Benchmark emulator relaunched as owned PID 5775, emulator-5580; the existing launcher again verified isolation and pinned attestation. Final heldout inference/evaluation is pending pipeline completion.

2026-10-04 12:42:50: Completed infer

2026-10-04 12:42:50: Starting evaluate

2026-10-04 12:42:51: Completed evaluate

2026-10-04 12:42:51: L1 artifacts ready for final audit. Emulator still owned for capture-inclusive timing.

Heldout inference/evaluation completed on 171 frames. L1 acceptance FAILS. Clock MAE 0 s; own hand slot accuracy 98.538%, full-hand accuracy 94.152%, next 92.982%, integer elixir 99.415%. Entity recall 63.509%, all-truth within-one-tile 63.264%; tower detections dominate. Play events 18 TP / 50 FP / 135 truth, recall 13.333%. Placement gate only 44.444% within one tile among 18 matched events, with 117 missing. HP MAE 0.04474 at 36.797% coverage. Derived elixir MAE 5.25067 on 33/171 frames before posterior failures; both episodes collapse and no hand is recovered. Pixel-to-PublicVisionFrame inference is 22.679 FPS, p99 75.813 ms, excluding adb. Capture-inclusive benchmark is running under owned PID 8413.

Capture-inclusive benchmark completed, 10 frames per transport: PNG 0.652 FPS / p99 1620.27 ms; raw RGBA 2.016 FPS / p99 642.26 ms. Both miss 10 FPS, even on a paused scene. Visual review of heldout overlays confirms accurate tower anchors and missed troop/Tesla bodies; no tuning followed heldout inspection. Rechecked IPv4/IPv6 app-UID rejection rules and stopped owned benchmark emulator PID 5775. Stop receipt saved. Final RESULTS.md and artifact verification remain.

Final semantic integration fix: VisionEntity uses body names Archer/IceGolemite/IceSpirits, while HUD and play events retain action names Archers/IceGolem/IceSpirit. Model weights, thresholds and tracking behavior are unchanged. Rerunning all 171 frames produced exactly identical values after this three-name normalization; every quality metric and contract gate is unchanged. Final artifacts are inference-final/ and evaluation-final/. 34 tests now pass. The emulator-off rerun measured 39.902 FPS, p99 40.817 ms; the earlier 22.679 FPS run overlapped emulator startup. A final capture benchmark with the corrected output names is underway on owned emulator PID 16439, again with isolated and attested startup.

Final verification complete: body-name-corrected inference/evaluation preserves all quality metrics exactly. 34 tests pass. Canonical CLI independently reproduces failed gates. Final capture benchmark exited 0: PNG 0.522 FPS, raw 1.607 FPS, versus >=10 target. Final emulator PID 16439 stopped after firewall recheck; all owned emulator instances and long L1 jobs are stopped. Final startup required one same-app restart after SIGSEGV; no probe/APK change. RESULTS.md contains the full measurements, label limits, failed gates and L2 gaps.

## v1 implementation, 2026-10-04

Read all requested rules and v0 evidence. Scope remains vision, L1 scripts/tests and L1 reports. Foreign C56 PID 15128 and all protected paths are untouched. Free disk 16 GiB, swap 4.37 GiB; no emulators at preflight. One read-only 3072 MiB / 2-core emulator planned. PyAV 19.0.1 installed in the existing venv for an in-memory H.264 decoder. Raw video will not be saved. V0 pairing has no compositor fence, so v1 will distinguish paused state pairing from exact rendered tick certification.

v1 streaming smoke: owned launcher PID 30394 exited successfully, emulator PID 30399 / emulator-5580 / probe 26789 is attested and firewalled. In-memory adb H.264/PyAV latest-frame stream delivered 40 frames in 1.382 s = 28.935 FPS; this is transport smoke only, not moving-match acceptance or render-tick latency. Collector smoke uses seed 261005000 and 30 frames with variable 2/4/6/8-tick steps; all body labels are explicitly uncertain, with overlap/retraction reasons. No raw captures saved.

2026-10-04 13:03:32: Collected l1-261005000 train: 30 paired JPEGs, 10 accepted plays; dataset JPEG bytes 3229384.

v1 H.264 freshness failure: final smoke label tick 344 expected public clock 163 s, stream showed 164 s, and a fresh raw screenshot showed 163 s. The 30-frame smoke is excluded from training/scoring despite its paused-state receipt audit. Switched to the installed emulator SDK gRPC screenshot protocol. Initial gRPC smoke was 45.09 FPS, timestamp-to-receipt mean 29.33 ms / max 55.88 ms, not tick-to-frame latency. Unauthenticated gRPC instance was stopped and replaced with a loopback-only, token-authenticated endpoint; owned PID 36895. SDK-generated protobuf bindings are in v1/grpc. Collector freshness smoke now runs on that instance.

2026-10-04 13:09:13: Collected l1-261005001 train: 40 paired JPEGs, 6 accepted plays; dataset JPEG bytes 4219701.

gRPC freshness smoke passed 40/40 public clock comparisons at variable ticks. Final paused streamed clock and independent raw screencap agree at 160 s. Mean capture wait 50.47 ms, excluding pause/step. Started full v1 collector on owned emulator PID 36895: 40 seeds beginning 261005100, 300 frames per match, four placement styles, 2/4/6/8-tick variable steps. Existing v0 decks are excluded from the new population, and each new deck appears in one split only. Collection checks the visible clock on every accepted frame. Exact compositor tick and sprite visibility remain uncertified, explicitly recorded.

2026-10-04 13:12:31: Collected l1-261005100 train: 300 paired JPEGs, 27 accepted plays; dataset JPEG bytes 30560056.

2026-10-04 13:14:36: Collected l1-261005101 train: 300 paired JPEGs, 29 accepted plays; dataset JPEG bytes 61024081.

2026-10-04 13:17:07: Collected l1-261005102 train: 300 paired JPEGs, 26 accepted plays; dataset JPEG bytes 92345629.

v1 parallel collection: primary collector PID 40313 and emulator PID 36895 remain owned. Second read-only emulator PID 44319 uses serial emulator-5582, probe 26790, authenticated loopback gRPC 8556, 3072 MiB / 2 cores. Second collector PID 46417 writes dataset-second2, seeds 261005200..219, excluding every deck in the first population. A discovery-filename typo made PID 46144 exit before saving frames; its empty dataset-second is excluded. Plan: retain the first 20 completed primary episodes, stop only primary collector after that boundary, merge with all 20 secondary episodes for up to 12k frames. Preserve both shards and audit the merged seed/deck split. No third emulator. HP train-only truth-position diagnostic: 603/1038 readings, coverage 58.09%, MAE .05583. Sixteen focused tests pass.

Collection intro correction: both earlier collectors stopped before admitting hidden-HUD labels. Primary retained three completed episodes / 900 frames; secondary had zero frames. Resumed only at completed-episode boundaries with bounded additional 1x warmup until a visible, correctly read clock is present. Owned collectors now 48836 and 48842, detached pipeline PID 50482. Both are producing frames. Forty focused L1 and existing contract/privacy tests pass. Pipeline will retain 20 primary + 20 secondary episodes, audit, benchmark continuous 1x capture, stop both owned emulators, then train at 640 pixels with JPEG/blur/colour augmentation for six epochs from the local v0 checkpoint. The new population excludes every v0 deck. Frozen prior is v1/public-deck-prior.json; no per-episode deck assignment enters inference.

2026-10-04 13:22:46: Collected l1-261005103 train: 300 paired JPEGs, 31 accepted plays; dataset JPEG bytes 123118144.

2026-10-04 13:22:55: Collected l1-261005200 train: 300 paired JPEGs, 33 accepted plays; dataset JPEG bytes 30690007.

HP diagnostic breakdown saved in v1/hp-training-diagnostic.json. Full-arena level-marker matching cost 73.9 ms/frame while both emulators ran; restricted searches to predicted body neighborhoods and retained one-to-one association to avoid assigning one bar to multiple units. Healthy HP is emitted only when a visible centered level marker has no adjoining bar; missing or ambiguous markers remain unknown. This is a renderer-specific visual cue, not unconditional full-HP imputation. Swarms remain the weakest association case.

2026-10-04 13:26:15: Collected l1-261005201 train: 300 paired JPEGs, 24 accepted plays; dataset JPEG bytes 61369898.

2026-10-04 13:26:17: Collected l1-261005104 train: 300 paired JPEGs, 28 accepted plays; dataset JPEG bytes 153763620.

HP ROI optimization reproduced all 603 readings and .05583 MAE exactly on the 238 v0 training frames, reducing diagnostic cost to 3.91 ms/frame. Own HUD play cues now require a unique hand change plus visible elixir spend, or a confident next-card refill; own births retained briefly for placement association. No placement is invented for HUD-only spell events. Derived-state time uses perceived clock intervals and public media-time deltas, preserving the read-only upstream module. Forty tests still pass. V1 HUD templates will be sampled across stable training hand windows and capped per value to bound memory and avoid a template bank dominated by one dense episode.

2026-10-04 13:29:28: Collected l1-261005202 train: 300 paired JPEGs, 29 accepted plays; dataset JPEG bytes 92126948.

2026-10-04 13:29:41: Collected l1-261005105 train: 300 paired JPEGs, 34 accepted plays; dataset JPEG bytes 184772788.

V1 inference plumbing smoke completed on 40 training frames with the v0 checkpoint at 640 pixels. The new HP/tracking/event output passed PublicVisionFrame serialization and measured 17.10 FPS, p95 107.04 ms while both emulators ran. This is not heldout v1 evidence. Collection exceeds 3,000 accepted frames; disk 16 GiB free, swap 3.51 GiB. No foreign jobs were signalled.

2026-10-04 13:32:42: Collected l1-261005203 train: 300 paired JPEGs, 24 accepted plays; dataset JPEG bytes 122980048.

2026-10-04 13:32:48: Collected l1-261005106 train: 300 paired JPEGs, 32 accepted plays; dataset JPEG bytes 215855230.

2026-10-04 13:35:48: Collected l1-261005204 train: 300 paired JPEGs, 31 accepted plays; dataset JPEG bytes 153528221.

2026-10-04 13:35:56: Collected l1-261005107 train: 300 paired JPEGs, 30 accepted plays; dataset JPEG bytes 246073172.

Before capture reaches those episodes, froze an expanded heldout split in v1/collection-plan.json: secondary seeds 261005216..219 are heldout, covering all four placement styles; 261005214..215 are validation. All other selected episodes are training. The merger applies this frozen split to labels, episodes and manifest consistently; training only opens the merged split. No model or threshold was selected on those future images. Restarted only the owned waiting pipeline PID 50482 to apply this policy and add the report-writing stage; collectors/emulators were not interrupted.

Source review confirms the native probe has scene load/tick counters but no compositor tick fence. Its rich visibility runtime reports owner-relative public visibility unavailable, and it cannot certify sprite occlusion. Kept those labels uncertain. A v0-training-only 640-pixel, batch-16, one-epoch smoke is testing memory and throughput before selecting the full-run batch size. It is not v1 heldout evidence. Four-style heldout and two validation episodes remain uncollected and uninspected.

2026-10-04 13:39:06: Collected l1-261005205 train: 300 paired JPEGs, 34 accepted plays; dataset JPEG bytes 184202842.

2026-10-04 13:39:16: Collected l1-261005108 train: 300 paired JPEGs, 25 accepted plays; dataset JPEG bytes 276757230.

Validation fix is local to src/clasher/vision/l1_training.py; vendor files are untouched. It copies predictions once to CPU for NMS and removes the validator time cutoff, then returns boxes to the original device. The corrected batch-16 smoke completed and scored all 86 v0 validation frames without an NMS timeout. Its 16-second training epoch is throughput evidence only; v1 acceptance remains pending. Comparing batch 8 at the same 640-pixel input before finalizing the main batch. Current collection is near 5,000 frames.

2026-10-04 13:42:30: Collected l1-261005206 train: 300 paired JPEGs, 28 accepted plays; dataset JPEG bytes 215030723.

2026-10-04 13:42:40: Collected l1-261005109 train: 300 paired JPEGs, 32 accepted plays; dataset JPEG bytes 307128472.

Selected batch 16 for the full 640-pixel run: matched v0 training smokes took 16 s/epoch at batch 16 versus 25 s at batch 8. Both corrected validation runs completed without skipped NMS samples. Selection evidence is v1/batch-selection.json; TOML updated. Restarted only the owned waiting pipeline PID 65683 so the full run uses the selected batch. Disk is now 14 GiB free; swap 4.92 GiB after MPS smoke allocation, below the user limit. Both emulators will stop before full training. Collection exceeds 5,200 frames.

2026-10-04 13:45:35: Collected l1-261005207 train: 300 paired JPEGs, 33 accepted plays; dataset JPEG bytes 246055137.

2026-10-04 13:45:41: Collected l1-261005110 train: 300 paired JPEGs, 29 accepted plays; dataset JPEG bytes 338319500.

2026-10-04 13:47:21: Collected l1-261005111 train: 148 paired JPEGs, 15 accepted plays; dataset JPEG bytes 353854271.

2026-10-04 13:48:31: Collected l1-261005208 train: 300 paired JPEGs, 26 accepted plays; dataset JPEG bytes 276777667.

2026-10-04 13:50:43: Collected l1-261005112 train: 300 paired JPEGs, 24 accepted plays; dataset JPEG bytes 384714999.

HP thresholds frozen before v1 heldout capture: marker .58, healthy marker .68, horizontal tolerance 6 pixels. Truth-position diagnostics: v0 validation 259/380 readings = 68.16% coverage, MAE .06152; 120 evenly sampled v1 training frames across four styles 365/552 = 66.12%, MAE .05942. These exclude detector errors and are not acceptance. Candidate sweeps and selection evidence are saved under v1/hp-*.json. A wider horizontal tolerance offered little benefit and was not selected.

2026-10-04 13:52:20: Collected l1-261005209 train: 300 paired JPEGs, 30 accepted plays; dataset JPEG bytes 307108387.

Resource housekeeping removed 95.61 MB of this run's reproducible smoke-training image copies only; source datasets, logs, manifests, and model checkpoints remain. Cleanup receipt: v1/smoke-cache-cleanup.json. Full-run training images will live in v1/model-data, separate from model weights. Capture benchmark now targets six ten-second 1x segments with repeated deployments, with short controller pauses between segments; screenshot transport latency is still distinguished from unavailable render-tick latency. Current pipeline PID is 73610; ownership is recorded in v1/runtime.json.

2026-10-04 13:54:29: Collected l1-261005113 train: 300 paired JPEGs, 25 accepted plays; dataset JPEG bytes 414828573.

2026-10-04 13:55:47: Collected l1-261005210 train: 300 paired JPEGs, 32 accepted plays; dataset JPEG bytes 338355751.

2026-10-04 13:58:02: Collected l1-261005114 train: 300 paired JPEGs, 34 accepted plays; dataset JPEG bytes 445818920.

2026-10-04 13:59:15: Collected l1-261005211 train: 300 paired JPEGs, 32 accepted plays; dataset JPEG bytes 369105041.

2026-10-04 14:01:19: Collected l1-261005115 train: 300 paired JPEGs, 20 accepted plays; dataset JPEG bytes 476250548.

Training-label audit found 36 transient empty own-hand slots in the first 4,669 frames. Added a regression to ensure an empty-slot refill is never emitted as a played card; spend-plus-hand-change still identifies the preceding real card. No v1 heldout predictions or metrics have been inspected.

2026-10-04 14:02:29: Collected l1-261005212 train: 300 paired JPEGs, 28 accepted plays; dataset JPEG bytes 399943404.

2026-10-04 14:04:34: Collected l1-261005116 train: 300 paired JPEGs, 27 accepted plays; dataset JPEG bytes 506583408.

2026-10-04 14:05:54: Collected l1-261005213 train: 300 paired JPEGs, 28 accepted plays; dataset JPEG bytes 430590714.

2026-10-04 14:07:46: Collected l1-261005117 train: 300 paired JPEGs, 29 accepted plays; dataset JPEG bytes 537012152.

2026-10-04 14:09:14: Collected l1-261005214 train: 300 paired JPEGs, 28 accepted plays; dataset JPEG bytes 461845073.

2026-10-04 14:10:38: Collected l1-261005118 train: 246 paired JPEGs, 18 accepted plays; dataset JPEG bytes 562354042.

2026-10-04 14:12:52: Collected l1-261005215 train: 300 paired JPEGs, 32 accepted plays; dataset JPEG bytes 492667110.

Early benchmark controller PID 11731 is detached and waiting up to four minutes for the primary completion receipt. It temporarily SIGSTOPs only owned waiting pipeline PID 73610, runs the primary stream benchmark, stops owned emulator PID 36895 after firewall recheck, then SIGCONTs the pipeline in a finally block. Do not duplicate/resume that pipeline while the controller is active. Secondary collector PID 48842 and emulator PID 44319 continue untouched. Stage completion receipts prevent a second benchmark.

2026-10-04 14:14:10: Collected l1-261005119 train: 300 paired JPEGs, 24 accepted plays; dataset JPEG bytes 593041345.

2026-10-04 14:14:12: v1 Temporarily suspended the owned waiting pipeline for an early primary stream benchmark; secondary collection continues.

2026-10-04 14:14:12: v1 Starting stream-benchmark

2026-10-04 14:15:43: v1 Completed stream-benchmark

2026-10-04 14:15:44: v1 Stopped owned emulator-5580, PID 36895

2026-10-04 14:15:44: v1 Resumed owned pipeline after early benchmark. Existing stage receipt prevents duplicate benchmark work.

2026-10-04 14:16:10: Collected l1-261005216 train: 300 paired JPEGs, 25 accepted plays; dataset JPEG bytes 523559929.

Continuous active-scene stream benchmark completed: 828 frames / 75.773 s = 10.914 FPS, screenshot-production-to-sanitized-receipt mean 66.426 ms, p95 122.375 ms, p99 141.652 ms. Two owned emulators were active at benchmark start. Native stepping ran at configured 1x in six ten-second tick segments with repeated deployments. Screenshot timestamps still do not certify game render ticks, so the requested render-tick latency gate remains unverified. Emulator PID 36895 was stopped after firewall recheck; its stop receipt is saved. Pipeline PID 73610 resumed normally; only emulator PID 44319 and collector PID 48842 remain active. Disk recovered to 15 GiB; swap 3.59 GiB.

2026-10-04 14:17:57: Collected l1-261005217 validation: 300 paired JPEGs, 33 accepted plays; dataset JPEG bytes 554031677.

2026-10-04 14:19:42: Collected l1-261005218 heldout: 300 paired JPEGs, 34 accepted plays; dataset JPEG bytes 585378482.

Three predeclared heldout episodes are complete; the final secondary episode is collecting. Original shard log split names are provisional; v1/collection-plan.json froze final roles before these episodes were captured, and the merger applies them to every row and manifest entry. Only the merged split is used for training/HUD fitting. Forty-one focused and existing contract/privacy tests passed after the empty-slot event fix. No v1 heldout quality metrics have been inspected or used for tuning.

2026-10-04 14:21:56: Collected l1-261005219 heldout: 300 paired JPEGs, 35 accepted plays; dataset JPEG bytes 616378639.

2026-10-04 14:22:04: v1 Merged 11794 frames from 40 episodes using hardlinks; no duplicated JPEG bytes

2026-10-04 14:22:04: v1 Starting audit

2026-10-04 14:22:30: v1 Completed audit

2026-10-04 14:22:30: v1 Stopped owned emulator-5582, PID 44319

2026-10-04 14:22:35: v1 Starting train

Data audit passed all 11,794 JPEG hashes and paused-state/visible-clock receipts. JPEG bytes 1,209,419,984; 40 distinct seeds, 80 distinct decks. Final split 9,994 train / 600 validation / 1,200 heldout. All 123,016 entity labels explicitly retain uncertain pixel visibility. Both owned emulators are stopped with firewall/stop receipts; no collector remains. MPS trainer PID 26814 is active under pipeline PID 73610, 640 pixels / batch 16 / six epochs. Epoch 1 is in progress. Disk 14 GiB free, swap 3.44 GiB.

Epoch 1/6 completed: validation weak-box precision .81446, recall .77627, mAP50 .81609, mAP50-95 .56778. These are validation diagnostics, not heldout gates. Epoch 2 is running. Physical L1 storage, counting hardlinks once, is 2.035 GiB nonmodel data and .133 GiB models. Both stay below the 3/1 GiB limits.

2026-10-04 14:37:42: v1 Pipeline stopped: train exited -15; see train.log

2026-10-04 14:40:07: v1 Resuming from the completed epoch-1 checkpoint at batch 8 with bounded MPS memory and cache cleanup.

Resource intervention: host free disk fell to 6.7 GiB and swap reached 9.6 GiB during epoch 2. Paused then stopped only owned trainer PID 26814; its pipeline PID 73610 exited on the expected -15 result. Verified last.pt is completed epoch 1 with optimizer state and preserved it as checkpoint-epoch1.pt, SHA-256 ed0eae39607e1faf76b4344f4e2ecc6a7e497551fa052b40c110de9a7baf3966. The partial epoch 2 is discarded, not counted complete. New detached wrapper PID 58474 owns resumed trainer PID 58477. Resume uses batch 8, MPS allocator ratios .4/.25, cache cleanup and telemetry every 25 batches; old producer archives are retained with -initial names. Driver memory dropped from 2.81 GB to 1.70 GB after cleanup; disk recovered to 12 GiB, swap 4.7 GiB. Resume continues epochs 2 through 6 in the original detector directory, then the wrapper completes inference/evaluation/report stages. No foreign processes were touched.

Epoch 2 completed with validation precision .86819, recall .84172, mAP50 .85641, mAP50-95 .63171. Preserved its resumable checkpoint as checkpoint-epoch2.pt. Validation still increased host pressure despite cache cleanup, so all variable-sized validation matching/statistics now stay on CPU; the MPS device is restored afterward. A new MPS-to-CPU metrics regression passes against the CPU reference; 42 tests pass. Stopped only owned resumed trainer PID 58477 after verifying the epoch-2 checkpoint; the small partial epoch 3 is discarded. New wrapper PID 58474 owns trainer PID 58477, continuing epochs 3 through 6. Prior resume log, manifest and source snapshot are retained. Upstream derived-state loading now explicitly avoids bytecode writes to the protected srp-public directory.

Correction to the immediately preceding ownership update: it read the stale first-resume PID receipt. The intended second-resume launch PID 5397 disappeared before writing startup output, and no training process remained. No cause is established. Retained its empty log, archived the stale receipt, and relaunching the same authorized continuation with an exit-status wrapper. Completed epoch-2 checkpoint and data remain intact.

2026-10-04 14:56:29: v1 Resuming the latest completed checkpoint at batch 8 with CPU validation metrics and bounded MPS memory.

Second continuation verified running: exit-status shell wrapper PID 10467, Python pipeline wrapper PID 10471, trainer PID 10472. Fresh resume-process.json confirms startup; the log uses the original model/detector directory. The vanished earlier launch performed no training. Final source and PID records now reflect the active continuation.

Epoch 3 completed after the CPU metric change: validation precision .87079, recall .87706, mAP50 .88393, mAP50-95 .66379. Full validation completed without NMS skips. Epoch 4 is active. Training-memory cleanup and global resource guards remain enabled; no heldout predictions or quality metrics have been opened.

Epoch 4 completed: validation precision .90349, recall .89668, mAP50 .89620, mAP50-95 .67967. CPU validation completed all 600 frames in about 20 seconds. Epoch 5 is active. Free disk briefly approached the 4 GiB process guard but recovered above 6 GiB; no guard failure or additional restart occurred. No heldout metrics have been computed.

2026-10-04 15:25:46: v1 Fresh-process training attempt 0, owned trainer PID 71546.

The process resource guard stopped the incomplete fifth epoch when free disk reached 3.324 GiB. Epoch 4 remains the last completed checkpoint; its validation result is preserved. Stopping the owned trainer recovered about 10 GiB free disk. Added an optional one-epoch resume mode that exits with code 75 only after the library has saved a full epoch checkpoint, preserving optimizer state. A bounded continuation starts a fresh MPS process for each remaining epoch, waits for >=8 GiB free disk before launching, and marks training complete only on the normal final-epoch exit. This avoids carrying GPU caches across epochs. The interrupted epoch-5 log and failure receipt are retained; no foreign jobs or files were changed.

Final fairness review before heldout inference removed the derived-state media-time interpolation. Sample timestamps come from the native stepping timeline; they remain media/association metadata, but must not supply extra clock precision to opponent resource inference. Derived state now uses only perceived plays and the perceived clock midpoint, as in v0. Native labels/ticks are used only for post-inference scoring. This change was made before any v1 heldout prediction or metric was inspected.

2026-10-04 15:34:47: v1 Completed epoch 5; released its MPS process before the next epoch.

2026-10-04 15:34:52: v1 Fresh-process training attempt 1, owned trainer PID 89618.

Epoch 5 completed and its worker exited with the intentional checkpoint-ready code 75. Validation precision .88214, recall .89568, mAP50 .89897, mAP50-95 .69635. A fresh owned trainer PID 89618 is running epoch 6 under wrapper PID 71542. Added an evaluation-only true-event reference to measure when the opponent hand is actually determined; abstentions/collapses count as misses on that reference-determined set. This oracle never feeds or repairs predictions. No v1 heldout predictions or metrics have been inspected.

2026-10-04 15:44:20: v1 Starting infer

2026-10-04 15:45:13: v1 Completed infer

2026-10-04 15:45:13: v1 Starting evaluate

2026-10-04 15:45:17: v1 Completed evaluate

2026-10-04 15:45:17: v1 Starting report

2026-10-04 15:45:17: v1 Completed report

2026-10-04 15:45:17: v1 Collection, audit, training, inference, evaluation, stream benchmark and RESULTS-v1.md completed. Final verification still required.

Final verification complete. Six full epochs finished; selected validation checkpoint SHA-256 8b6fde6fc402e2b075cdd9e5a92a9486eb738b0428912b7c1975aa12491748a5. All 1,200 heldout predictions are frozen. Entity within-one-tile coverage 96.95% overall / 93.75% non-tower; HP 66.06% all-body coverage at .0498 MAE, with visibility certification still absent. Events: 90/127 timely correct-card matches, 93 false positives; 75/127 placements within one tile. Own hand 99.69%, displayed elixir 97.08%, clock MAE 0. Derived elixir MAE 2.67785 at 11.58% coverage; hand 0% on 633 reference-determined frames, with all four posteriors collapsing. True-event reference gives .0129 elixir MAE and 100% determined-hand accuracy. Perception 24.85 FPS; stream 10.91 FPS / screenshot-transport p95 122.37 ms; exact render-tick latency uncertified. All 42 tests pass. Canonical CLI exactly reproduces exported contract metrics and failed gates; prediction/input/source hashes pass. Four fixed heldout images inspected without tuning; Tesla has no heldout body support. No owned emulator or long-running L1 job remains. RESULTS-v1.md records failed/unverified gates and NOT READY for L2.

2026-10-04 15:56:13: v2 preflight read all required guidance and v1 evidence. Existing live-loop occupies 2.3 GiB; disk free 18 GiB. V2 will use a separate directory with a 1.5 GiB data ceiling and 4 GiB total ceiling, one owned 3072 MiB / 2-core offline emulator. No foreign process or protected source changes. Launch uses the existing firewall/attestation path and detach.sh. Exact single-tick capture validity will be tested before collection; v1 has no compositor fence.

2026-10-04 16:00:35: v2 diagnostic frame limit reached: l1v2-261006100, 37 frames. Not a completed dataset.

2026-10-04 16:01:25: v2 single-tick smoke completed 37 frames, HogRider opponent and Archers own events, visual deploy clocks and spawns inspected. Native step/capture observations agree, but paused presentation animates markers and has no compositor fence. Warmup extended from visible-clock readiness to tick 340 to clear FIGHT overlay. Frozen main plan: 4 train / 2 validation / 2 heldout matches, complementary P16 decks in each split, no prior L1 deck overlap. Owned collector wrapper PID 15993 started via detach.sh. Smoke is diagnostic and excluded from fitting/scoring. A separate continuous-stream test is required for realistic timing.

2026-10-04 16:04:08: v2 collected l1v2-261006100 train: 592 frames, 19 accepted events, 51983768 image bytes.

2026-10-04 16:07:14: v2 collected l1v2-261006101 train: 592 frames, 21 accepted events, 105416565 image bytes.

2026-10-04 16:08:16: v2 implementation added causal three-frame EventNet, visible deploy-clock detector and v1/HUD fusion. Training script excludes heldout and balances positive/negative temporal stacks. Copied the exact public-state reference without writing to srp-public; robust adapter now retains accept/skip hypotheses, checks affordability and attempts one-missed-play recovery on contradictions. No v2 quality claims yet. First two training matches complete, 1,184 frames and 40 events; no raw captures retained.

2026-10-04 16:10:13: v2 collected l1v2-261006102 train: 592 frames, 19 accepted events, 157829378 image bytes.

2026-10-04 16:13:45: v2 collected l1v2-261006103 train: 592 frames, 23 accepted events, 210342789 image bytes.

2026-10-04 16:13:46: v2 restarted owned collector after four completed training matches; no partial episode or action replay. Acceptance tolerance now covers six ticks of double/triple elixir regeneration.

2026-10-04 16:13:46: v2 starting train-events

2026-10-04 16:17:08: v2 collected l1v2-261006104 validation: 592 frames, 23 accepted events, 270137136 image bytes.

2026-10-04 16:20:48: v2 collected l1v2-261006105 validation: 592 frames, 20 accepted events, 321921386 image bytes.

2026-10-04 16:21:55: v2 train split complete: 2,368 frames, 82 events, all 32 P16 side/card combinations. Validation complete: 1,184 frames and 43 events. Temporal model at epoch 19/24, bounded MPS fit. Pixel clock offsets fitted on training only. Added conservative continuous-stream replay scoring: predicted time must follow the event upper bound and remain within 500 ms of its lower bound. Public derivation now reads visible-clock intervals plus relative media time, not native/frame-ID ticks. New continuous wrapper PID 28162 waits for stepped capture, replays heldout commands without fitting, then stops the owned emulator.

2026-10-04 16:23:04: v2 temporal fit completed 24 epochs on 4 training episodes; no heldout fitting.

2026-10-04 16:23:04: v2 finished train-events

2026-10-04 16:23:04: v2 starting sample-validation

2026-10-04 16:23:07: v2 finished sample-validation

2026-10-04 16:23:07: v2 starting infer-validation

2026-10-04 16:24:22: v2 pixel inference frozen: inference-validation, 608 frames, 8.87 FPS excluding capture.

2026-10-04 16:24:23: v2 finished infer-validation

2026-10-04 16:24:23: v2 starting select-validation

2026-10-04 16:24:34: v2 validation selected event threshold 0.5, marker 0.8; F1 0.816.

2026-10-04 16:24:34: v2 finished select-validation

2026-10-04 16:27:51: v2 pixel inference frozen: inference-validation, 608 frames, 9.01 FPS excluding capture.

2026-10-04 16:27:59: v2 first validation result was 31/43 correct timely plays, 2 false positives, 27/43 placements. Validation revealed own spells incorrectly associated with unrelated deploy clocks. Preserved the first predictions/selection under *-initial. Corrected fusion to exclude spell-clock association, retain own-HUD spells with unknown placement when no strong spatial cue exists, and corroborate weak temporal/clock detections with v1 births. Refitting no weights; rerunning validation only before heldout inference. Inference measured 8.87 FPS with the emulator active, below the v1 throughput, and remains a readiness concern.

2026-10-04 16:28:01: v2 validation selected event threshold 0.5, marker 0.8; F1 0.916.

2026-10-04 16:31:59: v2 collected l1v2-261006106 heldout: 2261 frames, 36 accepted events, 520152534 image bytes.

2026-10-04 16:32:36: v2 revised validation: 38/43 timely correct-card plays, 2 false positives, 30/43 placements. Selected threshold remains .5/.8. Froze weights, clock offsets, thresholds and inference/evaluation source hashes before any heldout prediction. Validation inference 9.01 FPS with emulator active. Runtime denied-read check succeeds on four frames: zero private input reads; three Ultralytics connectivity probes were blocked, zero successful connections. Eight new regression tests pass, including unrelated-clock rejection for own spells.

2026-10-04 16:35:22: Manually reviewed 29 spell-event sequences across completed matches at offsets +1, +3, +9 and +20 ticks. Saved per-event cue labels and contact sheets. Zap flash/area, falling/rolling Log and airborne Fireball are visually distinct; some opponent projectiles appear late in the inspected samples. Cues from unrelated simultaneous troop clocks are explicitly excluded. This annotation review followed inference freezing and caused no model/threshold change.

2026-10-04 16:36:53: Manually reviewed 132 troop/building deployment crops from the first seven matches at +3/+7 ticks. Recorded unit-spawn and clock presence per event; one overlapping Skeletons spawn remains uncertain and three clocks were not observed in the selected samples. Combined with 29 spell reviews, this covers every event in those seven matches. Final heldout-match annotations will follow collection. The review records positive evidence, not exact onset or exhaustive per-frame visibility.

2026-10-04 16:43:44: v2 collected l1v2-261006107 heldout: 2261 frames, 39 accepted events, 719442038 image bytes.

2026-10-04 16:43:44: v2 starting sample-heldout-10

2026-10-04 16:43:46: v2 finished sample-heldout-10

2026-10-04 16:43:46: v2 starting infer-heldout-10

2026-10-04 16:43:48: v2 starting collect-stream

2026-10-04 16:45:11: Stepped collection completed: 8,074 frames, 200 accepted deployments, all eight planned matches. Final-match review adds 29 troop/building and 10 spell events; all 200 events now have manual cue samples. Two body-presence cases remain uncertain due to overlap. Captured JPEGs total 719,442,038 bytes; dataset including metadata 735,220,814 bytes. Heldout inference at 10 FPS and continuous 1x replay are active with frozen model/thresholds.

2026-10-04 16:46:13: v2 continuous pipeline stopped: collect-stream exited -15

2026-10-04 16:47:22: Continuous preflight found probe command serialization: observe calls blocked behind advance-native 200, producing only sparse screenshots. Stopped only owned stream collector PID 41356 and preserved its rejected data/logs. Revised capture runs step-1/observe in one worker and an independent gRPC screenshot consumer; execution times are bracketed by each native step request/response. This changes capture only, not model/fusion/thresholds. Native tick-to-pixel correspondence remains uncertified.

2026-10-04 16:47:22: v2 starting collect-stream

2026-10-04 16:47:49: v2 pixel inference frozen: inference-heldout-10, 2262 frames, 9.59 FPS excluding capture.

2026-10-04 16:47:50: v2 finished infer-heldout-10

2026-10-04 16:47:50: v2 starting evaluate-heldout-10

2026-10-04 16:48:28: v2 dataset audit: 8074 frames, 200 events, 4 pairing/split failures; missing card-sides {'train': [], 'validation': ['0:Giant', '0:Prince', '1:Giant'], 'heldout': []}.

2026-10-04 16:48:58: v2 heldout evaluation 10.0 FPS: event recall 0.853, precision 0.762, placement 0.653; gates {'events': False, 'placement': False, 'derived_elixir': False, 'derived_hand': False}.

2026-10-04 16:48:59: v2 finished evaluate-heldout-10

2026-10-04 16:48:59: v2 starting sample-heldout-10.9141

2026-10-04 16:49:01: v2 finished sample-heldout-10.9141

2026-10-04 16:49:01: v2 starting infer-heldout-10.9141

2026-10-04 16:52:01: v2 continuous stream l1v2-261006106: 3091 frames at 12.13 FPS; final hand/elixir replay parity True.

2026-10-04 16:53:25: v2 pixel inference frozen: inference-heldout-10.9141, 2468 frames, 9.55 FPS excluding capture.

2026-10-04 16:53:26: v2 finished infer-heldout-10.9141

2026-10-04 16:53:26: v2 starting evaluate-heldout-10.9141

2026-10-04 16:53:39: v2 heldout evaluation 10.9141 FPS: event recall 0.880, precision 0.776, placement 0.680; gates {'events': False, 'placement': False, 'derived_elixir': False, 'derived_hand': False}.

2026-10-04 16:53:40: v2 finished evaluate-heldout-10.9141

2026-10-04 16:53:40: v2 starting sample-heldout-20

2026-10-04 16:53:41: v2 finished sample-heldout-20

2026-10-04 16:53:41: v2 starting infer-heldout-20

2026-10-04 16:56:41: v2 continuous stream l1v2-261006107: 3196 frames at 12.43 FPS; final hand/elixir replay parity True.

2026-10-04 16:56:45: v2 starting recapture-tail

2026-10-04 16:56:56: v2 starting recapture-tail

2026-10-04 16:56:56: v2 continuous pipeline stopped: recapture-tail exited 1

2026-10-04 16:57:48: v2 independently recaptured 2 late deploy windows in l1v2-261006106: ticks 2580..2616. Frozen scored inputs unchanged.

2026-10-04 16:58:54: v2 independently recaptured 2 late deploy windows in l1v2-261006107: ticks 2580..2616. Frozen scored inputs unchanged.

2026-10-04 16:58:54: v2 starting continuous event-boundary replay; long native advances between commands avoid one-tick control overhead. JPEG quality 55 keeps total new data bounded.

2026-10-04 17:00:02: v2 diagnostic JPEG conversion: 6287 frames losslessly archived and every member hash verified before deleting its loose original; 555118636 -> 198899304 bytes.

2026-10-04 17:00:05: Four complete late-event windows independently recaptured, 74 supplemental frames, preserving scored inputs. Coordinator handoff raced with the original tail child startup: the second tail attempt correctly failed at mkdir before any native command. Original owned tail PID 48794 completed both windows and owns the sole active event-boundary collector PID 49685. No capture restart or duplicate game driver is being launched; a finisher waits for that exact collector before stopping the emulator. Both one-tick pacing replays reached tick 2600 with exact final opponent hand/elixir parity. Their JPEGs are being losslessly archived in verified small batches to bound new data.

2026-10-04 17:00:21: v2 dataset audit: 8074 frames, 200 events, 0 pairing/split failures; missing card-sides {'train': [], 'validation': ['0:Giant', '0:Prince', '1:Giant'], 'heldout': []}.

2026-10-04 17:01:18: v2 pixel inference frozen: inference-heldout-20, 4522 frames, 10.05 FPS excluding capture.

2026-10-04 17:01:18: v2 finished infer-heldout-20

2026-10-04 17:01:18: v2 starting evaluate-heldout-20

2026-10-04 17:01:40: v2 heldout evaluation 20.0 FPS: event recall 0.893, precision 0.728, placement 0.680; gates {'events': False, 'placement': False, 'derived_elixir': False, 'derived_hand': False}.

2026-10-04 17:01:40: v2 finished evaluate-heldout-20

2026-10-04 17:01:40: v2 stepped dataset, temporal fit, validation selection and three-cadence heldout evaluations completed. Continuous-stream confirmation and final audit still required.

2026-10-04 17:01:48: v2 continuous stream l1v2-261006106: 1530 frames at 10.25 FPS; final hand/elixir replay parity True.

2026-10-04 17:07:44: Event-boundary capture completed match 106, then its conservative byte estimate stopped match 107 near the end. Actual storage had already fallen after lossless archival; this was stale bookkeeping, not a cap breach. Preserved 1,530 completed frames and quarantined 1369 unscored partial frames. Fixed the guard to recheck current storage before stopping and added completed-episode resume. Only match 107 will be replayed; frozen model and scored stepped data remain unchanged.

2026-10-04 17:10:44: v2 continuous stream l1v2-261006107: 1539 frames at 10.06 FPS; final hand/elixir replay parity True.

2026-10-04 17:10:50: v1 Stopped owned emulator-5580, PID 12958

2026-10-04 17:10:50: v2 all owned captures complete; emulator stopped. Single-tick pacing data is an unscored diagnostic. Frozen event-boundary inference remains queued.

2026-10-04 17:10:52: v2 starting sample-fast-stream

2026-10-04 17:10:53: v2 finished sample-fast-stream

2026-10-04 17:10:53: v2 starting infer-fast-stream

2026-10-04 17:12:29: Both event-boundary matches completed at 10.25 and 10.06 FPS, with exact final opponent hand/elixir parity. The owned emulator stopped after firewall recheck. Initial stream inference rejected fractional millisecond media timestamps at the unchanged public contract before producing any prediction. Corrected manifest normalization to integer milliseconds, preserving raw receipts and failed manifest; model/inference sources/thresholds stay frozen. A regression now covers fractional stream timestamps.

2026-10-04 17:12:30: v2 starting sample-fast-stream

2026-10-04 17:12:31: v2 finished sample-fast-stream

2026-10-04 17:12:31: v2 starting infer-fast-stream

2026-10-04 17:14:57: v2 pixel inference frozen: inference-fast-stream, 2458 frames, 17.24 FPS excluding capture.

2026-10-04 17:14:58: v2 finished infer-fast-stream

2026-10-04 17:14:58: v2 starting evaluate-fast-stream

2026-10-04 17:14:59: v2 continuous event-boundary score: recall 0.213, precision 0.188, placement 0.213.

2026-10-04 17:15:00: v2 finished evaluate-fast-stream

2026-10-04 17:16:58: Cadence audit found that fixed-phase resampling dropped bursty arrivals: 2,458 selected frames averaged about 8.1 FPS despite the 10.9141 target. Preserved that diagnostic unchanged. The live-rate gate will now score all 3,069 captured frames, whose measured rates are 10.25 and 10.06 FPS. No model, fusion or threshold change; native-cadence manifest preparation only.

2026-10-04 17:19:39: v2 pixel inference frozen: inference-fast-stream, 3069 frames, 19.49 FPS excluding capture.

2026-10-04 17:19:42: v2 continuous event-boundary score: recall 0.240, precision 0.194, placement 0.240.

2026-10-04 17:24:16: v2 RESULTS-v2.md written with measured gates and NOT READY verdict. Final integrity and owned-process checks still required.

2026-10-04 17:29:16: v2 RESULTS-v2.md written with measured gates and NOT READY verdict. Final integrity and owned-process checks still required.

2026-10-04 17:29:16: Final v2 verification complete. 8,074 scored stepped frames + 74 full-window supplement frames; 200 deployments and 41 negative windows; all P16 side/card combinations in train and heldout. All 200 events manually reviewed at selected cue frames, with uncertainty retained. Native-rate stream: 3,069 frames at 10.25/10.06 FPS; conservative recall 24.00%, precision 19.35%, placement 24.00%; optimistic timing bounds still fail at 38.67%/31.18%. Stepped 10.9141-FPS recall 88.00%, precision 77.65%, placement 68.00%, derived elixir MAE 3.3211 and determined-hand accuracy 12.52%. New data 1.213 GiB; live-loop 3.477 GiB. All 52 tests and 22 integrity/resource checks pass. Frozen inference/model/threshold hashes and protected reference match. Owned emulator and known workers are stopped. RESULTS-v2.md records NOT READY for L2; deploy-event quality remains unresolved.

2026-10-04 17:32:39: v3 step 0: required reports/source inspected; design written before collection. Existing live-loop is about 3.6 GiB allocated, host free space 15 GiB. No running reference emulator found. Prior v2 evidence preserved; continuous timing certification is the first gate.

2026-10-04 17:36:05: v3 timing capture: 1417 frames, 80 seconds continuous resume at 1x; analysis pending.

2026-10-04 17:36:37: v3 timing analysis: native held-out p95 120.5 ms, clock interval residual p95 0.0 ms; empirical bound 241.7 ms. Exact per-frame compositor ticks remain uncertified.

2026-10-04 17:38:56: v3 timing capture: 801 frames, 80 seconds continuous resume at 1x; analysis pending.

2026-10-04 17:39:14: v3 timing analysis: native held-out p95 91.6 ms, clock interval residual p95 0.0 ms; empirical bound 140.9 ms. Exact per-frame compositor ticks remain uncertified.

2026-10-04 17:41:24: v3 timing analysis: native held-out p95 91.6 ms, clock interval residual p95 0.0 ms; empirical bound 140.9 ms. Exact per-frame compositor ticks remain uncertified.

2026-10-04 17:46:30: v3 mixed C56 pilot failed at tick 1302 after 14 accepted events: ordinary observe returned malformed JSON during continuous stepping. Partial H.264 and receipts preserved, excluded. Existing observe-atomic endpoint verified while paused; retry uses its consistent ordinary payload and fails on truncation. No probe modification. Added an uncalibrated sampleable public-event particle filter; tests and stream calibration pending.

2026-10-04 17:48:05: v3 stream l1v3-261007100: 21 accepted deployments, 750 frames at 8.32 FPS, 3384480 H.264 bytes; timing audit pending.

2026-10-04 17:50:21: v3 stream l1v3-261007100: 16 accepted deployments, 580 frames at 7.24 FPS, 2588950 H.264 bytes; timing audit pending.

2026-10-04 17:51:25: v3 stopped owned emulator-5582, PID 80206, after firewall verification.

2026-10-04 17:51:27: v3 stopped owned emulator-5580, PID 72696, after firewall verification.

2026-10-04 17:54:20: v3 stream l1v3-261007100: 23 accepted deployments, 770 frames at 9.62 FPS, 3573173 H.264 bytes; timing audit pending.

2026-10-04 17:54:36: v3 audit: 1 episodes, 23 accepted events; empirical timing only, certification pending.

2026-10-04 17:57:55: v3 stream l1v3-261007100: 60 accepted deployments, 1573 frames at 9.62 FPS, 8010454 H.264 bytes; timing audit pending.

2026-10-04 17:58:27: v3 cumulative-atomic collector stopped and preserved before training. Host pilot achieved 9.62 FPS and native local p95 45.1 ms, but a rich-response gap inflated a frame timing half-width to 681 ms. Installed probe rejects the newer cursor endpoint. Existing started/completed step counters support a checked ordinary-observation bracket without pausing; testing that capture path next.

2026-10-04 17:59:53: v3 stream l1v3-261007100: 23 accepted deployments, 780 frames at 9.75 FPS, 3642473 H.264 bytes; timing audit pending.

2026-10-04 18:00:12: v3 audit: 1 episodes, 23 accepted events; empirical timing only, certification pending.

2026-10-04 18:03:16: v3 stream l1v3-261007100: 60 accepted deployments, 1597 frames at 9.78 FPS, 8095248 H.264 bytes; timing audit pending.

2026-10-04 18:03:48: v3 shard 1 warmup exceeded the inherited 30-second RPC timeout before recording any frame. Preserved the empty episode directory. Warmup now advances in <=1000-tick chunks; continuous capture remains free-running at 1x. Shard 0 first match remains active and untouched.

2026-10-04 18:04:35: v3 counter-bracket host pilot: 780 frames at 9.746 FPS, 23 accepted C56/P16 deployments; global native residual p95 27.0 ms (0.54 ticks), local p95 30.5 ms, visible-clock midpoint p95 55.8 ms. Empirical frame half-width 140.3 ms, not yet a certified coverage guarantee. Two owned host-GPU collectors now use disjoint shards. All 15 v3 regression tests pass. Event fusion and video training/inference commands are implemented but untrained and unaccepted.

2026-10-04 18:04:48: v3 stream l1v3-261007102: 32 accepted deployments, 592 frames at 9.83 FPS, 3450888 H.264 bytes; timing audit pending.

2026-10-04 18:05:20: v3 stream l1v3-261007101: 30 accepted deployments, 592 frames at 9.83 FPS, 3340921 H.264 bytes; timing audit pending.

2026-10-04 18:06:21: v3 stream l1v3-261007104: 30 accepted deployments, 594 frames at 9.85 FPS, 3395334 H.264 bytes; timing audit pending.

2026-10-04 18:06:58: v3 stream l1v3-261007103: 28 accepted deployments, 644 frames at 9.81 FPS, 3608478 H.264 bytes; timing audit pending.

2026-10-04 18:08:03: v3 stream l1v3-261007106: 36 accepted deployments, 690 frames at 9.81 FPS, 4017363 H.264 bytes; timing audit pending.

2026-10-04 18:08:41: v3 stream l1v3-261007105: 38 accepted deployments, 699 frames at 9.82 FPS, 4038502 H.264 bytes; timing audit pending.

2026-10-04 18:10:23: v3 stream l1v3-261007108: 60 accepted deployments, 1058 frames at 9.80 FPS, 6590778 H.264 bytes; timing audit pending.

2026-10-04 18:10:42: v3 stream l1v3-261007107: 35 accepted deployments, 1121 frames at 9.80 FPS, 5811683 H.264 bytes; timing audit pending.

2026-10-04 18:11:09: v3 first seven completed matches contain 254 accepted deployments at 9.78-9.85 FPS. Many games finish near tick 3600, so the original 56 matches may not reach 3000. Froze 42 additional disjoint seed/deck matches with phase starts from 340 to 5200. Additional policy waits for underrepresented expensive cards rather than repeatedly spending on affordable cheap cards. All 56 card identities appear on both sides in each split of both plans. 33 focused v1/v2/v3 tests pass.

2026-10-04 18:11:55: v3 stream l1v3-261007110: 34 accepted deployments, 592 frames at 9.81 FPS, 3375226 H.264 bytes; timing audit pending.

2026-10-04 18:12:36: v3 stream l1v3-261007109: 40 accepted deployments, 800 frames at 9.80 FPS, 4547794 H.264 bytes; timing audit pending.

2026-10-04 18:13:26: v3 stream l1v3-261007112: 25 accepted deployments, 595 frames at 9.85 FPS, 3440538 H.264 bytes; timing audit pending.

2026-10-04 18:14:22: v3 stream l1v3-261007111: 37 accepted deployments, 731 frames at 9.79 FPS, 4188464 H.264 bytes; timing audit pending.

2026-10-04 18:15:31: v3 collection checkpoint: 13 completed matches, 485 accepted deployments. Before any model fit or heldout inspection, protocol 2 now records scheduled commands immediately and retains 700 ms of final video after native game end. Primary stream gates will use protocol-2 heldout matches; earlier protocol-1 data remain diagnostic/training by original split, with terminal windows censored. No v3 quality gate has been measured yet.

2026-10-04 18:15:54: v3 stream l1v3-261007113: 28 accepted deployments, 589 frames at 9.74 FPS, 3470223 H.264 bytes; timing audit pending.

2026-10-04 18:16:04: v3 stream l1v3-261007114: 52 accepted deployments, 1472 frames at 9.72 FPS, 7475627 H.264 bytes; timing audit pending.

2026-10-04 18:17:26: v3 stream l1v3-261007115: 31 accepted deployments, 589 frames at 9.81 FPS, 3508372 H.264 bytes; timing audit pending.

2026-10-04 18:18:20: v3 stream l1v3-261007116: 62 accepted deployments, 1000 frames at 9.69 FPS, 5935262 H.264 bytes; timing audit pending.

2026-10-04 18:18:58: v3 stream l1v3-261007117: 30 accepted deployments, 586 frames at 9.71 FPS, 3375772 H.264 bytes; timing audit pending.

2026-10-04 18:20:21: v3 stream l1v3-261007119: 24 accepted deployments, 490 frames at 9.61 FPS, 2923548 H.264 bytes; timing audit pending.

2026-10-04 18:21:34: v3 stream l1v3-261007118: 76 accepted deployments, 1553 frames at 9.55 FPS, 9149498 H.264 bytes; timing audit pending.

2026-10-04 18:23:06: v3 stream l1v3-261007120: 28 accepted deployments, 590 frames at 9.81 FPS, 3311895 H.264 bytes; timing audit pending.

2026-10-04 18:23:10: v3 stream l1v3-261007121: 53 accepted deployments, 1586 frames at 9.71 FPS, 8688330 H.264 bytes; timing audit pending.

2026-10-04 18:23:24: v3 ongoing capture: 22 complete matches, 869 accepted deployments, 18760 stream frames. Added validation-only per-card threshold selection and a validation residual distribution that affects both reported elixir spread and search samples. These are implemented paths, not measured acceptance results.

2026-10-04 18:23:38: v3 preserved empty warmup for l1v3-261007122; resuming the same frozen episode.

2026-10-04 18:24:38: v3 stream l1v3-261007123: 30 accepted deployments, 543 frames at 9.73 FPS, 3218194 H.264 bytes; timing audit pending.

2026-10-04 18:25:11: v3 stream l1v3-261007122: 26 accepted deployments, 595 frames at 9.79 FPS, 3454624 H.264 bytes; timing audit pending.

2026-10-04 18:26:16: v3 stream l1v3-261007125: 33 accepted deployments, 646 frames at 9.70 FPS, 3711432 H.264 bytes; timing audit pending.

2026-10-04 18:27:54: v3 stream l1v3-261007124: 53 accepted deployments, 1291 frames at 9.78 FPS, 7429393 H.264 bytes; timing audit pending.

2026-10-04 18:28:48: v3 stream l1v3-261007127: 56 accepted deployments, 1185 frames at 9.81 FPS, 6898134 H.264 bytes; timing audit pending.

2026-10-04 18:29:12: v3 stream l1v3-261007126: 18 accepted deployments, 455 frames at 9.81 FPS, 2621012 H.264 bytes; timing audit pending.

2026-10-04 18:30:20: v3 stream l1v3-261007129: 29 accepted deployments, 590 frames at 9.78 FPS, 3470401 H.264 bytes; timing audit pending.

2026-10-04 18:30:31: v3 stream l1v3-261007128: 14 accepted deployments, 709 frames at 9.72 FPS, 3436777 H.264 bytes; timing audit pending.

2026-10-04 18:31:51: v3 stream l1v3-261007130: 18 accepted deployments, 475 frames at 9.81 FPS, 2680795 H.264 bytes; timing audit pending.

2026-10-04 18:32:41: v3 stream l1v3-261007131: 50 accepted deployments, 1070 frames at 9.79 FPS, 6090406 H.264 bytes; timing audit pending.

2026-10-04 18:33:29: v3 stream l1v3-261007132: 29 accepted deployments, 658 frames at 9.80 FPS, 3622675 H.264 bytes; timing audit pending.

2026-10-04 18:34:12: v3 stream l1v3-261007133: 30 accepted deployments, 594 frames at 9.85 FPS, 3542052 H.264 bytes; timing audit pending.

2026-10-04 18:35:02: v3 stream l1v3-261007134: 30 accepted deployments, 600 frames at 9.84 FPS, 3604482 H.264 bytes; timing audit pending.

2026-10-04 18:36:35: v3 stream l1v3-261007136: 27 accepted deployments, 600 frames at 9.85 FPS, 3641876 H.264 bytes; timing audit pending.

2026-10-04 18:36:40: v3 capture checkpoint: 36 completed matches, 1312 accepted deployments. Corrected the audit interval calculation to include clock-edge displacement from the fitted lag, not just edge width. The earlier pilot half-width is superseded; exact per-frame timing certification remains open.

2026-10-04 18:37:02: v3 stream l1v3-261007135: 72 accepted deployments, 1599 frames at 9.79 FPS, 8773633 H.264 bytes; timing audit pending.

2026-10-04 18:38:08: v3 stream l1v3-261007138: 25 accepted deployments, 600 frames at 9.83 FPS, 3224143 H.264 bytes; timing audit pending.

2026-10-04 18:38:37: v3 stream l1v3-261007137: 30 accepted deployments, 621 frames at 9.78 FPS, 3427335 H.264 bytes; timing audit pending.

2026-10-04 18:40:03: v3 stream l1v3-261007140: 30 accepted deployments, 815 frames at 9.72 FPS, 4913225 H.264 bytes; timing audit pending.

2026-10-04 18:40:56: v3 stream l1v3-261007139: 56 accepted deployments, 1050 frames at 9.73 FPS, 6419548 H.264 bytes; timing audit pending.

2026-10-04 18:42:54: v3 stream l1v3-261007142: 52 accepted deployments, 1600 frames at 9.76 FPS, 8465260 H.264 bytes; timing audit pending.

2026-10-04 18:43:11: v3 stream l1v3-261007141: 51 accepted deployments, 1000 frames at 9.76 FPS, 5738807 H.264 bytes; timing audit pending.

2026-10-04 18:44:27: v3 stream l1v3-261007144: 28 accepted deployments, 600 frames at 9.85 FPS, 3378496 H.264 bytes; timing audit pending.

2026-10-04 18:45:13: v3 stream l1v3-261007143: 40 accepted deployments, 896 frames at 9.80 FPS, 5049702 H.264 bytes; timing audit pending.

2026-10-04 18:46:00: v3 stream l1v3-261007146: 26 accepted deployments, 600 frames at 9.84 FPS, 3406495 H.264 bytes; timing audit pending.

2026-10-04 18:46:45: v3 stream l1v3-261007145: 28 accepted deployments, 593 frames at 9.85 FPS, 3352605 H.264 bytes; timing audit pending.

2026-10-04 18:47:33: v3 stream l1v3-261007148: 25 accepted deployments, 600 frames at 9.85 FPS, 3386489 H.264 bytes; timing audit pending.

2026-10-04 18:48:18: v3 stream l1v3-261007147: 25 accepted deployments, 600 frames at 9.85 FPS, 3250053 H.264 bytes; timing audit pending.

2026-10-04 18:49:15: v3 stream l1v3-261007150: 27 accepted deployments, 695 frames at 9.82 FPS, 3756509 H.264 bytes; timing audit pending.

2026-10-04 18:50:47: v3 stream l1v3-261007152: 25 accepted deployments, 599 frames at 9.85 FPS, 3421952 H.264 bytes; timing audit pending.

2026-10-04 18:51:07: v3 stream l1v3-261007149: 56 accepted deployments, 1600 frames at 9.81 FPS, 8373482 H.264 bytes; timing audit pending.

2026-10-04 18:52:55: v3 stream l1v3-261007151: 32 accepted deployments, 748 frames at 9.77 FPS, 4521994 H.264 bytes; timing audit pending.

2026-10-04 18:52:56: v3 stream l1v3-261007154: 36 accepted deployments, 952 frames at 9.74 FPS, 5526146 H.264 bytes; timing audit pending.

2026-10-04 18:54:27: v3 stream l1v3-261007153: 32 accepted deployments, 592 frames at 9.80 FPS, 3494618 H.264 bytes; timing audit pending.

2026-10-04 18:54:48: v3 stream l1v3-261009136: 31 accepted deployments, 925 frames at 9.75 FPS, 4940766 H.264 bytes; timing audit pending.

2026-10-04 18:55:59: v3 stream l1v3-261007155: 36 accepted deployments, 592 frames at 9.80 FPS, 3532938 H.264 bytes; timing audit pending.

2026-10-04 18:56:24: v3 stream l1v3-261009138: 23 accepted deployments, 475 frames at 9.68 FPS, 2832222 H.264 bytes; timing audit pending.

2026-10-04 18:58:21: v3 stream l1v3-261009140: 31 accepted deployments, 539 frames at 9.66 FPS, 3459282 H.264 bytes; timing audit pending.

2026-10-04 18:58:50: v3 stream l1v3-261009135: 48 accepted deployments, 1582 frames at 9.65 FPS, 7891550 H.264 bytes; timing audit pending.

2026-10-04 19:00:22: v3 stream l1v3-261009137: 25 accepted deployments, 593 frames at 9.74 FPS, 3409355 H.264 bytes; timing audit pending.

2026-10-04 19:01:38: v3 extra shard 0 stopped because its long-lived gRPC stream stalled immediately after an encoder fork. Native renderer stayed awake and responsive; a fresh independent gRPC connection returned a valid frame immediately. Preserved the failed episode with zero video frames and six unscored deployments. Each new episode now opens gRPC after a posix_spawn encoder launch and closes it before subprocess-based verification. Resuming the exact frozen validation seed, with no completed episode replay.

2026-10-04 19:02:03: v3 stream l1v3-261009139: 15 accepted deployments, 444 frames at 9.67 FPS, 2575003 H.264 bytes; timing audit pending.

2026-10-04 19:03:45: v3 stream l1v3-261009141: 19 accepted deployments, 355 frames at 9.84 FPS, 2102758 H.264 bytes; timing audit pending.

2026-10-04 19:05:08: v3 stream l1v3-261009128: 66 accepted deployments, 1971 frames at 9.70 FPS, 10328880 H.264 bytes; timing audit pending.

2026-10-04 19:06:09: v3 capture checkpoint: 64 completed matches and 2302 accepted deployments. A 24-match protocol-2 metadata check found no executed command missing from event receipts and no pending command beyond a fixed cutoff. One end-of-game tail had 485 ms of actual receipt coverage despite the 700 ms target; full per-event windows will be audited. Future launches reserve two seconds before fixed cutoffs, pause at termination, and record actual trailing coverage.

2026-10-04 19:06:43: v3 stream l1v3-261009129: 55 accepted deployments, 1560 frames at 9.66 FPS, 8874223 H.264 bytes; timing audit pending.

2026-10-04 19:07:15: v3 stream l1v3-261009130: 34 accepted deployments, 933 frames at 9.74 FPS, 5937037 H.264 bytes; timing audit pending.

2026-10-04 19:08:14: v3 stream l1v3-261009131: 19 accepted deployments, 429 frames at 9.76 FPS, 2574746 H.264 bytes; timing audit pending.

2026-10-04 19:08:53: v3 stream l1v3-261009132: 16 accepted deployments, 434 frames at 9.78 FPS, 2523904 H.264 bytes; timing audit pending.

2026-10-04 19:09:59: v3 stream l1v3-261009133: 26 accepted deployments, 426 frames at 9.80 FPS, 2530516 H.264 bytes; timing audit pending.

2026-10-04 19:10:36: v3 stream l1v3-261009134: 22 accepted deployments, 355 frames at 9.86 FPS, 2073503 H.264 bytes; timing audit pending.

2026-10-04 19:12:16: v3 stream l1v3-261009101: 41 accepted deployments, 1185 frames at 9.80 FPS, 6522928 H.264 bytes; timing audit pending.

2026-10-04 19:13:32: v3 stream l1v3-261009100: 46 accepted deployments, 1656 frames at 9.76 FPS, 8002984 H.264 bytes; timing audit pending.

2026-10-04 19:13:45: v3 stream l1v3-261009103: 16 accepted deployments, 416 frames at 9.75 FPS, 2395125 H.264 bytes; timing audit pending.

2026-10-04 19:15:05: v3 stream l1v3-261009102: 24 accepted deployments, 600 frames at 9.84 FPS, 3397508 H.264 bytes; timing audit pending.

2026-10-04 19:15:15: v3 stream l1v3-261009105: 15 accepted deployments, 282 frames at 9.85 FPS, 1695811 H.264 bytes; timing audit pending.

2026-10-04 19:17:14: v3 stream l1v3-261009104: 41 accepted deployments, 737 frames at 9.78 FPS, 4572714 H.264 bytes; timing audit pending.

2026-10-04 19:18:05: v3 stream l1v3-261009107: 46 accepted deployments, 1600 frames at 9.78 FPS, 8503645 H.264 bytes; timing audit pending.

2026-10-04 19:18:57: v3 stream l1v3-261009106: 21 accepted deployments, 351 frames at 9.75 FPS, 2135857 H.264 bytes; timing audit pending.

2026-10-04 19:19:38: v3 stream l1v3-261009109: 25 accepted deployments, 596 frames at 9.74 FPS, 3403231 H.264 bytes; timing audit pending.

2026-10-04 19:21:15: v3 stream l1v3-261009108: 37 accepted deployments, 1164 frames at 9.60 FPS, 6412079 H.264 bytes; timing audit pending.

2026-10-04 19:21:45: v3 stream l1v3-261009111: 41 accepted deployments, 701 frames at 9.59 FPS, 4120191 H.264 bytes; timing audit pending.

2026-10-04 19:23:28: v3 stream l1v3-261009113: 21 accepted deployments, 348 frames at 9.66 FPS, 2057161 H.264 bytes; timing audit pending.

2026-10-04 19:23:33: v3 stream l1v3-261009110: 39 accepted deployments, 875 frames at 9.56 FPS, 5245343 H.264 bytes; timing audit pending.

2026-10-04 19:25:31: v3 stream l1v3-261009112: 31 accepted deployments, 540 frames at 9.65 FPS, 3378441 H.264 bytes; timing audit pending.

2026-10-04 19:25:46: v3 stream l1v3-261009115: 40 accepted deployments, 1163 frames at 9.60 FPS, 6492388 H.264 bytes; timing audit pending.

2026-10-04 19:27:20: v3 stream l1v3-261009117: 18 accepted deployments, 464 frames at 9.69 FPS, 2673845 H.264 bytes; timing audit pending.

2026-10-04 19:29:11: v3 stream l1v3-261009119: 27 accepted deployments, 461 frames at 9.66 FPS, 2893940 H.264 bytes; timing audit pending.

2026-10-04 19:29:11: v3 shard 1: adaptive minimum reached with all frozen validation/heldout matches complete.

2026-10-04 19:29:11: v3 shard 1 finished both frozen collection plans; emulator remains owned and paused.

2026-10-04 19:29:18: v3 stream l1v3-261009114: 67 accepted deployments, 2136 frames at 9.64 FPS, 11372043 H.264 bytes; timing audit pending.

2026-10-04 19:29:18: v3 shard 0: adaptive minimum reached with all frozen validation/heldout matches complete.

2026-10-04 19:29:18: v3 shard 0 finished both frozen collection plans; emulator remains owned and paused.

2026-10-04 19:29:20: v3 starting stop-emulator-host2

2026-10-04 19:29:22: v3 stopped owned emulator-5584, PID 81567, after firewall verification.

2026-10-04 19:29:22: v3 finished stop-emulator-host2

2026-10-04 19:29:22: v3 starting stop-emulator-host-second

2026-10-04 19:29:24: v3 stopped owned emulator-5586, PID 83460, after firewall verification.

2026-10-04 19:29:25: v3 finished stop-emulator-host-second

2026-10-04 19:29:25: v3 merged 88 matches and 3070 deployments, preserving original splits and hardlinking media.

2026-10-04 19:29:25: v3 starting audit

2026-10-04 19:30:33: v3 pipeline stopped: RuntimeError: audit failed; see retained log

2026-10-04 19:33:18: v3 collection completed with 3070 accepted deployments across 88 matches and 72019 frames. Both owned emulators stopped after firewall verification. The merged corpus uses hardlinks and is undergoing timing/window audit. Late-phase HUD preflight now reads all 282 clocks; its native local p95 timing residual is 37.9 ms and all 15 deployment windows are complete. Added public overtime-phase handling and a generic late-entry state prior; no unseen warmup history is invented. Twenty v3 tests pass.

2026-10-04 19:36:08: v3 full audit stopped at the regulation/overtime transition in a phase-start clip: a missing clock frame hid the 1-to-120 reset from an adjacent-frame-only detector. Preserved the failed audit. The audit now retains the last visible reading across missing frames and uses the visible overtime background. Re-running the audit before any model fit; collected videos/labels and all owned shutdown receipts are unchanged.

2026-10-04 19:36:08: v3 starting audit

2026-10-04 19:37:05: v3 audit: 88 episodes, 3070 accepted events; empirical timing only, certification pending.

2026-10-04 19:37:05: v3 finished audit

2026-10-04 19:37:05: v3 starting train

2026-10-04 19:48:05: v3 fit complete: 24 epochs on continuous training windows; heldout unopened.

2026-10-04 19:48:08: v3 finished train

2026-10-04 19:48:08: v3 starting inputs-validation

2026-10-04 19:48:09: v3 finished inputs-validation

2026-10-04 19:48:09: v3 starting boundary

2026-10-04 19:48:15: v3 finished boundary

2026-10-04 19:48:15: v3 starting infer-validation

2026-10-04 19:57:18: v3 inference complete: 9508 video frames, 17.68 FPS excluding capture.

2026-10-04 19:57:20: v3 finished infer-validation

2026-10-04 19:57:20: v3 starting evaluate-validation

2026-10-04 19:57:41: v3 validation: recall 0.659, precision 0.584, placement 0.604; gates {'event_recall': False, 'event_precision': False, 'placement': False, 'elixir_mae': False, 'uncertainty_coverage': False, 'concentrated_hand': False, 'frame_timing_certified': False}.

2026-10-04 19:57:42: v3 finished evaluate-validation

2026-10-04 19:57:42: v3 starting inputs-heldout

2026-10-04 19:57:43: v3 finished inputs-heldout

2026-10-04 19:57:43: v3 starting infer-heldout

2026-10-04 20:04:01: v3 inference complete: 7159 video frames, 19.18 FPS excluding capture.

2026-10-04 20:04:03: v3 finished infer-heldout

2026-10-04 20:04:03: v3 starting evaluate-heldout

2026-10-04 20:04:17: v3 heldout: recall 0.671, precision 0.511, placement 0.589; gates {'event_recall': False, 'event_precision': False, 'placement': False, 'elixir_mae': False, 'uncertainty_coverage': True, 'concentrated_hand': False, 'frame_timing_certified': False}.

2026-10-04 20:04:18: v3 finished evaluate-heldout

2026-10-04 20:04:18: v3 starting report

2026-10-04 20:04:19: v3 RESULTS-v3.md written from completed heldout metrics; L2 verdict NOT READY.

2026-10-04 20:04:20: v3 finished report

2026-10-04 20:07:27: v3 calibration correction, using validation only: equal-F1 thresholds now prefer more matches, then fewer predictions, then the higher threshold. Zero-TP Miner/RoyalDelivery ties no longer default to 0.3. Preserved original validation and uninspected heldout results. Weights, pixel predictions, candidates and timings remain frozen; rescoring only.

2026-10-04 20:09:13: v3 starting evaluate-validation

2026-10-04 20:09:33: v3 validation: recall 0.659, precision 0.781, placement 0.604; gates {'event_recall': False, 'event_precision': False, 'placement': False, 'elixir_mae': False, 'uncertainty_coverage': False, 'concentrated_hand': False, 'frame_timing_certified': False}.

2026-10-04 20:09:34: v3 finished evaluate-validation

2026-10-04 20:09:34: v3 starting evaluate-heldout

2026-10-04 20:09:49: v3 heldout: recall 0.643, precision 0.667, placement 0.579; gates {'event_recall': False, 'event_precision': False, 'placement': False, 'elixir_mae': False, 'uncertainty_coverage': True, 'concentrated_hand': False, 'frame_timing_certified': False}.

2026-10-04 20:09:50: v3 finished evaluate-heldout

2026-10-04 20:09:50: v3 starting report

2026-10-04 20:09:51: v3 RESULTS-v3.md written from completed heldout metrics; L2 verdict NOT READY.

2026-10-04 20:09:52: v3 finished report

2026-10-04 20:15:28: v3 RESULTS-v3.md written from completed heldout metrics; L2 verdict NOT READY.

2026-10-04 20:29:49: v3 RESULTS-v3.md written from completed heldout metrics; L2 verdict NOT READY.

2026-10-04 20:34:50: v3 RESULTS-v3.md written from completed heldout metrics; L2 verdict NOT READY.

2026-10-04 20:34:50: v3 final verification complete: 3070 accepted deployments, 3064 complete cue windows, 72019 frames, 88 disjoint matches; all 56 cards on both sides in train/primary validation/heldout. Native timing p95 26.96 ms (0.539 ticks), visible-clock midpoint p95 64.48 ms; per-frame certification unresolved. Heldout 180/280 timely matches, 90 false positives: recall 64.29%, precision 66.67%, all-play placement 57.86%. Derived elixir MAE 2.1141; nominal 90% coverage 86.05%, mean width 8.2828; zero concentrated-hand samples. L2 NOT READY. All 51 focused tests and 24 integrity/resource checks pass; all owned emulators stopped. Allocated v3/live-loop storage 1.229/4.820 GiB. RESULTS-v3.md includes per-card scores, calibration diagnostics and limitations.
2026-10-05T06:49:36Z coordinator: disk at 5 GiB -> deleted superseded L1 v1/v2 training datasets, YOLO data copy and intermediate checkpoints (~3.2 GB; regenerable from the renderer; metrics stay in RESULTS-v1/v2). Kept v1/model (detector weights used by L2), v3 dataset, all results.
