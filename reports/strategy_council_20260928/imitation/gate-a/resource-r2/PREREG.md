# Gate (a): technical continuation registration r2

Frozen BEFORE any r2 continuation/restart; initial T5 training has already
started under the original immutable pretraining registration. No held-out
model inference has occurred. Original PREREG SHA256 `71335325d383282bfe8effd6bf550ef322713520bb6119b8ed363e3869835cce`.
Original executable manifest SHA256 `934516a0ae3a2d950a676d6c35f0d310ead7ad951ec2c776967ccbd21a7e7f9f`.

This technical amendment supersedes ONLY execution resource handling and
checkpoint provenance. All five scientific runs, seeds, architecture, losses,
effective batch, primary microbatch, sampler, optimizer, selection/calibration,
bootstrap, descriptive scope and A1–A4 bars remain unchanged. Failed segments
and original checkpoints/source snapshots are retained, never deleted.

Revised executable manifest SHA256 `2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13`.
It pins every actual staged source and the parent registration. T4 code remains
`301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`; throughput receipt remains
`5c7e83bacc92096a30520ccdaf002321b753542a7afc489e57183df865fc7229`. No receipt-covered file changed.

# T5 technical resource amendment r2

Recorded before any retry; no held-out model inference. Original PREREG and
source snapshots remain unchanged and retained. The five scientific runs,
seeds, objectives, effective batch8192, primary microbatch7168, architecture,
selection/calibration rules and A1–A4 bars are unchanged. This amendment is
solely for observed technical failures, not tuning.

At10:26Z, the lease wrapper stopped13 and14 after aggregate process RSS reached
153,296,777,216 and154,109,530,112bytes. Both exited0 after saving resumable
checkpoints (main03 step61; noD1 latest checkpoint to be recorded). Read-only
random mmap pages are represented in every loader's RSS, so four workers breach
the shared-host64GB limit. Use one loader worker and evict read-only mmap pages
from each process after a batch has been copied into independent tensors. This
uses MADV_DONTNEED, changes neither files nor tensors, and retains OS page cache.
Validate exact features and bit-exact optimizer/EMA replay across worker counts.
T4's covered source remains hash-identical. Measure actual resumed throughput
from these same declared runs; do not run a new fitting/throughput trial.

GRU08 exited1 at10:26:46Z: CUDA OOM allocating1008MiB with184.56MiB free during
step3 backward. Steps1–2 completed, but no scheduled1000-step checkpoint existed.
Retain the failed segment and restart the same seed as an explicitly justified
technical retry. Reduce ONLY the added historical-context encoding chunk to1024;
retain current-endpoint primary microbatch7168 and effective8192. All32 historical
CLS states remain differentiable and causal. Save GRU checkpoints every10steps
in addition to every epoch to bound future technical loss. No run outcome was
used to choose this operational change.

Freeze revised source and registration BEFORE resume. To keep one coherent
execution manifest, gracefully checkpoint the healthy04/11 runs, then rebind
only checkpoint provenance hashes under a recorded migration receipt; verify
every model/EMA/optimizer/scheduler/RNG/sampler/config value bit-for-bit unchanged.
All original checkpoints and snapshots are retained. These are continuations
of the same five runs, not additional trials. No new T4 shakedown or optimization.

## Validation and execution details

Eight synthetic tests pass: causal32 context/boundaries/gradient, noD1 feature
removal, role/content guards, baseline conventions, whole-cluster resampling
and exact features after mmap-page release. Replay from old4loader to new1loader
preserves model/EMA/sampler state bit-for-bit for main/noD1/GRU. The additional
8192-row GRU memory probe on train performs forward/backward with NO optimizer
update and explicitly asserts unchanged parameters/no optimizer state. It
passed at27555.244MiB allocated /37484MiB reserved. This is a technical memory
check, not an additional fitted trial or a repeat T4 throughput benchmark.

