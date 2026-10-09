# Perf audit: v4 perception, validation capture and the live runtime (P1–P5)

Auditor: read-only subagent, 2026-10-08 ~23:50Z. No code edited, no jobs touched, no commits.
Evidence comes from code reading, the repo's own profiling receipts, and one light CPU microbenchmark on
127x08. That run used nice 19, one process, `CUDA_VISIBLE_DEVICES=` and synthetic random-weight inputs with the
real vocabulary sizes (56 cards, 39 bodies). The T5 GPU job there stayed at 100%, and the scratch files were
deleted afterwards. No validation, heldout or eval payload was opened. Out of scope: cross-match lockstep
batching (another worker owns it), T11/GRU, and simulator search.

## 0. What is actually on the clock

| Pipeline | Current cost | Is it on the critical path? |
|---|---|---|
| T7 formal fit (24×400, batch 1, bf16) | **692 s** total, 13.9 windows/s (`l1/RESULTS.md`) | No. Training is solved. |
| T6/v3 control fit and inference | complete | No |
| **Validation capture, 24 epochs × 64 matches × 106,744 frames × 9 body branches** | packed serial 0.9–5 fps/process; vectorized quarantine **48.8–81.5 ms/frame** (`receipts/inference-sharing-20261008/vectorized-capture-status-2338.json`) | **Yes.** It gates selection, seal, heldout, E1, E9 and L2-v4. |
| CPU 18-cell grid per epoch | 225 s with 2 workers (epoch 1, sparse) | Minor |
| Live P1–P5 on the Mac | 186 ms p50 / 334 ms p99 frame→tap, **measured with v3 fallback perception**. v4 on MPS is unmeasured. | **Yes.** E4 T9 smoke needs ≥18 FPS, ≥95% processed, p50 ≤260 / p99 ≤400 and ≥90% first-attempt acceptance. L2-v4 runs 29 h on 1 renderer vs 14.5 h on 2; 2 renderers need CPU/MPS headroom. |

## 1. Ranked opportunities

### #1 (BLOCKING correctness, fixed by speed): the shared 9-branch capture inflates the measured FIFO availability clock

(a) Files: `l1/shared_epoch_inference_v4.py:main`, `shared_epoch_inference_packed_v4.py` and
`vectorized_capture_candidate_v4.py:main`. In each, the per-branch loop does
`service=(now-started[i])*1000; ready[i]=max(ready[i],stamp)+service; started[i]=now`.
Consumers are `persisted_grid_decode_v4.decode_episode` → `validation_replay_v4.completed_predictions` →
`scoring_v4` matching, which requires `hi <= available <= lo+500`.

(b) Evidence, from code plus the repo's own profile receipts:
- `started[i]` is reset only when branch i finishes. Branch i's "service" for frame k is therefore the **whole frame
  period**: the 8 other branches, the cache fetch and every write.
- When the frame period P exceeds the 50 ms production interval, each branch's availability lag grows by about
  (P−50) ms per frame.
- Quarantine vectorized profiles give P = **75.0 ms (epoch 1)**, **81.5 ms (epoch 3)** and **48.8 ms (epoch 20)**:
  (cache+step+extract+write)/frames.
- At epoch 3, the lag after one minute of play is about 1200 × 31.5 ms ≈ 38 s. The mean match (1,668 frames) ends
  about 52 s behind. Any prediction after roughly the first second of a match fails the 500 ms window.
- Epoch 20 runs at a utilization of ρ ≈ 0.98, so FIFO backlog still builds to seconds.
- The packed/serial production path (0.9–5 fps) is far worse.
- For comparison, the honest single-branch `validation_replay_v4` took about 940 s per cell, about 8.8 ms/frame
  (ρ ≈ 0.18). That is why `body-3-complete.json` shows `final_available ≈ (frames−1)×50 ms`.
- The equality gates could not catch this. They were checked on epoch 1, where the 0.5 event threshold has
  **0 predictions** (`persisted-verified-r2.json`), so the clock-dependent metrics are trivially equal.

