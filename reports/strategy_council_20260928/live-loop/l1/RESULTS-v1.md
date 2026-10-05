# L1 v1 results

L2 readiness: NOT READY. The report below separates measured failures from unverified gates. Only the unchanged offline native renderer was used. No official client, account, game-app network, native-probe/APK modification, or engine edit was part of this work.

## Gates

| Gate | Target | Result | Verdict |
|---|---|---|---|
| Dataset | 10k–20k frames | 11794 | PASS |
| L1 data/storage | <3 GiB data; <1 GiB models | 2.043 GiB data; 0.213 GiB models | PASS |
| Entity position, all truth | >=90% within one tile | 96.95% | PASS |
| Non-tower position, all truth | >=90% within one tile | 93.75% | PASS |
| Both-side plays | >=90% correct card within 500 ms | 70.87% | FAIL |
| Play placement, all plays | >=90% within one tile | 59.06% | FAIL |
| Non-tower HP, certified visible | >=60% coverage; MAE <=0.10 | unmeasured; unmeasured | FAIL |
| Clock | MAE <=1 second | 0.0000 s | PASS |
| Derived opponent elixir | MAE <=0.5 with full coverage | 2.6779; coverage 11.58% | FAIL |
| Derived opponent hand | >=90% once determined | 0.00% over 633 reference-determined frames | FAIL |
| Streaming capture | >=10 FPS sustained | 10.9141 FPS | PASS |
| Render-tick latency | p95 <=150 ms | Uncertified; no render-tick fence | FAIL |
| Perception throughput | >=10 FPS | 24.8459 FPS | PASS |
| Public status/lifecycle | Required before L2 | Not implemented | FAIL |

## Dataset and pairing

11794 JPEG frames, 1,209,419,984 bytes, 40 seeds and 80 distinct decks. Split counts: {'train': 9994, 'validation': 600, 'heldout': 1200}. Seeds and decks are disjoint across splits, and all v0 decks were excluded. Both shards are retained; the merged dataset uses hardlinks, so it does not duplicate JPEG storage.

Collection advances continuously for 2, 4, 6 or 8 ticks, then pauses, waits for a fresh gRPC image, and observes again. Four placement styles cover balanced, bridge, backline and spread play. The intro advances at 1x without actions until the public HUD is visible. Native state must remain equal across capture; every admitted frame also agrees with the frozen v0 clock reader. This clock-conditioned sample is not an unfiltered live-clock test. All images are masked at source resolution before downscaling to 540x1140. No raw video or screenshot files are retained.

All 11794 hash/pairing receipts pass. Visibility assessments: {'uncertain': 123016}. Projected-box overlap and possible Tesla retraction are recorded per label. Uncertain labels are retained in conservative all-object metrics. There is no independently certified visible-unit denominator, so the visible-HP gate cannot pass. Ground-anchor boxes remain weak sprite extents. Paused state equality and clock agreement do not establish an exact compositor tick.

The H.264 pilot delivered 28.9 FPS but failed freshness: tick 344 still showed 2:44 while a fresh screenshot showed 2:43. Its 30 frames are excluded. A separate 40-frame gRPC smoke passed all visible-clock checks and is also excluded from the scored dataset.

## Detector and public readings

YOLOv8n was retrained from the local v0 checkpoint for 6 epochs at 640 pixels, initial batch 16, resumed batch 8, on MPS. JPEG compression and blur augment the training images; colour, translation and scale augmentation run during training. No heldout images enter model or HUD fitting. Stable hand windows and bounded per-value templates keep dense sampling from inflating HUD memory.

Selected checkpoint SHA-256: `8b6fde6fc402e2b075cdd9e5a92a9486eb738b0428912b7c1975aa12491748a5`. Validation uses CPU NMS without a time cutoff so late images in a batch cannot be silently skipped. Model selection uses validation only.

Entity precision 92.20%, recall 97.14%. Non-tower position within one tile, including misses: 6190/6603. HP readings cover 4362/6603 non-tower labels, or 66.06%, with MAE 0.0498. This denominator includes visibility-uncertain labels.

