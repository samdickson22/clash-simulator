# Registered driver candidate, 2026-10-22

Review candidate only. No engine games, registered training, GPU qualification,
SSH, watcher changes, deployment, or main-branch landing were performed by this
implementation task. R41 lifecycle and R42 training-precision components are
integrated; their component approvals do not approve this driver.

The parent registration at `4f3c8b0bf` supplies the current resource amendment.
Three BC seeds continue on08/01/02 without yield requests or signals. The
registered placements remain M01/S10002. Qualification-only fallback placements
are M09/S10012 under the existing R37 watchers. The driver rejects leased configs
in registered mode. Hosts13–16 cannot hold this entire process tree under their
32-process total cap, and are not selected by this implementation.

## Entry points and budgets

`run_registered_rl.py` provides `audit`, `audit-soak`, `run`, `soak`, `worker`,
and `evaluate`. Workers and evaluation bootstrap the exact calibrated runtime
before importing bot modules. They use the separate pinned actor-source root;
pretrain code comes from this candidate. Module origins are checked after games.

Registered mode has exactly262144 generated acting-seat polls per update,
32 updates including three critic warmups, minibatch2048, microbatch128,
two epochs and the existing learner objective/optimizer settings. The32 persistent
worker processes each have8192 polls per update. Each has one CPU math thread.
The parent owns the GPU learner and one IPC adapter thread per worker.

An active game, Session, causal history and sampling RNG remain in the same
worker across quota barriers. A bounded NPY publication is acknowledged only
after the parent closes its mappings and the coordinator returns its permit.
The callback may block at the exact global barrier; that is not a recycle point.
Only true terminal completion after close and acknowledged publications permits
`ActorCheckpoint.capture`. The parent independently verifies the record, SHA,
cursor, policy, counters and exact PID/start, waits for process exit, and starts
the successor with the canonical record and one run-wide `out/claims` directory.
One-use restore retains lifetime budgets/counters. Disk run/engine resume and
midgame replay are not qualified. Search descendants must be gone/reaped before
a successor can start; a remaining live descendant aborts the seed.

The separate `soak` entry is **not a counted registered prefix**. Its maximum is
128 updates at the same262144 polls/update and unchanged microbatch/objective.
The six-hour clock begins after all32 first worker-ready messages. At six hours
the parent closes its own exposure and stops the qualification; generated,
accepted, trained and unfinished-tail counts remain explicit. Exhausting the
finite128-update cap before six hours is a failure, without extension/top-up.
An early reclaim/resource/engine failure is also a failure. A completed exposure
is labelled `completed-exposure-pending-review`, never GO. No qualification rows
or checkpoints may be promoted to a registered run.

## Resource admission

The parent holds a singleton host/GPU lock, sets the allocator fraction to
43.5GiB/physical capacity, and checks GPU memory before allocating the model.
Admission requires both pinned R40 max-shape evidence and a pinned **full CUDA
process** peak, including context/non-allocator memory. R40 allocator-reserved
19.44GiB M /8.95GiB S100 alone cannot admit co-location. Physical free memory
must cover the measured full RL peak plus8GiB at admission. An independent
`nvidia-smi` monitor samples physical free memory each second with a two-second
query timeout, and aborts only this runner when it falls below8GiB. BC is not
signalled or paused. A learner stop check runs before microbatches/forwards.

A separate parent monitor samples exact worker PID/start and RSS, including
blocked acknowledgements: worker RSS<=2GiB, host MemAvailable>=32GiB,
load1<=90, nice>=10 and math threads1. Generation counters use bounded flock
acquisition and are read again after reap. Unknown counters remain labelled
unknown. R37 lease environment is inherited unchanged; the parent independently
polls its lease adapter, so a blocked worker is not the only reclaim observer.
The external R37 watcher remains the final lease/process/PSS enforcer.

The queue reserves a conservative whole-update disk budget. Before simultaneous
mapping, only this process's soft RLIMIT_NOFILE is raised, within the hard limit,
and the required count/old/new limits are logged. Actual loads recheck capacity;
short-game fragmentation cannot silently exhaust descriptors. The CPU full-queue
probe is separate from the real32-actor soak and generates no experiment rows.

## Frozen league, populations and evaluation

Case-index hashes pair seed, seat, league family, deck/level draws and shuffle
across sizes. Mixtures are30 current/20 reservoir/15 ownBC/15 HP1v330/15 LIVE/
5 scripts; decks50 Hog/30 frequency-meta/20 random; opponent levels70 empirical/
20 adjacent/10 stress. Current is frozen at game start. The proposed reservoir
contains milestones0/10/20/30 available at that start, capped at16 entries.
Actual opponent version and case are saved with every game.

**Registered gate still open:** game starts can occur at different update versions
across sizes. Thus current/reservoir snapshot indices are not proven matched.
Registered audit requires an explicit source/config-bound amendment accepting
this candidate's `paired-case-draws-game-start-version-v1` protocol. No such
amendment is adopted here. Retaining exact matching requires a redesigned paired
protocol and another review. Qualification does not require that amendment.

LIVE is the parent's explicitly confirmed existing serial factory:
`bot.rl.actor.make_opponent`,
`livesearch:LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-RF-pt5-wint`,
f1a2 step001200 SHA0c03f79f..., calibration SHAe805d498...,
threshold0.6444047689437866, belief
`fullpool:11433651:freq=b53b02a1fde4`, native_threads1/pool0/chunks4/no wall.
This is the frozen deployed opponent. The BC LIVE-K4CW-r16-fp surrogate is not
selected. HP1 is exact recovery04v330 SHA73bbbd86... through the existing
`student:<checkpoint>@0.019753086419753086` factory. Missing artifacts fail.

