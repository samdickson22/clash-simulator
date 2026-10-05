# Stored recurrent state and truncated BPTT

This is an opt-in learner change. The default remains current-weight full-episode-prefix replay. Stored-state mode uses the behavior actor's pre-observation recurrent state and bounded, gradient-free burn-in before each loss-bearing chunk. It changes training semantics and is not expected to match full-prefix training after weights change.

The final suite passes 45 tests. Measured end-to-end speedup is 2.73x to 3.04x in the pinned benchmarks. The <=2 ms learner target is missed, and the completed 150k-per-mode A/B establishes numerical sanity but leaves learning-quality acceptance unproven.

## Flags

Both `python -m clasher.rl.train_recurrent` and `python -m clasher.rl.imitation fit` accept:

```
--recurrent-update-mode stored-state --tbptt-chunk 64 --tbptt-burn-in 16
```

Alternatively pass `--recurrent-config reports/strategy_council_20260928/learner-tbptt/configs/stored-state.toml`. The strict TOML accepts those same three names with underscores; explicit CLI values override TOML. Omitted options select `full-prefix`. Default-mode checkpoint arguments do not gain new keys. `--sequence-batch-size` counts PPO chunks in stored-state mode. For 256 nominal loss-bearing tokens use full-prefix 2×128, T32 8×32, or T64 4×64. Burn-in tokens do not contribute loss.

## Design

- All three rollout paths capture detached actor hidden and cell state before every observation. Worker transport carries those arrays plus at most B prior observations and their states across rollout boundaries. Stored-state collection also stops rebuilding full prefixes after policy updates, retaining behavior state instead.
- PPO splits each sequence into fixed T-decision windows, shuffles chunks, buckets equal lengths, and includes every rollout tail once per completed epoch. Episode-start masks reset state and block gradients inside a window. Splitting at episode resets was removed after the first A/B exposed short terminal tails receiving separate optimizer updates. The current model replays at most B observations without gradients before each chunk. Reset masks prevent history from crossing an episode reset. Only short rollout-tail minibatches can contain fewer than 256 loss-bearing tokens; with 128 rollout steps and T32/T64, ordinary updates have exactly 256 tokens per minibatch.
- Only the stored-state learner crops trailing entity padding. Interior mask holes and entity indices remain intact.
- The current privileged critic is feed-forward, so there is no recurrent critic state to save. Actor state includes both LSTM tensors, or both full structured-memory tensors.
- BC makes a linear no-grad pass over training episodes once per epoch, caches pre-burn states only at needed boundaries, then refreshes B steps with current weights at each minibatch. Validation retains its existing full-prefix path. BC requires complete public-v4-or-later episodes, chunk length at least two, and no sequence augmentation. Stored-state replay requires zero dropout.
- States become stale as weights change; burn-in reduces but does not eliminate this approximation. Chunk length also truncates temporal gradients. Neither flag changes engine mechanics or the default loss definitions.

## Verification

The final focused suite passed all 45 tests in 72.57 seconds. See `logs/tests-final.log`. Preserved pre-change PPO and BC references are under `results/`, with original source copies under `before/`. PPO verification compares model tensors, optimizer, losses, RNG state and CLI arguments, then normalized torch serialization bytes. BC compares checkpoint/control payloads and RNG state exactly. These are deterministic fixture checks, not proof for every training configuration.

Tests also cover strict TOML validation, CLI precedence, padding parity with interior holes, reset state/gradient isolation, and 256 loss-bearing tokens per ordinary T32/T64 minibatch even when episodes reset. PPO equivalence requires the short episode to terminate exactly at the chunk boundary, covers the whole episode with zero burn-in, and compares losses and gradients at atol=rtol=2e-6. BC whole-episode model/metric equivalence uses the same tolerance. Burn-in, reset/tail coverage, BC cache refresh, collector contracts, transport and resume RNG regressions are included.