Own hand slot accuracy 99.69%; whole-hand accuracy 98.83%; next card 99.92%. Displayed own elixir accuracy 97.08%, MAE 0.0350. Clock missing on 0 frames. No additional own-HUD acceptance threshold was invented.

| Card | Truth | Predictions | Precision | Recall | Mean position error, tiles | p95 position error | Within 1 tile, all truth |
|---|---:|---:|---:|---:|---:|---:|---:|
| Archers | 882 | 976 | 89.04% | 98.53% | 0.0872 | 0.2827 | 98.53% |
| Cannon | 725 | 720 | 98.89% | 98.21% | 0.0296 | 0.0564 | 98.21% |
| DarkPrince | 65 | 84 | 77.38% | 100.00% | 0.1104 | 0.2169 | 100.00% |
| Giant | 63 | 62 | 93.55% | 92.06% | 0.1219 | 0.2452 | 92.06% |
| Goblins | 1033 | 1457 | 66.85% | 94.29% | 0.1958 | 0.6735 | 92.35% |
| HogRider | 99 | 106 | 83.02% | 88.89% | 0.1084 | 0.3335 | 88.89% |
| IceGolem | 757 | 758 | 96.57% | 96.70% | 0.1028 | 0.2246 | 96.70% |
| IceSpirit | 197 | 222 | 73.87% | 83.25% | 0.1713 | 0.6056 | 83.25% |
| KingTower | 2400 | 2400 | 100.00% | 100.00% | 0.0182 | 0.0225 | 100.00% |
| Knight | 804 | 881 | 88.65% | 97.14% | 0.1048 | 0.2488 | 97.01% |
| Musketeer | 169 | 206 | 78.64% | 95.86% | 0.0778 | 0.2180 | 95.86% |
| Prince | 76 | 86 | 75.58% | 85.53% | 0.2129 | 0.5202 | 85.53% |
| Skeletons | 1733 | 1754 | 88.08% | 89.15% | 0.1355 | 0.4629 | 88.92% |
| Tesla | 0 | 8 | 0.00% | unmeasured | unmeasured | unmeasured | unmeasured |
| Tower | 4586 | 4597 | 99.74% | 99.98% | 0.0103 | 0.0234 | 99.98% |

Position errors are conditional on identity/owner matching within three tiles. The final column counts unmatched truth as failure.

## Deployments and derived state

Strict events: 90 matched, 37 missed, 93 false positives; precision 49.18%. Placement within one tile is 83.33% among timely detected plays and 59.06% across all plays. Unknown placement is a miss. Mean timely event delay 248.8889 ms; this excludes real capture and inference delay.

Persistent tracks survive brief detection gaps. New same-card units are clustered near legal deployment zones. Own plays additionally require a hand transition with a visible elixir spend or a confident refill; submitted actions never count as perception. HUD-only spell events retain unknown placement. Opponent spell-effect recognition remains unimplemented, so the event work is incomplete.

The unmodified srp-public/derived_public_state.py was run on perceived opponent plays and the perceived clock, using a monotonically clamped interval midpoint. The frozen prior is a uniform deck population without episode assignments. Opponent elixir MAE 2.6779 on 139/1200 frames. Opponent hand resolved on 10 frames, conditional accuracy 0.00%, exact recovery over all frames 0.00%. Posterior collapses: [{'episode_id': 'l1-261005216', 'frame_id': '574', 'error': 'no deck/order consistent with public plays'}, {'episode_id': 'l1-261005217', 'frame_id': '372', 'error': 'no deck/order consistent with public plays'}, {'episode_id': 'l1-261005218', 'frame_id': '246', 'error': 'no deck/order consistent with public plays'}, {'episode_id': 'l1-261005219', 'frame_id': '412', 'error': 'no deck/order consistent with public plays'}].

Event-spend diagnostic: {'opponent_true_spend': 135, 'opponent_perceived_spend': 296, 'missed_minus_extra_spend': -161, 'interpretation': 'Missing spend raises the derived elixir estimate until the cap; extra or wrong plays lower it and can eliminate every hand/order. This spend difference is a diagnostic, not the actual elixir error.'}. Misses leave too much derived elixir until the cap; false or wrong plays can reduce it and make the hand/order posterior inconsistent. Posterior failures stop derivation; no truth repair is applied.