All r2 runs use one loader worker. A bounded subclass calls T4's unchanged
batch constructor then MADV_DONTNEED on read-only mmap input pages; all returned
tensors are independent copies. The OS page cache and store files remain.
GRU context construction performs the same release after copying features.
Both historical and current CLS remain differentiable; context chunk1024 only
bounds activation memory. Primary endpoint microbatch7168 and effective8192
are unchanged. GRU checkpoints every10steps plus epochs; others1000plus epochs.
Actual resumed rows/s, CPU/RSS/GPU memory are recorded from the same runs.

The original five-GPU placement remains04/11/13/14/08. Shared RSS cap64GB,
borrowed GPU headroom8192MiB, host process caps/console cap and nice>=10 remain
binding. All data/copy/live-lease/content guards apply. Leased stop trigger
04:20Z; mandatory checkpoint-and-exit05:00Z2026-10-09, or within30min of reclaim.
Home launchers remain fleet_run.sh; borrowed launchers remain lease-local
run.sh/env.sh. Verify exit before any resume; never copy checkpoints/stores05.
Provenance migration may alter ONLY checkpoint hash metadata and must verify
all other fields bit-exact. GRU's failed uncheckpointed prefix is a recorded
same-seed technical restart, not an additional trial. No held-out tuning.

The original noD1 whitelist, full128entity cap,192token bucket, tile_width64,
static assets/scope/role/store pins, T3-aligned float64 frequency baseline,
exclusive heldout claims and saved-statistics analysis remain binding. Each
selected checkpoint's r2 hash and dev temperatures are released before first
heldout scoring. Bootstrap uses lexicographically sorted match|side identities,
including zero-eligible perspectives. Resume validation and code pins are in
the revised manifest. Source architecture/metric changes are not authorized
by this resource-only amendment.

## Scope and prior exposure

Authority: DESIGN.md §§4.3–4.4, 5.1 and 7; frozen
`c56/data/eval/heldout_eval_spec_v1.json`. This registration covers five v1
runs only, not v2, search games, or standalone games.
T3 independently fitted its train-only baselines under its own prereg.json.
Its already-published frequency eval/OOD summaries were visible in the required
PROGRESS-data.md handoff. They must not inform recipe changes or checkpoint
selection. No model eval/OOD predictions have been produced by T5.

## Runs, selection and calibration

- v1-main seeds 2026100801, 2026100802, 2026100803.
- v1-noD1 and v1-gru each use seed 2026100801. They are descriptive ablations.
- Main architecture and losses are DESIGN §4.1–4.2; eager CUDA bf16,
  AdamW 3e-4, weight decay .05, cosine decay, 2,000-step warmup, clip 1,
  effective batch 8,192 and EMA .999. At most 12 epochs, dev patience 3.
  Every epoch uses every train play and a fresh hash-selected 25% of waits,
  inverse probability weight 4 and the frozen quality/balance weights.
- Select each run's EMA checkpoint by lowest uncalibrated natural-row dev
  joint NLL, evaluated after each epoch. Ties select the earliest step.
  Select the primary main seed by that same dev statistic; exact ties select
  the smaller seed. Record checkpoint hashes and selection before held-out
  inference. Report all three main seeds; never select a seed using eval/OOD.
- Fit three temperatures separately on dev only after checkpoint selection.
  Use the T4 deterministic uniform subset of at most 100,000 dev rows,
  NumPy PCG64 seed 1; apply each head's eligibility after sampling. Preserve
  T4's bounded log-temperature [-4,4] and LBFGS recipe. Freeze temperatures
  and their provenance before held-out inference. The calibrated policy is
  primary for A1–A4; report uncalibrated metrics alongside it.
- Each selected run is inferred once on eval and once on eval_ood. Compute
  before/after-temperature metrics from the same forward pass. Persist row
  identities and sufficient statistics so bootstrap/report work does not
  rerun model inference. No checkpoint or temperature changes after opening
  held-out model results. Technical failures alone may justify a recorded
  continuation/retry; preserve original receipts and completed row prefixes.
