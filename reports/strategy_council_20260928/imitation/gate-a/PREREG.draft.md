# Gate (a), C56 v1: registration draft

Prepared 2026-10-08 UTC by T5. **NOT FROZEN; NOT AUTHORIZATION TO SCORE.**
T3 training release, all five target copies and T4 rerun shakedown have passed;
the additional throughput qualification remains pending. Finalize this as PREREG.md
with an immutable SHA256 receipt after qualification and executable-code review,
before any T5 training or eval/eval_ood inference. Keep this draft as an earlier artifact.
No T5 fitting or held-out scoring has occurred.

## Qualified-model correction to bind before T5 training

Coordinator resumed T5 on 2026-10-08 after the first T4 shakedown failed on a
dev row with more than 64 visible entities. The original 64-entity limit was
a contract-cap bug. The corrected adapter preserves **all entities up to the
full v5 cap of 128**, and adds a **192-token training bucket** for entities plus
the fixed public/history tokens. No truncation or row exclusion is allowed.
This is a technical contract correction, not held-out tuning.

The qualifying rerun is `t4-shakedown-20261008T0727Z` on 04, launcher2398593.
It must publish PASS before T5 proceeds; a second failure stops T5 again.
Its actual command uses **tile width64**, the DESIGN's predeclared latency
fallback (T4 reports d128 p99=17.45ms at78 entities). Trunk remains unchanged;
2,254,938 parameters. Single-row inference omits training-bucket padding with
tested equal logits. Preserve this qualified configuration in all five runs.

Rerun source hashes independently read on04 at07:44:50 UTC, equal to05:
- features.py: `4a1d2f79002ba704783d5138321b1c242ac04937b3cbfff3517b2ac541e02d3d`.
- network.py: `39ad5ea8a5d2342c16724fd6c53daedb5d9ac211b9e28a5d2c57860ce1d65db6`.
- train.py: `0d546c7fb6e534dd2c97729d0f58e9560bd52c972781892aed9c1cdeb07f3fab`.
Full source manifest: `imitation/model/receipts/source-20261008T0727Z.json`.
These identify the pending T4 rerun, **not a final T5 code freeze**. Before
launching any T5 run, freeze PREREG.md plus commit and full per-file SHA256
manifest of the actual staged T5 model/trainer/ablations/evaluator/assets.
Verify remote code hashes against that manifest, record them in run receipts
and checkpoints, and never rely on an earlier checkout hash alone.

## Additional throughput start gate — coordinator update 2026-10-08

T4 shakedown PASS alone does not release the five runs. Require the T4-owned
`imitation/model/receipts/throughput-pass.json` as an additional hard gate.
T4 is raising the microbatch from64 and vectorizing the loader/evaluator;
target **at least8,000 loader-inclusive training rows/s**. Do not treat the
old2.3k subset measurement, step-only throughput, or a filename without its
verified contents as this qualification. T5 does not duplicate T4's optimization
or benchmark work. Verify the actual receipt schema, PASS evidence, measured
loader-inclusive throughput and source/configuration provenance.

Start runs only on the code hash recorded in that receipt. In final PREREG.md
record the receipt SHA256, qualifying code hash/full source manifest, measured
rows/s and **exact qualified microbatch size** (pending; do not assume64).
Verify deployed files against the qualifying hash before each launch/resume;
keep effective batch8,192 and the fixed statistical/optimization recipe.
Changes to receipt-covered model/trainer/loader/evaluator files invalidate
that code qualification until a matching throughput receipt exists. Record
all owned T5 ablation/scoring additions in the full executable manifest as
well; do not silently substitute an unqualified trainer or copied old source.

Plan wall time from actual throughput and measured dev/checkpoint overhead,
not the design estimate. Leased jobs must finish or checkpoint and **exit by
2026-10-09 05:00Z**, ahead of05:30Z expiry. Arrange the checkpoint/exit trigger
early enough to finish by05:00Z; record the trigger and verified exit receipts.
Use periodic resumable checkpoints and the lease wrapper for earlier reclaim.
If unfinished, preserve the same seed/optimizer/scheduler/RNG/sampler cursor,
transfer checkpoints directly over LAN to home GPUs01/04/08, verify hashes,
and resume the same run there after resource checks (01 only if perception
is not using it). No checkpoints/stores via05, no new trial, no deletion.

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
  exact implementation must be specified and tested before the final freeze.
  Adoption requires >.01 nats better dev joint NLL than main and compliance
  with the DESIGN latency budget. It cannot replace the main gate entrant
  based on held-out results. noD1 removes the derived input block; targets
  remain targets only. Its exact feature whitelist must be frozen with code.

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

## Available provenance pins; final verification required