Evaluation-only true-event reference: elixir MAE 0.0129 on 1200 frames. The reference determines the opponent hand on 633 frames, with accuracy 100.00%. Perceived-event hand accuracy on those same frames is 0.00%, counting abstentions and collapsed states as misses. These native labels and ticks are used only for scoring; they never repair or feed the pixel model.

## Capture and latency

1x capture with short controller pauses between ten-second segments: 828 frames over 75.77 seconds, 10.91 FPS. The authenticated gRPC endpoint is loopback-only. Emulator screenshot-production timestamp to sanitized host receipt: mean 66.43 ms, p95 122.37 ms, p99 141.65 ms. This is a screenshot-transport measurement, not certified render-tick latency. The latter remains unmeasured because the unchanged renderer supplies no per-frame tick fence.

JPEG-to-public-frame perception: 24.85 FPS, p95 57.39 ms, synchronized batch-1 MPS. Capture, search and action execution are excluded; capture and perception rates must not be added together as a closed-loop result.

## Evidence and remaining work

Artifacts: v1/dataset-merged/audit.json, v1/model/training_manifest.json, v1/inference/frames.jsonl, v1/inference/timing.json, v1/evaluation/metrics.json, v1/evaluation/derived.jsonl, v1/stream-timing.json, v1/producer-sources.json and v1/producer-sources.zip. Emulator launch, attestation, firewall and stop receipts are in v1/emulator-grpc-auth2 and v1/emulator-second.

Before L2, close the failed perception gates, implement opponent spell cues and public status/lifecycle handling, establish visible-unit labels for HP scoring, and obtain defensible render-tick latency evidence without changing the prohibited native probe/APK. No offline closed-loop search/control acceptance run was performed.

## Changed files

Vision: src/clasher/vision/l1_perception.py, l1_stream.py, l1_temporal.py, l1_hp.py, l1_training.py.

Scripts: scripts/collect_l1_rendered.py, audit_l1_dataset.py, train_l1_perception.py, resume_l1_training.py, infer_l1_perception.py, evaluate_l1_perception.py, evaluate_l1_v1.py, benchmark_l1_stream.py, launch_l1_reference.py, run_l1_v1_pipeline.py, report_l1_v1.py.

Tests: tests/test_l1_v1.py. Reports and generated artifacts: this L1 directory, primarily v1/, PROGRESS.md and RESULTS-v1.md.

## Resource restart

Host pressure reached 6.7 GiB free disk and 9.6 GiB swap during epoch 2. Only the owned trainer was stopped. The completed epoch-1 checkpoint retained optimizer state; the incomplete second epoch was discarded. scripts/resume_l1_training.py resumed the fit at batch 8. After epoch 2 completed, validation box matching and retained statistics moved to CPU, and a second restart discarded a short partial epoch 3. The input data and HUD model stayed unchanged. Both completed checkpoints, initial producer archives, checkpoint hashes, and resume source hashes are retained.

A later free-disk guard stopped an incomplete epoch 5. The final two epochs used separate processes, releasing MPS caches after each saved checkpoint and requiring at least 8 GiB free disk before the next process started. Only completed epochs count toward the reported fit.

The resumed process uses MPS high/low allocator ratios of 0.4/0.25 and clears unused MPS cache every 25 batches and at epoch/validation boundaries. These controls follow the [PyTorch allocator documentation](https://docs.pytorch.org/docs/stable/mps_environment_variables.html). Actual driver allocation, swap and free disk are logged in v1/model/mps-memory.jsonl. Foreign jobs were never signalled.

## Final verification

All 42 focused L1 and existing contract/privacy tests pass. The canonical live-inference CLI reproduces every exported contract metric and gate exactly; its exit code is 1 because acceptance fails. Frozen prediction and training-label hashes were rechecked. The upstream derived-state source hash matches v0. All owned emulators and long-running L1 jobs are stopped.

Four fixed heldout samples were visually inspected in v1/heldout-qa.jpg. Ground-anchor predictions align with the native labels, while dense troop groups show extra detections. This is a spot check, not per-label visibility certification. Heldout traces contain no Tesla bodies, so Tesla recall remains unmeasured despite training support. No tuning followed heldout inspection.
