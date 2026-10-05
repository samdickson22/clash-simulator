# L1 v2 results

L2 readiness: NOT READY. No acceptance claim is made from the stepped dataset or continuous replay alone. This run used only the unchanged offline native renderer. The official client, game accounts, APK/probe, engine, gamedata and protected experiment directories were not modified.

## Dataset

The main stepped dataset contains 8,074 sanitized JPEGs, 200 accepted deployments, 41 explicit negative windows and eight disjoint seed/deck pairs. Split frames: {'train': 2368, 'validation': 1184, 'heldout': 4522}. Four late deployments originally had only 14 post-command ticks at the cutoff. Separate deterministic replays recaptured their complete -6 through +30 tick windows, adding 74 frames. Original scored inputs stayed frozen. Both seats cover P16 in training and heldout; split gaps are recorded below.

Coverage gaps by split: {'train': [], 'validation': ['0:Giant', '0:Prince', '1:Giant'], 'heldout': []}. Pairing/split/hash failures: [].

Stepped dataset: 0.685 GiB. Entire new v2 directory: 1.213 GiB. Total live-loop, counting hardlinks once: 3.477 GiB. No raw capture files were written; pixels were masked in memory before JPEG conversion.

Each collected interval advances one native tick, waits for a newly produced screenshot and checks unchanged native observations. This is exact simulation stepping, not a certified compositor tick. Deploy-clock and spell animations also advance on presentation time while paused. Therefore the continuous 1x replay is reported separately. It reuses heldout commands without fitting, measures actual screenshot cadence, and brackets event execution from native tick crossings.

Event coordinates retain the requested command placement. The renderer sometimes moves spawns around occupied tower footprints. For example, a training Cannon requested at (2.5, 24.5) appeared at (2.5, 22.5). These labels were not silently changed to make placement pass. 200/200 events have manually reviewed cue-presence samples. Clock traces are pixel-derived and model-assisted. These samples do not certify exact cue onset or every frame's visibility.

## Detector and validation

A small convolutional temporal model uses the current OpenCV color image plus differences from two earlier frames. It was trained for 24 epochs on four training matches, including both 20 Hz and 10 Hz stacks. Checkpoint SHA-256: `ac305303578214c75d6ca718ee9bb68c090e3e7b36860c0f4b72ca4cb6a09143`. Deploy clocks use pixel color/ring evidence, with offsets fitted only on training. Fusion combines these cues with v1 track births and own hand/elixir transitions. Own spell events retain unknown placement if spatial evidence is weak.

Validation selected temporal threshold 0.5 and clock threshold 0.8. Validation recall 88.37%, precision 95.00%, all-play placement 69.77%. The initial validation run and the spell/clock fusion correction are retained under `*-initial`. No heldout fitting followed model/threshold freezing.

## Heldout gates

| Run | Recall within 0.5 s | Precision | Placement within 1 tile, all plays | Elixir MAE | Hand accuracy once determined |
|---|---:|---:|---:|---:|---:|
| fast-stream | 24.00% | 19.35% | 24.00% | unmeasured | unmeasured |
| heldout-10 | 85.33% | 76.19% | 65.33% | 3.3693 | 24.49% |
| heldout-10.9141 | 88.00% | 77.65% | 68.00% | 3.3211 | 12.52% |
| heldout-20 | 89.33% | 72.83% | 68.00% | 4.1151 | 16.79% |

Targets are recall >=90%, precision >=90%, placement >=90%, elixir MAE <=0.5 and hand accuracy >=90%. Placement includes missed events and unknown coordinates as failures. Matching is one-to-one and requires the correct seat/card. Stepped timings use media time. Continuous timing conservatively requires a prediction after the event bracket upper bound and within 500 ms of its lower bound; there is no compositor fence. Event latency uses image production time and excludes capture transport and inference completion latency.

