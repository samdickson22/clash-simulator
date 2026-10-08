# T6 CUDA control: engineering shakedown, validation only

93 frozen-inventory matches (83 train / 10 validation), 83,763 converted frames
and 4,560 roundtripped deployment labels, converted using the unchanged
v4 producer converter. All per-match roundtrip checks passed. No v4 heldout payload
was opened. The separate adapter provides the legacy evaluator's expected layout,
protocol-2 marker and integer-millisecond input timestamps, preserving raw times.

CUDA port preserves v3 architecture, v2 warm-start weights, optimizer, loss,
3-positive/1-negative sampling, augmentation, gradients and default MPS behavior.
The only additional operational option is an explicit disk-cache budget: default
450MiB, raised to 4096MiB for the larger corpus. No data was deleted.

The shakedown fitted **one epoch / 40 steps**, seed 6107. Mean loss 7.15737; optimizer
loop 5.31s. This is 1/240 of the formal 24x400-step schedule. It demonstrates the
pipeline, not convergence or collection comparability with the published model.

| Validation endpoint, regular ~10FPS input | Result |
|---|---:|
| Opponent correct-card/side recall at 500ms | 22/259 = 8.494% |
| Opponent precision | 22/42 = 52.381% |
| Opponent false positives / misses | 20 / 237 |
| Both-side recall | 179/560 = 31.964% |
| Both-side precision | 179/228 = 78.509% |
| Both-side placement within one tile, all truth | 65/560 = 11.607% |
| Derived opponent elixir MAE | 3.3267 |
| Nominal 90% interval coverage / mean width | 66.963% / 7.5833 |
| Concentrated-hand query count | 0 / 1,011 |
| Inference throughput / per-frame p95 | 20.264 FPS / 67.575ms |

Thresholds were selected by the unchanged v3 evaluator on validation only.
FIFO processing completion counts against the deadline. These CUDA timings
exclude capture and do not establish the Mac gate. All historical v3 admission
gates fail here, including its legacy compositor-certification gate (v4 dropped
that gate; do not silently rewrite the control evaluator).

Important timing limitation: converted event brackets have p95 **208.16ms** for
opponent plays. The control uses the unchanged conservative matcher: prediction
after the upper bracket, within 500ms of the lower bracket. Exact native execution
ticks are retained in the source, but converter bracketing is coarser than the
published v3 timing residual (~27ms). Formal results must report this collection/
label-timing shift; this short fit cannot establish comparability with published
180/280 recall and 90 false positives.

The empirical-gap replay uses the historical L2 public-frame intervals (seed
6109), keeps the same checkpoint and regular-validation thresholds, and does not
retune on gaps. Completed 3,692 selected frames; source distribution has 60,586
intervals and p95 exactly 610ms. Opponent recall **4/259 = 1.544%**, precision
**4/12 = 33.333%**, eight false positives. Both-side recall **60/560 = 10.714%**,
precision **60/143 = 41.958%**. Processing 16.157 FPS, p95 76.596ms, including
reading past dropped video frames. This reproduces gap sensitivity diagnostically;
it is not a converged-model comparison. Receipt: ../l1/receipts/t6-gap-validation.json.

Artifacts on 127x01:
- Corpus: `/mpac/sdicks02/repos/clasher-v4-training/t6-shake-1`.
- Current model/inference/evaluation: `.../clasher-v4-training/t6-run-2`.
- Gap replay: `.../clasher-v4-training/t6-gap-1`.
- Retained failed attempts: t6-run-1, validation-inference-missing-dill,
  validation-inference-fractional-ms. See ../l1/INCIDENTS.md.
- Compact mirrored results: ../l1/receipts/t6-validation.json,
  t6-validation-selection.json, t6-training.jsonl and t6-conversion.json.

Formal commands and guarded admission are in ../l1/RUNBOOK.md. Formal runs are
prepared, not started. They require authentic T1 completion evidence and the
frozen population/registration checks. All heldout scoring remains disabled.
