# Compiled exact native route-goal selection

Date: 2026-08-12

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Machine: Mac mini, Apple M4 Pro (12 physical/logical cores), 24 GB RAM,
macOS 26.5.2 (25F84), Python 3.12.13.

## Change

The exact row-interval native route-goal selector remains a measurable Python
hotspot after the full-grid scan was removed. This change moves that arithmetic
kernel into the existing optional Numba acceleration layer. It retains the
Python row-interval implementation as the exact fallback when Numba is absent.

The compiled kernel uses the same arena bounds, half-grid tie rule, y-major row
order, strict-smaller replacement rule, integer predicates, and output shape as
the Python reference. Numba does not support `math.isqrt`, so its initial square
root estimate is corrected upward/downward with exact integer comparisons before
it is used. There are no card, deck, player, or enabled-interaction special
cases.

All timed commands were single-process CPU-only at `nice -n 15`, with one
Torch/BLAS thread where applicable. Variant order alternated within each paired
run. No trainer, rollout worker, MPS/GPU task, corpus task, or repository staging
process overlapped the accepted final runs.

## Exact oracle workload

```sh
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 nice -n15 \
  uv run python scripts/perf/benchmark_oracle_route_goal_row_interval.py \
  --comparison compiled-row-interval --seed 9037 --planner-seed 2037 \
  --states 2 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

| implementation | median seconds / 2 labels | median labels/s |
| --- | ---: | ---: |
| Python row interval | 1.217256 | 1.643039 |
| compiled row interval | 1.193808 | 1.675311 |

The paired throughput median is **+1.440%** (10/11 pairs positive); the
bootstrap mean 95% CI is +0.733% to +1.792%. Every row produced complete
action/battle/planner-RNG digest
`f2189cf83eab5eb6c9b9512bd621a351c0691b8dd8ac14cb2d4c4745c7772f32`.

## Production-shaped stationary rollouts

Both workloads used 4 environments, 32 learner decisions per row, 24 untimed
warmup decisions, 15 interleaved pairs, exact fast path, and `defense-v2`
rewards.

```sh
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 nice -n15 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison compiled-native-route-goal --workload random --seed 9037 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2

env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 nice -n15 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison compiled-native-route-goal --workload strategy \
  --strategy balanced --seed 9037 --num-envs 4 --rollout-steps 32 \
  --repetitions 15 --warmup-steps 24 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

| workload | Python seconds | compiled seconds | Python decisions/s | compiled decisions/s | paired median gain | positive pairs | bootstrap mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 0.664140 | 0.651093 | 192.730 | 196.592 | **+2.045%** | 15/15 | +1.895% to +2.975% |
| balanced strategy | 0.618706 | 0.611819 | 206.884 | 209.212 | **+1.006%** | 15/15 | +0.944% to +1.196% |

Random variants produced exact digest
`4ef9603055d56a1dc40e81ba6830b56ca0a9fe01844095d3f040802d68e56381`;
strategy variants produced
`b073a56fee0d23e290c8eceb8938316c07cb8d2589356c24c76f55bc039cb621`.

## Exactness and static gates

- 10,000 seeded randomized Python/compiled comparisons pass. The retained
  Python row implementation itself has 10,000 randomized and six explicit
  boundary comparisons against the original full scan.
- A no-Numba unit test proves the wrapper takes the exact Python fallback.
- Python and compiled variants under scalar/off, shadow, and optimized/on all
  produce fixed-seed digest
  `6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e`.
  Each shadow variant records one comparison and zero mismatches.
- 750 route/path/river/bridge/enabled-interaction/targeting/collision/action-mask
  tests pass in 8.30 seconds.
- Ruff passes for all owned files; both benchmark drivers `py_compile`; and
  `git diff --check` passes.
- Mypy reports only inherited findings: four `card_types.py` annotation errors,
  the existing untyped optional-Numba import, and nine existing dynamic Entity
  route-cache attributes. No finding is on a line owned by this change.

## Integration

Cherry-pick the isolated commit. If `pathfinding.py` conflicts, port the
`_USE_COMPILED_NATIVE_ROUTE_GOAL` switch, compiled raw kernel and exact fallback
wrapper, separate Python-reference cache, and the small dispatch inside
`native_route_goal_cell`. Keep `_cached_native_route_goal_cell_units` as the
compiled production cache so existing cache metrics and compatibility remain
unchanged. No observation, action, reward, legal mask, RNG, CLI, fingerprint,
checkpoint, or corpus format changes are required.