fast-stream: 18/75 timely matches, 75 false positives, 18/75 placements. This is the live event check, using every captured frame at measured rates of 10.25 and 10.06 FPS. It uses native advances up to the next command boundary, with a one-tick bracket around each deployment. Sparse native observations do not certify per-frame derived-state truth, so that gate is scored on the complete stepped heldout matches. JPEG quality is 55 for this extra replay to stay within the data cap; main data uses 82.

heldout-10: 64/75 timely matches, 20 false positives, 49/75 placements. Derived state covers 2262 frames, with 1895 reference-determined hand frames and 61.53% hand coverage on that denominator. True-event elixir reference MAE 0.0177. Gates: {'events': False, 'placement': False, 'derived_elixir': False, 'derived_hand': False}.

heldout-10.9141: 66/75 timely matches, 19 false positives, 51/75 placements. Derived state covers 2468 frames, with 2068 reference-determined hand frames and 36.27% hand coverage on that denominator. True-event elixir reference MAE 0.0177. Gates: {'events': False, 'placement': False, 'derived_elixir': False, 'derived_hand': False}.

heldout-20: 67/75 timely matches, 25 false positives, 51/75 placements. Derived state covers 4522 frames, with 3789 reference-determined hand frames and 54.68% hand coverage on that denominator. True-event elixir reference MAE 0.0177. Gates: {'events': False, 'placement': False, 'derived_elixir': False, 'derived_hand': False}.

Timing sensitivity on the same frozen live-stream predictions: command-bracket midpoint recall 28.00%, precision 22.58%; optimistic interval-compatible upper bounds are recall 38.67%, precision 31.18%, placement 36.00%. These also fail. The conservative result is a lower bound, not an exact render-timestamp measurement.

## Derived-state robustness

The exact public-state source was copied and hash-pinned without importing or writing in srp-public. The adapter maintains a bounded accept/skip posterior, checks affordability, deduplicates events, and tests one omitted play when an observed card contradicts a hypothesis. Hand-slot permutations are merged while preserving prior mass. Elixir is a posterior mean; hand predictions require 90% posterior mass. That confidence is a model assumption, not a proof of correctness. Perceived updates use visible-clock intervals and relative media time. Native ticks and hands are scoring-only inputs.

The corruption experiment applies independent seeded misses, inserted plays, or wrong identities to true events. It samples scoring states once per second but processes each corrupted event at its original time. Its zero-error baseline isolates event-noise degradation from detector timing error. There is one fixed corruption seed, so these are diagnostics, not confidence intervals.

| Error mode | Nominal rate | Realized errors / events | Elixir MAE | Determined-hand accuracy |
|---|---:|---:|---:|---:|
| miss | 0.00% | 0/38 | 0.0110 | 100.00% |
| miss | 5.00% | 2/38 | 0.1358 | 89.47% |
| miss | 10.00% | 3/38 | 1.0923 | 78.42% |
| miss | 20.00% | 8/38 | 3.5397 | 19.47% |
| insert | 0.00% | 0/38 | 0.0110 | 100.00% |
| insert | 5.00% | 3/38 | 0.0110 | 100.00% |
| insert | 10.00% | 3/38 | 0.0110 | 100.00% |
| insert | 20.00% | 11/38 | 0.1761 | 93.16% |
| wrong | 0.00% | 0/38 | 0.0110 | 100.00% |
| wrong | 5.00% | 2/38 | 0.1358 | 89.47% |
| wrong | 10.00% | 2/38 | 0.1144 | 91.58% |
| wrong | 20.00% | 8/38 | 2.9601 | 32.11% |

## Runtime and evidence

stream-dataset, l1v2-261006106: 3091 screenshots at 12.13 FPS, simulation 8.87 ticks per wall second; screenshot-to-saved p95 116.6 ms; final opponent hand/elixir replay parity True.
stream-dataset, l1v2-261006107: 3196 screenshots at 12.43 FPS, simulation 8.80 ticks per wall second; screenshot-to-saved p95 112.4 ms; final opponent hand/elixir replay parity True.
fast-stream-dataset, l1v2-261006106: 1530 screenshots at 10.25 FPS, simulation 15.15 ticks per wall second; screenshot-to-saved p95 145.2 ms; final opponent hand/elixir replay parity True.
fast-stream-dataset, l1v2-261006107: 1539 screenshots at 10.06 FPS, simulation 14.79 ticks per wall second; screenshot-to-saved p95 146.6 ms; final opponent hand/elixir replay parity True.

