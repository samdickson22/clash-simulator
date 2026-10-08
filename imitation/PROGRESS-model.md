# T4 model implementation

**Current: expanded T4 COMPLETE / PASS (2026-10-08).** Shakedown and throughput
receipts are below; the continuation schedule is disabled. T5 should use
`imitation/model/receipts/throughput-pass.json`, one run per A6000.
The chronological entries below preserve earlier pending/failure states.

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


07:51Z inspection: subset stage including full dev validation completed;
wrapper entered the 1,000-row overfit at 07:51:04Z. Observed step 4 loss
9.65022. Verified launcher PID 2398593 remains active, nice 10, no exit
receipt. No new job launched. Full metric evaluator follows overfit.


08:01Z inspection: overfit reached **200 steps / 200,000 row exposures**
on the fixed 1,000 train rows. Loss decreased from 9.65022 at step 4 to
**7.34967** at step 200. Measured **2,536.27 rows/s** including loader;
GPU training peak allocated/reserved **402.73 / 498 MiB**. Full dev validation
is still part of the overfit stage; launcher PID 2398593 active, no exit receipt.
Full metric evaluator remains next. No duplicate job launched.


08:21Z inspection: both training stages and their full dev validation have
completed. The full metric evaluator started at **08:13:01Z**, using subset
`best-dev-step-00000008.pt`, dev only, with calibration and default 10,000
perspective bootstraps. Verified launcher PID 2398593 is active, nice 10;
no exit receipt. No duplicate job launched.



08:49Z coordinator scope expansion: **T4 now includes a throughput pass before T5**.
- Let current 0727Z shakedown finish and record PASS/FAIL first. Its dev evaluator
  was still active at the latest inspection; no duplicate/optimization job launched.
- Then raise microbatch to largest 1024–8192 fitting >=8 GB GPU headroom while
  retaining effective batch 8192 and the recipe. Verify fixed-batch optimizer
  equivalence against micro64 with documented bf16 tolerance and dropout control.
- Vectorize batch features and evaluator, use bounded workers/pinning/prefetch;
  verify dev-subset metrics against original evaluator within float tolerance.
- Measure loader-inclusive rows/s for one and two concurrent A6000 runs, target
  >=8k. Publish receipts/throughput-pass.json with final microbatch and full code
  hash manifest only after measured qualification. T5 is waiting for this receipt.
- Leases end 2026-10-09 05:30Z. Our work stays on permitted home hosts. The
  existing 10-minute schedule now carries this expanded scope; do not disable it
  merely because the original shakedown finishes. Next scheduled check 08:51:07Z.


09:12Z shakedown **PASS**, exit0, completed09:05:52Z. Receipts copied to
`imitation/model/receipts/shakedown-20261008T0727Z/` (small JSON/logs only).
Subset loss 9.753533 → 9.600328; overfit 9.649827 → 7.349667. Full2,759,722-row dev
evaluator, calibration,10,000-perspective bootstrap and TorchScript export
completed. Throughput implementation starts now; no optimization job yet.

Throughput qualification launched in fresh owned snapshot0921Z: label
`t4-throughput-qualify-20261008T0921Z`, launcher2444705, source/run under
`/mpac/sdicks02/tmp/t4-throughput-20261008T0921Z`. No users/other workers/GPU
jobs before launch, nice10 fleet_run.sh. Explicit own-file rsync-c and hashes
in source-throughput-20261008T0921Z.json. **16 CPU tests passed in4.01s**.
Vectorized batch adapter, pinned/prefetched loader, one-transfer row metrics,
teacher-forced dev joint NLL, and signal exit before dev validation implemented.
Benchmark receipt is not yet published; qualification still running.

First throughput qualification0921Z passed numerical tests: features exact;
metric rows/ECE/bootstrap exact; micro4096 vs64 update relativeL2=.02919,
gradient relativeL2=.003866,p99 parameterabs=2.98e-7. Micro8192 OOM;4096
reserved35.59GB and step-only5494rows/s, belowtarget. No throughputPASS.
Second snapshot0924Z now tests block-sparse numeric GEMM (GPU only) and
tile head only on supervised plays, preserving exact objective and inference.
17 CPU tests pass4.10s including sparse-tile loss/gradient equivalence and
TorchScript export. Numerical GPU comparison now uses original shakedown
network+optimizer at micro64, not only the optimized implementation.

