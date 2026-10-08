# Gate (a), C56 v1: frozen preregistration

Frozen before ALL T5 real-data training and held-out model inference. The earlier
PREREG.draft.md remains historical, not the registration. No v1 trials have
started and no model eval/eval_ood predictions have been produced.

Authority: DESIGN §§4.3–4.4,5.1,7 and the coordinator's explicit start-gate and
lease overrides. T3 release, T4 qualifying rerun and throughput gates all PASS.

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

## Frozen implementation and qualification

Full executable manifest: `executable-manifest.json`, SHA256 `934516a0ae3a2d950a676d6c35f0d310ead7ad951ec2c776967ccbd21a7e7f9f`.
It binds the actual checkout commit plus every staged Python dependency and T5
extension, including uncommitted content. Every host verifies every pinned file
before launch/resume. `freeze.json` binds this document and the manifest.

Qualified T4 code hash `301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`.
Throughput receipt SHA256 `5c7e83bacc92096a30520ccdaf002321b753542a7afc489e57183df865fc7229`.
T4 rerun0727Z shakedown summary SHA256 `5cda727dacb9743c922dc8f36aba13124d0fb30133b95f0cf75ab56f9d1f303f`.
Historical0714Z cap failure is superseded, not erased. The full v5 cap is128
entities; token buckets48/64/96/128/192. Tile width64 is DESIGN's qualified
latency fallback; main/noD1 have2,254,938 parameters. Unpadded serving is qualified.

Exact qualified main microbatch7168; effective8192; four loader workers;
eager torch2.7.1+cu118, bf16; production dropout.1. Main measurement12154.126054
loader-inclusive rows/s (cold11415.551647); two/GPU11394.330462 aggregate, hence
one/GPU. The timing includes mmap batches, loader delivery, transfer, forward/
backward, clip, AdamW and EMA; excludes index initialization, checkpoint and dev.
No extra T4 benchmark is run. Record actual early-step throughput of each of
the five declared runs, plus dev/checkpoint overhead, without recipe tuning.

T5 calls the unchanged qualified T4 train.main and optimizer. Its explicit
in-process dependency injection is listed in imitation/t5/README.md: policy
factory, provenance store, row-index annotation, GRU binding, interruptible dev.
No covered T4 file is edited. T5 additions are separately fully hashed; T4's
throughput does not claim to measure the GRU. Main sampling, loss, optimizer,
EMA, scheduler, checkpoint/RNG logic are not replaced.

noD1 masks token types3–13 and15–17 and zeros global numeric columns15–19.
It retains public hand/next, opponent seen cards, entity features, original
v5 globals/champion button, legal masks. Own deck remains only in auxiliary
target mapping, not noD1 features. Derived values are both zeroed and masked.

GRU adds one192-wide layer (2,477,274 total parameters). At each endpoint it
uses the current public CLS and preceding31 stored public observations, with
zero initial state and no context before perspective start. The final valid
state replaces CLS for all heads; current tokens remain for card/tile heads.
All context states are recomputed under current weights with full gradients;
no stale state or detached history. Current/past trunks use activation
checkpointing preserving RNG. Repeated context rows within a microbatch are
deduplicated; historical encodings use local8192 entity sorting and7168+1024
microbatches. Endpoint sampling remains iid, all plays/fresh25% waits, weights
unchanged; unsampled waits can appear as public history. Evaluation uses the
identical sliding32 definition with EMA and dropout disabled. No hidden state
persists between optimizer steps or perspectives. This exact-context workload
may take substantially longer; GRU runs on home08, with measured ETA reported.

Frequency comparisons use the T3 float64 baseline convention: normalize raw
counts, add one ONLY to tile histograms, clip final NLL probabilities at1e-300.
T4's helper clips zero counts at1e-30 in logits and is deliberately not used
for these baseline sufficient statistics. T5 dev-only alignment reproduced
all four T3 NLLs within1e-10 (receipt pinned). No baseline refit or model heldout
inference was involved. The existing T3 P16 receipt is pinned and all counts,
role/perspective scope and play eligibility are checked before A2 reporting.
OOD has no P16 perspectives: report A2 N/A there, not an invented zero/pass.

## Content pins and execution

All full store, role-file, role-manifest, eval-spec, sidecar, assets, token,
gamedata, baseline/count and56-card-scope pins are in executable-manifest.json.
T3 release SHA256 `6b335ec4470215922c1ff346da18535fe3f8e3eb9e88dfe109d16d1f86b9472c`.
Assets SHA256 `3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737`.
Scope is the fixed C56 declared16+40 cards mapped through these pinned assets;
it is not inferred from heldout outcomes. Card names/arenas are frozen there.
Bootstrap identities sort lexicographically by T3 match|side; record ordered
identity hash. Zero-eligible perspectives stay in every role's resample universe.
Additional frozen-spec phase/match-part/archetype/mode/P16/OOD/engine-phase/
forms/ability-attribution slices are descriptive. Per-card and arena tables
include all fixed scoped cards; missing cards are unassessed.

Main seeds2026100801/02/03 run on04/11/13, noD1 seed01 on14, GRU seed01 on08.
All five data copies are checksum-qualified; no data-worker transfers duplicated.
Validate hub readiness plus live leases, who, GPU and all-Clasher process/RSS
occupancy immediately before launch. Caps home96,11=96,13/14=64; with a console
user cap16. Reserve two supervisors. Nice>=10, shared RSS<=64,000,000,000bytes,
borrowed GPU free>=8192MiB. Home jobs use fleet_run.sh; borrowed jobs use only
clasher-lease/run.sh and its env.sh/GPU env/footprint. No shared environment
writes, forbidden hosts, roader repo/jobs/cache access, commits or data deletion.

Leased jobs must finish or checkpoint AND EXIT by2026-10-09T05:00Z. The
predeclared stop trigger is04:20Z, leaving40minutes; the wrapper independently
checks reclaim every60s and requires exit within30minutes. Synthetic SIGTERM
at dev entry saved the full pre-dev state and exited before a dev batch.
The dev guard checks at each batch; training checks after each optimizer step.
On reclaim/end, verify own PID exit and checkpoint hash, transfer checkpoint
LAN directly to home01/04/08, never05, and resume SAME optimizer/scheduler/RNG/
sampler epoch+cursor. Home01 requires perception GPU free. No new trial.

Select/hash all five checkpoints on dev only; fit/hash all temperatures on dev
only; create all-run release before first heldout inference. Each selected run
gets an exclusive role claim beside its checkpoint. Commit raw/calibrated and
aligned baseline statistics per batch. Completed roles refuse reinference;
technical continuation requires a recorded reason and reuses committed prefix.
Analysis and any report revision read saved statistics. Log training loss/dev
curves, PIDs, exact resumes and measured wall/CPU/GPU-process hours; separately
account validation, training, calibration, heldout and analysis. Mirror only
small owned docs/receipts/results to05. Disable continuation when results finish.