Command:
```
nice -n 10 .venv/bin/python -m pytest -q tests/test_recurrent_tbptt.py tests/test_council_ppo_contract.py tests/test_pilot_learner_inference.py tests/test_council_rollout_transport.py tests/test_train_resume_rng.py
```

## Measurement scope

`run_experiment.py` loads `human-prior-p16/checkpoints/human-bc-natural-seed2903.pt`, seed 2903, eight local environments, 128 rollout steps, two PPO epochs, one CPU torch thread, and public balanced/pressure/defense scripts. Each run records source hashes, checkpoint hash, architecture, config, PID and per-update monitor metrics. TOML configs are validated before collection. KL stopping is enabled at 0.02, so actual optimizer work and trajectories differ between modes. Tables measure the configured training loop rather than an identical fixed tensor workload.

Learner ms/decision divides total update wall time by collected decisions, including all executed epochs. End-to-end decisions/s divides decisions by collection plus update wall time; startup and checkpoint serialization are excluded. Other owners changed pathfinding.py between the original full/T32 benchmarks and entities.py between the first A/B starts. Those two partial A/B runs were stopped and retained as interrupted evidence. The full control uses runtime-src/clasher; corrected T64 uses runtime-src-fixed/clasher. Hash verification shows only the intentional stored-state chunk helper in tbptt.py differs; checkpoint and engine hashes match. Default byte identity was reverified after the correction. The original source manifest is results/runtime-source-sha256.json. The original benchmark comparison therefore also has source drift. The shared Mac mini has concurrent foreign jobs, so timing includes contention and is not directly comparable with the engine-speed report's 64-environment worker layout. Benchmarks use 4096 decisions per mode. Targets are ≤2 learner ms/decision and about 3× end-to-end speedup; measured success must be judged against those targets.

The A/B uses 150000 decisions per mode, the same checkpoint, seed and public-script recipe, and full-prefix versus T64/B16. It is a one-seed training sanity check, without held-out evaluation or a superiority claim. The experimental harness does not reproduce the pilot's anchor penalty or critic warmup. Monitor curves describe on-policy training games only.

## Final assessment

The 4096-decision benchmarks reach 3.04× end-to-end throughput at T32 and 2.73× at T64. Learner updates take 10.61 to 11.29 ms/decision, so the ≤2 ms target is not met. These are shared-host wall times with KL stopping, not isolated fixed-work CPU measurements.

Both A/B runs completed all 150000 decisions. Across the entire runs, full-prefix took 49.55 update ms/decision and ran at 12.99 decisions/s; T64 took 11.45 ms and ran at 36.56 decisions/s, a 2.82× end-to-end gain. Full-prefix finished 26 wins and 174 losses in training games; T64 finished 30 wins and 146 losses. Both final checkpoints reload, contain finite model/optimizer tensors, and changed 146 actor and 49 critic tensors from the same initializer. See `results/final-checkpoints.json`.

Numerical sanity passes. First-to-last-window value loss fell from 0.00518 to 0.00333 for full-prefix and 0.00658 to 0.00280 for T64. Explained variance rose from 0.323 to 0.752 and 0.265 to 0.795 respectively. There was no non-finite loss, gradient or parameter failure. Entropy remained nonzero and the final-window mean KL stayed bounded.

The stronger learning-quality gate remains unproven. Training win rates fell from 9/24 to 6/33 games for full-prefix, and 9/28 to 4/29 for T64. Average reward also worsened in both. This one-seed run omits the pilot's critic warmup and anchor penalty, and has no held-out strength evaluation. It supports neither a superiority claim nor enabling stored-state mode by default. T32 has a performance benchmark, not a 150k learning comparison. BC correctness is tested; BC wall-time speedup was not measured.