Throughput0930Z:1024-row-granularity memory sweep selected **micro7168**,
8192 rejected (<8GiB headroom). Original micro64 vs7168: updateL2=.02555,
gradientL2=.004546,p99 parameterabs=2.44e-7; qualified. Dev8192-row scoring
4169→9926rows/s; exact discrete card/tile/top8, continuous bf16 differences
(max jointNLL=.001466; mean=.00003354);3 gate-argmax ties changed.
Single64-step measurement: **12,188.05rows/s loader-inclusive**, cold11,447.60;
peakallocated28.373GB/reserved31.541GB. CPU p99 at78entities11.647ms.
Final snapshot0935Z (source receipt recorded) now runs qualification then
single+two-concurrent benchmarks with explicit driver free-memory monitoring.
Label`t4-throughput-final-20261008T0935Z`, launcher2448478, nice10, no users
or other workers at launch, planned<=18 processes. No throughputPASS yet.
18 CPU tests passed4.15s. No full runs/heldout scoring.

Final throughput qualification **PASS** (job exit0 at09:36:14Z):
- Published `imitation/model/receipts/throughput-pass.json`. Receipt SHA256
  `5c7e83bacc92096a30520ccdaf002321b753542a7afc489e57183df865fc7229`.
- Qualified Python code SHA256
  `301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`,
  verified identical on05 and04. Full20-file Python manifest plus immutable
  staged-source manifest included. README subsequently records final results;
  its separate current hash is included. No runtime code changed after the run.
- **One run per GPU recommended**: effective8192, micro7168,4loader workers,
  pinning and prefetch.64measured steps plus2warmups: **12,154.13rows/s**,
  cold-loader/startup-inclusive11,415.55. Peak allocated28,372,961,280bytes;
  reserved31,541,166,080bytes. Driver max31,342MiB used; minimum17,340MiB free.
- Two concurrent runs: micro3072/workers4 each; **5,696.55 +5,697.78 =
  11,394.33rows/s aggregate**. Each misses8k and aggregate is lower than single;
  do not pack two expecting a speedup. Driver peak28,407MiB/min free20,275MiB.
- Micro7168 was largest fitting candidate on1024-row grid; full8192 left only
  6.78GB allocator headroom and was rejected. No cache generated/data changed.
- Old network+optimizer micro64 vs new7168: update relativeL2=.02555 (tol.05),
  clipped-gradient relativeL2=.004546 (tol.02), max parameterabs=.00059792
  (tol.000601),p99abs=2.44e-7. Paired3072 also passes. Dropout disabled ONLY
  for equivalence; production remains.1 and effectivebatch/recipe unchanged.
-512realdev adapter rows including78entities match scalar features/labels
  bit-exactly. All metric rows match original formulas on identical logits;
  same seeded perspective bootstrap within1e-12.8192-row end-to-end bf16 dev
  comparison: card/top3/tile-error/within1/top8 exact; max jointNLL difference
  .001466,mean.00003354;3gate-argmax ties changed. Continuous row tolerance
  .01 and metric-mean tolerance.001 are recorded, not a bit-exactness claim.
  Scoring3,898.94→9,746.51rows/s on final code.
- **18 CPU tests pass4.15s**, including new batch/scalar and sparse-tile
  gradient equivalence and bootstrap identity. Separate CLI resume model+EMA
  bit-exact; verified-child SIGTERM checkpoints/exits without dev. TorchScript
  retains two-argument forward. CPU p50/p99ms (1000calls,core0):
  10entities7.106/7.371;25entities7.942/8.309;64entities10.386/10.860;
  78entities11.336/11.647. Parameters remain**2,254,938**.
- Original shakedown: subsetloss9.753533→9.600328,2,291.03rows/s; overfit
  9.649827→7.349667,2,536.27rows/s. Full2,759,722-row dev report, calibration,
  10,000perspective bootstraps and TS export passed. This is pipeline sanity,
  not an offline gate(a) quality claim. Initial64-entity failure preserved.
- New files batching.py,throughput.py,throughput_runs.py; network/train/runner/
  evaluate and tests updated; receipts+README+this progress current. GPU-only
  typed numeric GEMM and supervised-play-only tile work preserve objective.
  Predeclared tile64 latency fallback and entitycap128 remain documented.
- No T5/fullv1, eval/eval_ood or Mac execution; no commits/deletions.
  All T4 fleet jobs exited. Temporary10-minute schedule disabled on completion.
