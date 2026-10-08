# T4 model implementation

2026-10-08 UTC: active implementation on 127x05. No commits; no heldout scoring.

- Read the entire design and frozen heldout spec (read-only from 127x01).
- T3-PASS absent at first check; T0–T3 data work is still active. GPU shakedown awaits qualification.
- Building a fresh plain-PyTorch set transformer, shared public feature adapter, weighted losses,
  resumable trainer, dev evaluator, CPU proposal/export and synthetic verification.
- CPU-only isolated test environment: `/mpac/sdicks02/tmp/imitation-model-cpu` (Torch 2.7.1+cpu).
- Important spec clarification: training uses §2.7 weights; **reported metrics use unit natural
  supervised-row weights**, per the frozen JSON. All waits retained for evaluation.
- Design token SHA prefix differs from current contract_v5.py: record and verify the actual full
  token hash in assets/checkpoints rather than trusting the abbreviated prose prefix.
- No GPU jobs, full v1 training, eval/eval_ood scoring or Mac commands have run.

Implementation checkpoint 02:51Z:
- 2,399,898 parameters at the specified d192/4-layer/6-head/FFN768/tile128 size.
- 11 CPU tests pass (including optimizer-state replay and synthetic dev calibration/export).
- Full 1000-call-per-size single-core CPU bench: p50/p99 10.20/10.89 ms at
  10 entities; 12.06/13.08 ms at 25; 12.31/12.60 ms at 64. Raw receipt in
  `imitation/model/receipts/latency-127x05.json`. Synthetic inputs, random weights,
  entire feature adapter + top8 included. Tile-width reduction unnecessary.
- T3 DATA-CONTRACT.md has appeared. Implementing its exact adapter: big-endian
  mask bits, integer-ms refills, split history arrays, 8 ability-history slots,
  current-row-inclusive intent, 0.05..10s log bins. Intent targets never inputs.
- Scheduled 10-minute receipt checks are active in this same thread, next run
  2026-10-08T03:00:50.245Z; deadline 2026-10-09T14:30:00Z. Task id:
  `scheduled-task:command:mcp:c588a151-27f6-471c-bafb-661cddc13f03:schedule-task:clasher-imitation-t4-t3-poll-20261008`.
- T3 remains absent. No real fitting or GPU work yet.

03:02Z implementation status:
- 13 tests pass in 3.59s, including actual-T3-format adapter replica, all offline
  A1–A4 comparison functions, frequency-count evaluation, full synthetic dev
  calibration/export and checkpoint replay.
- Separate CLI smoke: 32-row train/dev fixture, two optimizer steps; resume from
  step 1 produced **bit-identical model AND EMA tensors** at step 2. Evaluator
  completed all dev metrics/slices, calibration, bootstrap and policy.ts export.
  Evidence: `imitation/model/receipts/cpu-integration.json`.
- Actual T3 adapter is implemented from the published contract, but remains
  unverified against finalized real data. It never imports the legacy BC or
  T3 baseline-scoring code; train-frequency counts and already-computed dev
  P16 summary are accepted as independent baseline inputs.
- CPU API, scripted tensor export and deployment usage documented in
  `imitation/model/README.md`. No Mac command run.
- Deviations/clarifications: add 128-token bucket to avoid discarding entities;
  intent classes canonicalize deck order; correctly distinguish censor/event
  boundary bins; preserve older checkpoints under the hard no-delete rule;
  use a recorded 100k uniform-dev-row calibration reservoir; explicit default
  patience=3 and ECE bins=10. No tile-width reduction or architecture shrink.
- Real GPU rows/s, loss curve and GPU memory remain **pending**, not inferred
  from the synthetic CPU checks. T5/full v1 and eval/eval_ood remain unrun by T4.

Handoff checkpoint: final test suite **13 passed**; current T3 receipt check is
still PENDING. Scheduler verified enabled, last dispatch succeeded, next check
2026-10-08T03:10:54.314Z. Current wait state is in
`imitation/model/receipts/t3-wait.json`. Resume this same task on receipt arrival;
T4 is not complete until the real 127x04 shakedown and dev evaluation are measured.
No GPU files/jobs have been staged or launched yet, so no remote job to duplicate.

Latest scheduled receipt check: 2026-10-08T03:04:54.587144+00:00 — T3_PENDING; no GPU job launched.