The population builder uses all seven hash-verified original royal-arena logs
plus the historical pekkas-playhouse adjacent log. In the draft training pool,
22/87 royal rows remain:42 prior-evaluation physical runs and23 incomplete rows
are excluded. Adjacent retains16/23:one evaluation run and six incomplete rows
are excluded. The separate evaluation population uses the42+1 eligible withheld
physical profiles. Physical source IDs are disjoint; incomplete levels are never
filled with medians. Synthetic stress levels12..16, meta weights and random
card-level rules are explicit draft registration choices requiring review.
The prior bank/run exclusion inventory still needs a completeness audit against
all BC/final/DEV physical identities; the available three banks are not claimed
to be a complete historical inventory by this implementation.

The freezer emits fresh1600 primary and200 DEV cases per seed, current LIVE
only, paired across both sizes and their own BC starts. DEV uses the same200
assignments at0/10/20/30. Engine seeds use disjoint training/evaluation namespaces
and exclude the supplied prior-bank inventory. Evaluation constructs exact-dtype
models from `model_cfg` checkpoints, without the serving FP32 loader or a serving
conversion. Defense/spell audits use the existing calculations and all actual
input files are hash-bound, at0/10/20/30 and final32. Old19k-anchor audit results
are not reused. Every evaluation assignment has one attempt; failures remain
missing, draws are not wins, and paired all-assigned bounds/BC bootstrap logic
are shared. Evaluation currently runs serially, so its wall time is substantial.

Operational rejections preserve sampled rows and count once. Training telemetry
reports overall/per-card/per-snapshot counts. Evaluation alerts compare only
matched valid-case exposures with the size's own fresh BC baseline; no positive
rejection rate stops training. All other engine/contract failures stop the seed.

## Concrete inputs and commands

Local05 draft bundle:
`/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/registered-driver-inputs-r1/bundle-r3.json`.
It pins current registration documents from parent4f3c8b0bf. Its `configs-r3`
directory contains six registered configs plus two soak-only fallback configs.
Missing GO and full-process-memory evidence have explicit `PENDING` references;
none are fabricated. Already-relocated fallback files are alongside the bundle:
`SOAK-M-127x09-relocated.json` and `SOAK-S100-127x12-relocated.json`.
All remaining pinned raw/population/bank/audit/document files must also be staged.
Readiness receipts alone do not include those inputs or approve an engine job.

Parent-owned commands, from the reviewed driver checkout (not executed here):

```bash
env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' nice -n 10 "$PYTHON" bot/pretrain_v1/checks/qualify_rl_queue.py --out "$FRESH_QUEUE_OUT"
env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' nice -n 10 "$PYTHON" bot/pretrain_v1/run_registered_rl.py audit-soak --config "$SOAK_CONFIG"
env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nice -n 10 "$PYTHON" bot/pretrain_v1/run_registered_rl.py soak --config "$SOAK_CONFIG" --out "$FRESH_SOAK_OUT"
env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' nice -n 10 "$PYTHON" bot/pretrain_v1/run_registered_rl.py audit --config "$REGISTERED_CONFIG"
env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 nice -n 10 "$PYTHON" bot/pretrain_v1/run_registered_rl.py run --config "$REGISTERED_CONFIG" --out "$FRESH_REGISTERED_OUT"
```

On09/12, `PYTHON` is
`/mpac/sdicks02/repos/clasher-pv1-ready-20261022/python/bin/python3.12` and
`PYTHONHOME=/mpac/sdicks02/repos/clasher-pv1-ready-20261022/python` must be exported.
Preserve the R37 job's inherited lease variables and GPU mask. Admission occurs
through the existing lease owner; these commands do not bypass its caps.
On01/02 use the qualified `/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python`.
Registered starts remain sequential per size/seed under the parent allocation.
The `run` entry evaluates completed training automatically on CPU. A failed
evaluation is preserved; automatic retry/resume is not implemented.

Freeze a reviewed input bundle with:
`python bot/pretrain_v1/prepare_registered_rl.py --bundle BUNDLE --out FRESH_DIR`.
Relocate a fallback config with the same tool's `--config CONFIG --readiness
RECEIPT --relocated-references MAPPING --out FRESH_CONFIG` arguments; SHA identities
must match the staging receipt. Generate the final equal-seed report with
`summarize_registered_rl.py --M M_SEED1 M_SEED2 M_SEED3 --S100 S_SEED1 S_SEED2
S_SEED3 --out FRESH_JSON`. Stopped arms remain explicitly unequal-budget evidence.

## Remaining gates

Fresh independent Sol high review of this exact clean commit/config is required.
The full262144-row host queue exposure, complete full-CUDA-process memory
measurement, real32-actor admission and six-hour RSS/PSS/recycle soak are pending.
Recycling equivalence needs production-shape review in addition to R41's CPU
fixtures. Source-bound precision registration receipts must bind the integrated
source to R42/R38 evidence; strict2e-6 remains unchanged. Review must also accept
the frozen population rules, complete the physical/seed exclusion inventory, and
verify all staged inputs. The paired snapshot-index issue blocks registered GO
even if the separate qualification passes. No deployment is included.