- GRU uses a causal 32-step CLS history, reset at perspective boundaries;
  implementation is the differentiable sliding window defined below.
  Adoption requires >.01 nats better dev joint NLL than main and compliance
  with the DESIGN latency budget. It cannot replace the main gate entrant
  based on held-out results. noD1 removes the derived input block; targets
  remain targets only. Its exact feature whitelist is specified below and frozen with code.

## Metrics and pass bars (DESIGN §5.1)

Metrics as defined in heldout_eval_spec_v1.json: play/wait NLL and Brier,
card top-1/top-3/NLL, tile NLL/median error, joint NLL, ability NLL, hazard
calibration. Add top-8 recall of the human (card,tile), exact and within one
Euclidean tile; per-card and per-arena slices, arena from the card's
unlockArena in frozen gamedata.json; gate/card ECE before and after scaling.
The arena code is descriptive, not an assertion about the current game.

Every reported eligible supervised row has natural weight 1, with no wait
subsampling or training balance. Entire perspectives are retained. Following
the explicit DESIGN playable-row denominator, primary play/wait metrics and
gate ECE use supervised rows with a legal card play. Also report the frozen
JSON's all-supervised-row timing metrics as distinctly named *_all fields.
Compare frequency baselines using exactly the same row eligibility.

The following bars are reproduced from DESIGN §5.1. All are required on eval,
and all are reported on eval_ood:

- **A1.** Joint NLL, play/wait NLL, card NLL and tile NLL are each lower than
  the frequency baseline, with 95% CIs of the paired difference below 0.
- **A2.** On the P16 slice, card NLL and tile NLL are ≤ the upgraded P16 BC's
  + 0.05 nats (the generalist doesn't lose to the specialist on its home data).
- **A3.** No own card with a significantly worse card-conditional tile NLL
  than its per-card frequency histogram. Count passing cards out of 56;
  for v2, out of all scoped cards.
- **A4.** Gate ECE after temperature scaling ≤0.01. The base play rate is
  ≈0.046, so this bounds miscalibration at about 20% of it.

A1 uses model minus baseline, with each paired CI upper endpoint strictly <0.
A2 is a point-estimate margin, not a new significance test. Validate P16 scope,
role, source hashes and eligible row identities/counts against T3's result.
A3 uses per-card paired two-sided 95% intervals: significantly worse means
lower endpoint >0. No multiplicity adjustment is added. Freeze the 56 card
token IDs from the C56 scope before scoring; absent cards are unassessed and
cannot count as passing. A4 is binary P(play-or-ability) versus observed act,
10 equal-width bins on [0,1], weighted by eligible row count; its bar is the
point ECE. Also report multiclass gate ECE and the spec's separate 10 equal-mass
timing calibration, without substituting either for A4.

Primary verdict is the preselected main seed. The other two main seeds receive
the same full gate diagnostics, but do not supply an alternative passing arm
if the primary fails. Report noD1/GRU minus seed-2026100801 deltas and each
run's eval_ood minus eval gap. No descriptive metric changes the verdict.

## Bootstrap

Use exactly 10,000 perspective-cluster resamples with replacement separately
within each role, NumPy PCG64 seed **2026100805**. Sort perspective identities
and record their ordered hash; draw N whole perspectives from N, equivalently
multinomial multiplicities. Include perspectives with zero rows eligible for
a conditional metric. Use identical multiplicities for model/baseline and
paired ablation comparisons. Resampled means are sums divided by eligible
row counts, not unweighted means of perspective means. Median tile error is
recomputed with replicated row multiplicities. Two-sided percentile endpoints
are .025/.975 with NumPy's linear quantile convention. Record undefined
zero-denominator resamples and valid count; no imputation of a passing result.
No within-perspective independent row bootstrap. Reuse saved statistics for
all intervals; uncertainty recomputation is not a new held-out scoring run.