(c) Impact: without a fix, event recall at 500 ms in every captured epoch with real predictions collapses toward 0.
The epoch/threshold selection grid then measures capture contention, not model quality, and 24 epochs of GPU time
are wasted. The honest clock options are:
- **Attributable per-branch clock** (recommended): service_i = measured shared-stage time + measured own-branch
  time, with stage boundaries already synchronized because `PixelPerception.step` calls `cuda.synchronize()`. This
  is what one deployed runtime experiences, and it needs no backdating or reference clocks.
- Or keep raw capture clock-free and re-measure FIFO in single-branch replays of the shortlisted configs.
- Simply making all 9 branches finish in <50 ms is **not** sufficient. It still biases each branch late by about 9×
  its own work and is load-dependent.
- The lockstep-batching worker must adopt the same attribution, or its batch period will inflate clocks the same way.

(d) Effort: about 15 min to confirm (a one-liner over any completed capture's `*-completion.jsonl` computing
`available − timestamp` at the last frame); 2–3 h to implement attributable timing; then a coordinator amendment
and a re-gate.

(e) Risk: non-clock records are unchanged (byte-identical decoder streams). Only the clock fields change, which is
the intended fix. Exactness check: non-clock streams are byte-equal to the existing captures. Clock validity check:
the clocks should reproduce the single-branch replay's lag distribution (median within a few ms) on a few matches.

(f) Frozen: yes. The capture schemas and source pins are referenced by `capture_admission_v4`, the equality proof
and the vectorized full gate. Implement it in a new capture-driver file with a new schema plus an amendment.
Captures already made keep their records; only their clock files need re-measuring.

### #2: Hoist per-frame shared work out of the 9-branch loop (validation capture, exact)

(a) Same drivers as #1; `l1_v4.PixelPerception.step`; `shared_model_v4.SharedModel`; `vectorized_shared_model_v4`.

(b) Each frame, every branch repeats work with identical inputs and identical deterministic ops:
- `prepare_pixels` runs 9× (0.69 ms each on CPU, measured): about 5.5 ms/frame wasted.
- Two host→device tensor builds per branch, plus `SharedModel.encode`'s `torch.equal` guard: 2 GPU syncs × 8 branches.
- `FeatureRing` appends and the 16-frame `torch.stack`: 9 identical rings, plus 3 `torch.equal` syncs × 8 in
  `SharedModel.temporal`.
- The HUD block (softmax/argmax/`tolist`/`float`, about 7 syncs) and `own_plays` produce identical results in all
  9 branches, so about 56 redundant syncs per frame.
- `decode_bodies` is already cached by `DecoderAdapter`.
- The per-branch temporal **tail** runs 9× even when births are identical. At body thresholds ≥0.5 most branches
  have zero births. `VectorSharedModel` dedupes this by exact input equality, but it is "experimental, not
  admitted" (amendment 08).

Only the tracker, births, tail, event records, fusion and the write are branch-specific. The measured remainder is
about 8 ms per branch-step (72 ms of `runtime_step` per frame at epoch 3). The CPU-proxy tail is about 5 ms, and
the tracker is ≤2 ms even at 128 detections (measured, table §3).

(c) Estimated 1.8–2.5× on `runtime_step` (72 → about 30–40 ms/frame). Validation-capture wall time after the 05:00
lease exit, with about 3 home GPUs × 3 processes: about 5 h → about 2.5 h for the remaining epochs. With #1 this
also cuts contention noise in the clocks.

(d) 4–6 h for a new `SharedFramePerception` driver that keeps per-branch tracker/fusion/ring objects; it reuses
the existing quarantine/full-gate tooling.

(e) Exact by construction: same ops, same shapes, batch 1, no reordering. Bit-exact checks:
`verify_shared_records_v4` / `verify_vectorized_capture_v4` compare byte-identical decoder streams. Amendment 08
showed that **cross-branch batching is NOT exact**, so do not batch tails; dedupe only identical inputs.