- Store: `127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/c56-store-v1`.
- Root manifest SHA256: `1acf6b5875091e009c18e598a71714016b9833b6cc626032e0fa676ccdac5c2f`.
- Role file SHA256: `7e357f64ad6df13e232ec9b1c7c143bbcd734d12a9cdceec2cef999bbe74fcdc`.
- Eval spec SHA256: `d9f978f75191b5d5a474d127dbccd618b93dad5069dd851ab4f8b2a47fdaa7ae`.
- Sidecar manifest SHA256: `1a18b263bd0d2d44aee75491e82aa89e152c8a8474cca6d664128c0fc2790cb6`.
- Store role manifest SHA256, train: `2c4c7c4f94ece017ec11f048576ce96ed596620c1b7f1f3b30c046c11ab51e5e`.
- Dev: `b416f9ddaf3c8619b9f5c08ebc6e23373ee5b49f79e6b485eb905de17987bdb0`.
- Eval: `d94de54f5b55dd8ebf9ee8816e651c6909a3ea52f9ef065a112d36248c67585f`.
- Eval OOD: `90279a99051b0cf6b98f886aeef83034ffa346bc9d3e4dd9037fb34769217db0`.
- T3 baseline recipe SHA256: `45c14463ee57798cef59d5c9d33a5caeccedfc11353c41b35445f0769ea74a84`.
- Checkout HEAD at draft: `2b8d528cb2294fea0b362aaa745c60a5074bd1f5`.

Pending final freeze: T3-PASS hash and verified host-copy receipts; T4 shakedown
receipt/hash; final code commit plus per-file content hashes (including dirty
files); static asset/token/gamedata hashes; baseline counts and P16 summaries;
56-card scope; finalized ablation/evaluation code and tests. Do not present
the draft's content hash as a frozen PREREG hash. Create an immutable freeze
receipt binding PREREG.md and the full provenance manifest before scoring.

## Operations and compute accounting

Coordinator update 2026-10-08: use one run per GPU across 04, 08, 11, 13 and 14
after both start gates and checksum-qualified store copies. Planned allocation:
main seed 2026100801 on 04, main 2026100802 on 11, main 2026100803 on 13,
noD1 on 14, GRU on 08 (retain the potentially longer recurrent run on a home
host). Fall back to up to two simultaneous runs per GPU on 04/08 if a leased
copy is not ready; queue the fifth if necessary. No extra fitted runs.
Measure loader-inclusive rows/s from early steps of the declared runs; fallback
packing is chosen from aggregate throughput, not losses or held-out scores.
Check who, all Clasher processes, GPU use and available memory before launches.
Home-host cap is 96, lease caps are 96 on 11 and 64 on 13/14; use the smaller
of the applicable cap and 16 with a console user. Include launchers/supervisors.
Effective batch and sample membership stay fixed when changing microbatch
size/loader concurrency. Record loader-inclusive and step-only throughput.

Stage only owned files with rsync -c into isolated T5 paths. Home GPU jobs use
fleet/fleet_run.sh. Leased jobs MUST instead source only the lease-local
clasher-lease/env.sh and use clasher-lease/run.sh, its GPU env and footprint.
Read /mpac/sdicks02/cc/FLEET-SHARING.md and fleet/LEASED-HOSTS.md; validate the
live lease before work. Reclaim/refusal/expiry/missing lease blocks launch.
Leases expire 2026-10-09 05:30Z; checkpoint and EXIT by05:00Z (trigger the
planned stop early enough to finish), or on earlier reclaim. Wrapper polls
every 60 seconds; checkpoint-and-exit must finish within 30 minutes, without
running a full dev evaluation after the stop request. Preserve ≥8192 MiB free
GPU memory everywhere borrowed and ≤64,000,000,000 bytes Clasher RSS on shared
hosts. No shared env/caches/home or roader repo/jobs/cache access. Only the seven
explicitly leased hosts 09/11/13/14/15/16/18 supersede earlier exclusions;
09/15 are GPU-only ≤8 processes, 16/18 ≤48; they are available reserves, not
extra runs. Never contact 02/07/10/12/17.
All jobs are detached, nice ≥10, with verified label/PID and checkpoint before
resume. Save JSONL curves, all checkpoint artifacts, timing and exit receipts.
Never delete data or commit, broadly kill processes, or touch tailscale/crontab.
Keep source authorship and small receipts/docs/results on 05; do not copy
stores/checkpoints there. No builds, tests, games, training or bulk transfers
on 05. A reclaim/lease-end resume migrates the same run, not a new seed/trial.
Report per-run wall/CPU time, GPU-process hours, and unique occupied-GPU wall
hours (avoid double-counting concurrent jobs) plus throughput probes, dev
evaluation/calibration, held-out inference and bootstrap analysis separately.

Shakedown qualification update09:15 UTC: rerun0727Z passed at09:05:52.560799Z,
exit0. Summary SHA256 `5cda727dacb9743c922dc8f36aba13124d0fb30133b95f0cf75ab56f9d1f303f`
at `imitation/model/receipts/shakedown-20261008T0727Z/summary.json`.
Throughput receipt/code/microbatch remain pending; draft still not frozen.
