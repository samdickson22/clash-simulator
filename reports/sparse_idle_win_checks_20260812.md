# Exact sparse idle win checks (2026-08-12)

## Result

The idle fast-forward loop now reuses the eligibility check already performed
by `SelfPlayBattleEnv` and calls the exact win-condition refresh only at the
regulation/overtime and tiebreak timer boundaries. Idle eligibility proves that
only static Crown Towers are live and that no tower HP, crowns, or stateful
tower clock can change between those boundaries.

The isolated tower-only workload improves **4.996%** by ratio of medians
(paired median **5.253%**, 21/21 positive pairs, bootstrap mean 95% confidence
interval **4.673% to 5.342%**). Production-shaped random and balanced-strategy
rollouts are parity-clean and statistically neutral; their confidence
intervals cross zero. This is an exact idle-path win, not a claim of whole
training throughput improvement.

## Machine and controls

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, one BLAS/OpenMP/Accelerate thread, `nice -n 15`
- fixed seed 9067; alternating paired reference/candidate order
- 21 repetitions for the isolated idle workload; 15 repetitions for each
  production-shaped workload
- no MPS/GPU use; a separate low-utilization Clasher vision process remained
  active, so only paired comparisons are attributed

## Benchmark commands

Isolated idle advancement:

```text
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 \
  uv run python scripts/perf/benchmark_idle_advancement.py \
  --seed 9067 --decisions 32 --repetitions 21 --decision-interval 8 \
  --max-ticks 9090 --engine-fast-path on
```

Production-shaped stationary workloads (run once with `random`, then with
`strategy --strategy balanced`):

```text
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison sparse-idle-checks --workload random --seed 9067 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2
```

## Timings and attribution

| workload | reference seconds | candidate seconds | reference decisions/s | candidate decisions/s | paired median | positive pairs | bootstrap mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tower-only idle | 0.008115 | 0.007729 | 3943.456 | 4140.474 | **+5.253%** | 21/21 | +4.673% to +5.342% |
| random policy | 0.663462 | 0.662143 | 192.928 | 193.312 | +0.297% | 9/15 | -0.078% to +0.640% |
| balanced strategy | 0.684710 | 0.677991 | 186.940 | 188.793 | +0.066% | 8/15 | -0.112% to +2.487% |

The idle workload digest is
`4cca5e5147c7f37d7f8b7ea16e08fe58f73b05f2c28df99260dc4e744ee8e241`.
Random variants share digest
`1541d3cb67504d8700f69c97dfc22a8958297e8df3f4ec21ea1e861063e31a51`;
strategy variants share
`8cc07c5fb46d36635bb714cc015bc1f5ceafccafa32395e80c330af198260f27`.

## Exactness gates

- Reference and sparse variants under scalar/off, shadow, and optimized/on all
  produce fixed-seed digest
  `6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e`.
  Each shadow variant sampled one legacy action-mask comparison and recorded
  zero mismatches.
- Focused tests cover ordinary static-tower advancement, rejection of active
  tower clocks, transition into tied sudden death, crown-lead resolution at
  regulation expiry, and tiebreak termination.
- 33 idle/determinism/action-mask tests pass.
- 976 route/path/river/bridge/enabled-interaction/targeting/collision/
  action-mask/idle tests pass.
- Ruff passes the owned benchmark/test files; shared source reports only
  inherited findings, with none on an owned line. Benchmark-driver
  `py_compile` and `git diff --check` pass.

## Integration

Cherry-pick the isolated commit. If `selfplay_env.py` conflicts with training
work, port only `_USE_TRUSTED_IDLE_ELIGIBILITY` and the
`eligibility_checked=` argument at its already-successful
`can_fast_forward_idle()` call. In `battle.py`, port the sparse reference
switch, the keyword-only `eligibility_checked` parameter, and the timer-boundary
guard around `_check_win_conditions()`. Public callers remain safe because the
new keyword defaults to false.