(f) Frozen: `l1_v4.py` stays untouched (use an adapter, as `DecoderAdapter` does). The capture driver is new-path
and needs the equality gate.

### #3: Port the vectorized decoder into the live V4 P1 path (per-peak host syncs)

(a) `src/clasher/live/perception.py:V4Perception`, which calls `l1_v4.PixelPerception.step`. That in turn calls
`decode_bodies(out,bodies,.1)` (up to 128 peaks × 3 scalar device reads: `float(hp_visible)`, `box.tolist()`,
`float(hp)`), `EventFusion.update` (about 6 scalar reads plus a per-candidate softmax/topk), and the HUD
(about 7 reads).

(b) Measured analog on CUDA, from the repo's real epoch-24 probe (`runtime-epoch24-r1.json`): 32 frames × 9
branches took 8.508 s scalar vs 2.128 s vectorized, i.e. **29.5 → 7.4 ms per branch-frame**, with byte-identical
records. That is about **22 ms per frame of pure sync/Python overhead** at dense-epoch peak density, and live P1
uses the same 0.1 body threshold. On MPS each blocking read flushes the command buffer, so it is likely costlier;
this is unmeasured and should be checked with a 10-minute Mac microbenchmark. The 20 FPS budget is 50 ms/frame.

(c) Live P1 latency is estimated to drop by about 20+ ms/frame. Effects: P1 throughput toward ≥18 FPS / ≥95%
processed (E4), frame→tap p50, and HUD freshness (#4). It also frees Mac CPU for a 2-renderer qualification
(L2-v4 29 h → 14.5 h).

(d) About 1.5–2 h. `vectorized_runtime_adapter_v4.DecoderAdapter` already monkeypatches `decode_bodies`/`EventFusion`;
install it in `V4Perception.__init__`. Add a Mac parity run on 2 train recordings.

(e) Bit-exact by design (same fp32 values, single packed transfer). The quarantine proved this on CUDA (synthetic
25×/38× faster, real 0 mismatches). Repeat the record-equality check on MPS with train recordings.

(f) The L2-v4 PREREG freezes `src/clasher/live/` hashes **before the first confirmatory game**. The T9 smoke has not
run yet, so the change is allowed now but must land before T9/E4 and the verifier re-test. `l1_v4.py` stays
untouched.

### #4: v4 HUD freshness: P4 has no direct HUD reader in v4 mode, so commands can expire unexecuted

(a) `runtime.py:p4`. `hud_reader` is built only for `kind=='v3'`. A command waits for
`fresh = now-hud.produced_at <= .060`, otherwise until `expires_at` (source + 400 ms), when `Actuation.submit` blocks
it as `'expired command'`.

(b) In v4 mode the only HUD comes from P1 after perception. Its age at P4 is about capture (17 ms p50 / 42 ms p95)
+ ring wait (about 13 ms p50) + P1 perception + one hop. Even at the v3-fallback perception speed (29 ms) that is
about **61 ms p50**, already over the 60 ms bound. v4 on MPS is expected to be slower. The measured 186 ms Mac run
did not exercise this, because the v3 path's P4 reads HUD directly from the newest ring frame (1.5 ms).
Measured on CPU: the v4 HUD-only path `model.hud(model.backbone.stem(hud))` takes **2.1 ms** on one CPU thread and
is **bit-identical** to `encode()`'s HUD outputs on the same device.

(c) This prevents a large share of taps from expiring or waiting, which hits E4 first-attempt acceptance ≥90%,
frame→tap p50/p99 and the verifier re-test. The expected frame→tap gain is several tens of ms, and correctness
improves (no expiry).

(d) 3–4 h: in P4, load the v4 checkpoint's backbone stem and HUD head on CPU, then crop and resize the HUD atlas
from the newest ring frame exactly as `prepare_pixels` does.

(e) Bit-exact against P1 only if it runs on the same device. CPU vs MPS can flip argmax near ties, so measure HUD
agreement on train recordings. The alternative is to relax the 60 ms freshness window, which is a T2 actuation
protocol change and not recommended.

(f) Same freeze as #3 (live runtime hashes before T9). It should be done **before** the PREREG's "P4 verifier
re-test with the v4 HUD head".

### #5: The temporal head recomputes 16 frames of work to read one token (Mac/CoreML export and live MPS)

(a) `l1_v4.TemporalHead.forward` and `shared_temporal_v4.prefix`. `self.spatial` runs on all 16 cached frames every
step; q/attention/proj/LayerNorm/FF run for all 16 tokens, but only the latest token is gathered. `EXPORT.md`'s
planned `event.pt`/`event.mlpackage` inherits this.

(b) Measured on CPU, 1 thread, real shapes:

| Variant | ms |
|---|---|
| Temporal full | **101** |
| Backbone | 158 |
| Spatial over 16 frames | 17.8 |
| Spatial over 1 frame | 1.15 |
| Prefix | 85 |
| Tail | 5 |
| **Latest-query-only attention with per-frame cached spatial** | **23.0 (4.4× temporal; 259 → 181 ms model total on CPU, −30%)** |

Max abs differences of the latest-only variant: event logits 9.5e-7, age 3.7e-4 ms, sigma 6e-5 ms. It is not
bit-exact. Caching the spatial output per frame alone was bit-equal on CPU (batch 1 vs batch 16), but saves only
about 16 ms of the 101.

(c) Mac P1 model time is estimated to fall 25–30% if MPS/ANE cost scales like FLOPs. It helps E4 FPS and a
2-renderer mode. It does not help fleet capture, which is CPU/launch-bound.

(d) 6–10 h, including CoreML conversion of a two-module design: a per-frame "spatial + K/V" producer, and a
latest-query head with a parity test.

(e) Not bit-exact (reassociation at the 1e-6 level). It must be evaluated by decision agreement, as EXPORT.md
already requires for fp16 CoreML (≥100 validation windows, event/board disagreements).

(f) The scientific model is frozen, and the formal checkpoint and selection depend on `TemporalHead`. Deploy only as
a new export/runtime path, chosen before E1/E4 and validated on validation windows. Never change the fleet
reference path mid-selection. Lowest risk: fold it into the CoreML export work, which already accepts non-bit-exact
fp16.

### #6: Overlap the GPU temporal prefix with the CPU tracker in live P1 (exact)

(a) `PixelPerception.step` order: encode → body decode (sync) → tracker/birth maps (CPU) → `temporal` (GPU) →
fusion. `prefix()` does not depend on births.

(b) The prefix/tail factorization is bit-equal (CPU measured here; CUDA in amendment 04, 108 comparisons plus real
matches). Enqueue `prefix` right after the body-decode sync, run the tracker and `birth_maps` on CPU, then the tail.

(c) Saves min(prefix GPU time, tracker+births CPU time): about 1–5 ms per frame in live P1.

(d) About 2 h in the live adapter, plus an MPS equality check.

(e) Exact (same ops and shapes).

(f) Live runtime freeze as #3.

### #7: Polling hops in the live runtime

(a) `runtime.py` p1/p2/p3/p4 idle loops: `ipc['stop'].wait(.002/.002/.003/.002)` on empty queues.

(b) Average added latency is about half a period per hop. There are about 4 hops between frame and tap (ring→P1,
obs→P2, snapshot→P3, command→P4): about **4–5 ms p50**, about 10 ms worst case. It also costs about 2,000 wakeups/s
on the shared 12-core Mac.

(c) Frame→tap −4..−5 ms p50.

(d) 1–2 h: blocking `get(timeout=…)` on the multiprocessing queues, and a `multiprocessing.Event`/condition for the
ring. Keep the `put_latest` drop-oldest semantics.

(e) Semantics-preserving, but concurrency tests must be re-run (`tests/live_v4`).

(f) Live freeze as #3.

### #8: CPU grid decode: redundant `deepcopy` and JSON (exact; low priority)

(a) `persisted_grid_decode_v4.decode_episode` calls `tracker.update(deepcopy(record['bodies']),...)`.
`BodyTracker.update` never mutates its input dicts, because it copies via `dict(...)`.

(b) For a dense record (128 bodies), `deepcopy` takes 0.55 ms vs 0.01 ms for a shallow copy, and `json.loads` takes
0.75 ms (measured). The grid processes 9 × 106,744 records per epoch, about 0.5 ms × 960k ≈ 8 CPU-min per epoch at
dense epochs. orjson is not installed.

(c) About 30–40% of grid CPU. It saves minutes per epoch on plentiful CPU, so it is not critical-path.

(d) 0.5 h.

(e) Exact; the equality is checkable with the existing grid outputs.

(f) `persisted_grid_decode_v4.py` is source-pinned in `capture_event_score_v4.score_event_grid`, so it needs a
new-file variant plus re-pinning. Do it only if grids are re-run anyway (they will be, after #1).

### #9: Serialization in capture (low)

(a) Capture drivers write `json.dumps` + gzip-1 + `flush()` per branch per frame, and `bodies` is identical in all 9
records.

(b) Measured 5.2 ms/frame (86 s / 16,651 frames at epoch 3), and 1.2 ms per dense record on CPU. Writing bodies once
per frame would cut bytes and time by about 40% at dense epochs. The per-record `flush` is not needed for resume
correctness, because `capture_resume_v4.reuse_episode` only reuses closed, complete matches. However, it is inside
the measured service clock today.

(c) About 2–3 ms/frame.

(d) 2 h, plus a schema change.

(e) The record bytes change (new schema), so equality must be checked at the parsed-record level.

(f) Frozen schema: new path only. Not worth it before #1 and #2.

### #10: Training throughput (not on the critical path)

(a) `l1/train_v4.py`, `data_v4.py`.

(b) Batch = 1 window (16 frames): the GPU loop runs at 19.8 windows/s and the full loop at 13.9 windows/s. The whole
formal fit took 11.5 min.

(c) Batch 8 + channels_last could give 3–5× more GPU throughput, but it saves under 10 min.

(d) 2–4 h.

(e) It changes the optimization recipe, so it is not equivalent.

(f) Frozen T7 recipe: only for a future v5 registration. **Do not pursue now.**

## 2. Quick wins (<2 h each)

1. **Confirm #1 now** (15 min, read-only): for any completed capture, check the last frame of each match. If
   `available_timestamp_ms − timestamp_ms` is greater than about 500 ms, stop treating capture clocks as scoring
   input until attributable clocks exist.
2. **Install `DecoderAdapter` in `V4Perception`** (#3), about 1.5–2 h plus a Mac parity run. It removes about
   20 ms/frame of syncs.
3. **Admit identical-birth tail dedupe** (`VectorSharedModel`, exact by input equality) as part of #2's candidate,
   about 1 h plus the existing gate.
4. **Blocking waits instead of 2–3 ms polls** in the live runtime (#7), about 1–2 h, −4..5 ms p50.
5. **Drop the `deepcopy`** in the grid decoder as a new-file variant (#8), 0.5 h.
6. **Correctness, not speed:** `V4Perception` constructs `PixelPerception` without `body_threshold`, so it defaults
   to 0.5. The validation-selected body threshold must be plumbed through the calibration JSON, or the live P1
   silently differs from the sealed selection. 15 min.

## 3. Measurements (127x08 CPU, 1 thread, nice 19, synthetic random-weight inputs, real shapes)

| Item | Result |
|---|---|
| `prepare_pixels` | 0.69 ms |
| `encode` (backbone+body+HUD) | 160 ms; backbone alone 158 ms |
| HUD-only `hud(stem(hud))` | **2.1 ms, bit-equal to encode's HUD outputs** |
| Temporal full / prefix / tail | 101 / 85 / 5.0 ms; prefix+tail **bit-equal** to forward |
| Spatial on 16 vs 1 frame | 17.8 vs 1.15 ms; batch-1 cached spatial **bit-equal** to batch-16 (CPU) |
| Latest-only attention + cached spatial | 23.0 ms; max abs diff logits 9.5e-7, age 3.7e-4 ms (not bit-exact) |
| `decode_bodies` (CPU tensors, so no sync cost) | 3.7–5.4 ms (fixed sigmoid/maxpool/topk cost dominates on CPU) |
| `BodyTracker.update`, 10/30/60/128 detections | 0.05 / 0.15 / 0.49 / 2.1 ms (thr 0.1); not a bottleneck |
| `birth_maps` (20 births, 200 sources) | 0.87 ms |
| Dense record json+gzip1+flush | 1.22 ms (90.9 KB JSON) |
| Grid: `json.loads` dense / `deepcopy` bodies / shallow | 0.75 / 0.55 / 0.01 ms |

Repo receipts used: `vectorized-capture-status-2338.json` (epoch 1/3/20 profiles), `runtime-epoch24-r1.json`,
`synthetic-probe-r1.json`, `batch-tail-probe-r1.json` (batching is not exact), `persisted-verified-r2.json`
(epoch 1 has 0 predictions), `runtime-mac-latency.json`, `formal-20261008/t7-formal-throughput` (via RESULTS.md).

## 4. Things not to do

- Do not batch the 9 branch tails or several matches through one forward and call it exact. Amendment 08 measured
  heatmap max error 8.1e-4 and age 0.14 ms even with deterministic cuDNN.
- Do not use fp16 on the fleet reference path (selection numerics).
- Do not run captures on CPU hosts. CPU numerics are not admissible against the CUDA reference, and 1-thread CPU
  is about 300 ms/frame.
- Do not use a per-user CUDA MPS daemon on shared lab GPUs to raise packed concurrency. It blocks other users' CUDA
  contexts. Packing more processes per GPU also inflates the current (#1) clocks further.
- Do not request 540×1140 directly from the emulator gRPC to save transfer. That replaces the
  `public_pixels`/INTER_AREA resampler that the training pixels went through, which is a distribution change.

## 5. Ten-line summary

1. Training is not a bottleneck: the T7 formal fit took 692 s. All remaining wall time is validation capture plus Mac live latency.
2. BLOCKING: the shared 9-branch capture measures each branch's "service" as the whole 9-branch frame period (75–82 ms > 50 ms), so FIFO availability falls behind by tens of seconds per match.
3. Because of that lag, event recall at 500 ms collapses for every epoch with real predictions. The equality gates missed it because epoch 1 has 0 predictions. Confirm in 15 min, then switch to attributable per-branch clocks (2–3 h plus an amendment).
4. Capture: hoist the per-frame shared work (prepare/H2D/HUD/ring/equality syncs) out of the 9-branch loop and dedupe identical-birth tails. This is exact, takes 4–6 h and should give ~1.8–2.5× on runtime_step.
5. Live P1: port the already-proven vectorized decoder. The scalar per-peak syncs cost ~22 ms/frame on CUDA at dense epochs, likely more on MPS. About 2 h, exact.
6. Live P4 in v4 mode has no direct HUD reader, and P1's HUD arrives at ≥~61 ms age vs the 60 ms freshness bound, so commands can expire. Add a 2.1 ms CPU v4 HUD-only reader (3–4 h, before the verifier re-test).
7. The temporal head recomputes 16 frames to read one token: 101 → 23 ms on CPU (−30% of model compute). It is not bit-exact, so put it into the CoreML/MPS export path with decision-level parity.
8. Smaller exact wins: overlap the temporal prefix with the CPU tracker (1–5 ms), blocking IPC instead of 2–3 ms polls (−4–5 ms p50), and drop the grid decoder's deepcopy (−30–40% grid CPU).
9. Freeze rules: never edit l1_v4.py or pinned capture/grid sources; use adapters or new files plus the equality gates. Live runtime edits must land before the T9 smoke and E4.
10. Correctness note: live V4Perception ignores the selected body threshold (defaults to 0.5); plumb it through the calibration JSON.
