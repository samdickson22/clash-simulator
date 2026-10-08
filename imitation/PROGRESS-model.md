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


06:51–06:57Z T3 release inspection:
- T3 PASS published 06:42:32Z, releasing store/frequency baseline for training;
  P16 baseline is pending and is not a training prerequisite per its coordinator decision.
- Root store SHA256: `1acf6b5875091e009c18e598a71714016b9833b6cc626032e0fa676ccdac5c2f`.
  Actual train/dev manifests match the implemented schema: 53,989,262 / 2,759,722
  rows, 69,380 / 3,546 perspectives. Inspected manifests only; no heldout scoring.
- Added exact array shape/dtype checks and bound the PASS receipt to store/role
  hashes and role counts. Light suite remains **13 passed in 3.82s**.
- 127x04: no logged-in users or GPU compute job; 77 existing search Python
  processes plus 2 active store-copy rsync processes. Probe itself brought the
  conservative worker count to 80. Train manifest and local T3 receipts absent.
  Wait for the data owner’s copy/verification; do not launch or duplicate it.
- No T4 source snapshot or GPU job has been staged/launched. Next scheduler
  invocation should read PASS and its referenced T3-COPIES receipt, verify 04
  copy availability, recheck budget, then continue the one-seed shakedown.


07:14Z detached shakedown launched:
- T3-COPIES now certifies **127x04 store passed**, 254 files / 86,075,227,942
  bytes, matching the qualified manifest. Its overall status is still false
  because other copies are pending; the required 04 store is verified.
- 04 became idle: who empty, zero existing worker/GPU compute processes.
  Staged only our explicit source-file list with rsync -c into the fresh
  `/mpac/sdicks02/tmp/t4-shakedown-20261008T0714Z/source`. Source hashes are
  in `imitation/model/receipts/source-20261008T0714Z.json`. Qualification is
  our byte-exact captured receipt (SHA256 `6b335ec4470215922c1ff346da18535fe3f8e3eb9e88dfe109d16d1f86b9472c`).
- New `imitation/model/shakedown.py` sequentially builds frozen-runtime assets,
  validates 256 real rows per train/dev role, runs seed 2903 at .2 epoch of
  2% train perspectives, overfits 1,000 train rows for 200 steps, and runs
  full dev evaluation/calibration/10,000-cluster bootstrap/export. No heldout.
- Light suite **13 passed in 3.83s** before staging.
- Launched via fleet_run.sh at 07:14:29Z, label `t4-shakedown-20261008T0714Z`,
  verified launcher PID **2393301**, nice 10. Own log/exit are under
  `/mpac/sdicks02/jobs/clasher/`; run artifacts under the snapshot sibling
  `run/`. First inspection: stage `preflight`, no exit receipt yet.
- This is an active job, not a success claim. Next scheduled invocation must
  inspect this job once and collect its measured results; **do not duplicate**.


07:21Z first shakedown failure and technical rerun:
- First job exited 1 in dev loading after **8 steps / 65,519 train rows**.
  The real data contains >64 entities: train maximum 74 (112 rows above 64),
  dev maximum 78 (10 rows above 64). Preflight samples had missed these rare rows.
- Initial d128 subset loss 9.73854 → 9.58864, including-loader throughput
  **2,131.94 rows/s**, peak GPU allocated/reserved **530.78 / 734 MiB**.
  These are measured partial-run results; overfit and full dev did not run.
  Original logs/receipts retained locally in receipts/shakedown-20261008T0714Z/.
- Fix: retain up to the full v5 cap of 128 entities and add a 192-token bucket.
  Preflight now checks the maximum-entity row too. Save a resumable checkpoint
  before validation; the failed initial run had no checkpoint to recover.
- Required latency fallback: the original d128 model measured 17.45 ms p99
  at 78 entities. Tile width 64 alone measured 15.07 ms; unpadded single-row
  inference removes unnecessary training-bucket padding with tested equivalent
  logits. Final model **2,254,938 parameters**, trunk unchanged.
- Final CPU p50/p99 ms (1000 calls each, core 0, feature build+top8):
  10 entities **7.07/7.55**, 25 **7.83/8.15**, 64 **10.26/10.60**,
  78 **11.26/11.56**. Receipt: latency-127x05-final.json.
  **15 tests passed in 3.72s**, including 128-entity preservation and padded/
  unpadded equality. This deviation is the design’s predeclared latency fallback.
- Fresh owned source/run: `/mpac/sdicks02/tmp/t4-shakedown-20261008T0727Z`.
  Launched via fleet_run.sh after who empty, zero other workers and empty GPU.
  Label `t4-shakedown-20261008T0727Z`, verified launcher PID **2398593**, nice 10.
  Same seed 2903/subset/overfit recipe; tile width 64 is explicit. This job is
  active; inspect its own log/exit once next poll and do not launch a duplicate.


07:31Z running-job inspection: verified PID 2398593 remains active, nice 10;
no exit receipt. The d64 subset finished **8 steps / 65,519 rows**, last loss
**9.60033**, measured **2,291.03 rows/s** including loader; GPU training peak
allocated/reserved **471.22 / 642 MiB**. Wrapper remains in subset stage
(the trainer performs full dev validation before overfit). No duplicate job.

Latest scheduled receipt check: 2026-10-08T07:41:31.182191+00:00 — SHAKEDOWN_RUNNING; verified own launcher PID 2398593 remains active at nice 10, subset stage, no exit receipt.