The initial stored-state candidate was stopped at 96256 decisions. It split at episode resets, giving short terminal tails separate optimizer steps. The final code uses fixed windows with internal reset masks, so ordinary minibatches keep equal loss-bearing tokens. The negative monitor trace is retained in `runs/ab-t64-pinned/`; it is not used in the final result table. The win-rate decline cannot be attributed solely to that defect, since the full-prefix control also declined.

![Completed A/B monitor curves](results/ab-monitor-curves.png)

The plot shows trailing eight-update means; the tables below use decision-weighted windows. Final checkpoints, source pins, reference fixtures and receipts are retained. Benchmark checkpoints and duplicate scratch checkpoints were removed. No owned training or supervisor process remains active.

## Files changed

Production changes are limited to `src/clasher/rl/train_recurrent.py`, `src/clasher/rl/imitation.py`, `src/clasher/rl/parallel_rollout.py`, and new `src/clasher/rl/tbptt.py`. `src/clasher/rl/model.py` is unchanged from the preserved pre-edit copy. Tests are in `tests/test_recurrent_tbptt.py`. Harness, configs, receipts and this report live under `reports/strategy_council_20260928/learner-tbptt/`. The repository was already dirty; pre-edit copies delimit this task's changes.

<!-- measured-results -->

## Benchmark receipts

| Mode | Decisions | Update ms/decision | End-to-end decisions/s | Speedup |
|---|---:|---:|---:|---:|
| bench-full-pinned | 4096 | 50.72 | 13.43 | 1.00× |
| bench-t32-fixed | 4096 | 10.61 | 40.89 | 3.04× |
| bench-t64-fixed | 4096 | 11.29 | 36.70 | 2.73× |

Source pinning: True. Full/T64 use the first 4096 decisions of the pinned A/B runs; T32 is a separate 4096-decision run against the corrected source; only tbptt.py differs from the full-prefix source, whose default behavior is byte-identical.

Compare the table with the ≤2 ms/decision and approximately 3× targets. This comparison includes entity-padding cropping, changed collection recurrence, differing KL early stops and shared-host contention. It does not isolate prefix replay cost.

## A/B monitor summary

### ab-full-pinned

Status: complete, 150000 decisions. Monitor values finite: True.

| Window | Decisions | Games | Wins | Mean reward | Entropy | Value loss | KL | Clip fraction | Gradient norm | Explained variance |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| early | 24576 | 24 | 9 | -0.00024475 | 0.36763 | 0.005182 | 0.0024898 | 0.014201 | 0.35657 | 0.32335 |
| late | 25072 | 33 | 6 | -0.00083678 | 0.31383 | 0.0033271 | 0.0070981 | 0.026925 | 0.92891 | 0.75215 |
| overall | 150000 | 200 | 26 | -0.00098688 | 0.31257 | 0.0031296 | 0.0060834 | 0.025788 | 0.69421 | 0.60658 |

### ab-t64-fixed

Status: complete, 150000 decisions. Monitor values finite: True.

| Window | Decisions | Games | Wins | Mean reward | Entropy | Value loss | KL | Clip fraction | Gradient norm | Explained variance |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| early | 24576 | 28 | 9 | -0.00040762 | 0.39691 | 0.0065784 | 0.0022983 | 0.012526 | 0.371 | 0.26507 |
| late | 25072 | 29 | 4 | -0.0008395 | 0.29383 | 0.0028002 | 0.0055327 | 0.027618 | 0.70721 | 0.79494 |
| overall | 150000 | 176 | 30 | -0.00077353 | 0.34722 | 0.0037968 | 0.0051415 | 0.026065 | 0.60368 | 0.61526 |

Early and late windows use update endpoints ≤25k and >125k decisions. Metrics are weighted by collected decisions; individual minibatch statistics retain the learner's existing aggregation. Terminal outcomes and training reward are noisy and are not a held-out strength evaluation.

Both runs completed. The final assessment above distinguishes numerical sanity from the unresolved learning-quality gate. No superiority claim is supported by this single-seed comparison.