The single-tick stream is an unscored pacing diagnostic because one-tick control overhead slowed simulation. Its original JPEG bytes are preserved in verified lossless tar.xz chunks under stream-dataset/archives; loose originals were removed only after every member hash matched. The initially blocked stream attempt is excluded and retained under rejected-blocking-*.

A fixed-phase stream subsample averaged only 8.19 and 8.08 FPS because it dropped bursty arrivals. It is retained under *fast-stream-subsampled*. The final event gate uses all 3,069 frames at the native capture cadence. Fractional raw media timestamps are floored to integer milliseconds in the public manifest, as required by the unchanged inference contract; raw receipts remain intact.

A coordinator handoff raced with a tail-recapture child already starting. The duplicate attempt failed at the existing-directory guard before issuing native commands. The original child completed the 74 supplemental frames and continued as the sole event-boundary capture driver. Ownership and recovery receipts are retained.
Inference validation: 9.01 FPS, p95 169.8 ms, excluding capture. This is not a closed-loop throughput result.
Inference fast-stream: 19.49 FPS, p95 59.2 ms, excluding capture. This is not a closed-loop throughput result.
Inference heldout-10: 9.59 FPS, p95 165.3 ms, excluding capture. This is not a closed-loop throughput result.
Inference heldout-10.9141: 9.55 FPS, p95 157.4 ms, excluding capture. This is not a closed-loop throughput result.
Inference heldout-20: 10.05 FPS, p95 144.6 ms, excluding capture. This is not a closed-loop throughput result.

The runtime input-boundary check processed 4 frames with private-label/native-data reads and INET sockets denied. There were 0 forbidden file-read attempts, 3 blocked library connectivity probes, and zero successful network connections. Details are in boundary-runtime.json. Emulator launch and shutdown receipts verify both IPv4 and IPv6 game-UID egress blocking. Only one 3072 MiB / two-core emulator was used.

Validation and stepped inference ran with the emulator active; final stream inference ran after its shutdown. These timings do not establish concurrent capture/perception throughput. All 52 focused tests pass. The final integrity record verifies frozen inference sources, weights, thresholds, predictions, the unchanged protected reference, dataset pairing, storage caps, lossless archives and owned emulator shutdown. Tests and integrity checks do not override the failed quality gates.

Evidence lives in v2/dataset, v2/tail-windows, v2/audit-final, v2/model, v2/inference-*, v2/evaluation-*, v2/stream-dataset, v2/fast-stream-dataset, v2/validation and v2/emulator. PROGRESS.md records collection, training, validation revisions, ownership and final checks. The model does not yet justify L2 admission. Remaining work includes timely opponent spell identity/placement, robust placement under native snapping, and reliable live-rate event fusion; exact rendered-tick timing remains uncertified.

## Files changed

New vision modules: src/clasher/vision/l1_events_v2.py and l1_derived_v2.py. New scripts: collect_l1_events_v2.py, train_l1_events_v2.py, infer_l1_events_v2.py, evaluate_l1_events_v2.py, audit_l1_events_v2.py, run_l1_events_v2.py, collect_l1_stream_v2.py, run_l1_stream_v2.py, recapture_l1_tail_v2.py, archive_l1_diagnostic_v2.py, finish_l1_capture_v2.py, run_l1_fast_stream_eval_v2.py, verify_l1_v2_boundary.py and report_l1_events_v2.py. Tests: tests/test_l1_v2.py. Reports: live-loop/l1/v2/, PROGRESS.md and RESULTS-v2.md. No existing v1 source was edited.
