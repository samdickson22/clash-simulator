# Exact row-interval native route-goal selection

Date: 2026-08-12

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Machine: Mac mini, Apple M4 Pro (12 cores: 8 performance + 4 efficiency), 24 GB RAM, macOS 26.5.2 (25F84), Python 3.12.13.

## Change

`_compute_native_route_goal_cell_units` selected the half-tile center inside an attack-range circle that was closest to the mover by scanning every x/y cell in the circle's bounding square. On any fixed y row, legal x centers form one contiguous integer interval and squared mover distance is minimized by exactly one interval-clamped x center. The optimized implementation therefore evaluates one exact candidate per row.

The implementation preserves the original y-major/x-minor ordering and strict-smaller replacement rule. Half-grid ties select the lower x, matching the original scan. It uses integer `isqrt`, exact ceil/floor division, the same arena bounds and range predicate, and no card, deck, player, or enabled-interaction special case. The existing full scan remains available only as a private benchmark reference.

## Attribution

Fresh current-stack `cProfile` samples attributed the following self time to `_compute_native_route_goal_cell_units`:

- stationary random, 4 environments x 32 learner steps: 3,859 calls / 0.061 s;
- balanced strategy, 4 environments x 32 learner steps: 3,159 calls / 0.066 s;
- exact depth-6, 32-simulation oracle label: 4,577 calls / 0.086 s.

All timed commands below were single-process CPU-only, limited to one Torch/BLAS thread where applicable, and run at `nice -n 15`. Variant order alternated within every paired run. No MPS/GPU, model training, checkpoint, corpus, or multi-worker process was started.

## Exact oracle

```sh
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n15 \
  uv run python scripts/perf/benchmark_oracle_route_goal_row_interval.py \
  --seed 9033 --planner-seed 2033 --states 3 --state-stride 4 \
  --repetitions 11 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 --engine-fast-path on
```

| implementation | median seconds / 3 labels | median labels/s |
| --- | ---: | ---: |
| full grid scan | 0.911995 | 3.289490 |
| row interval | 0.856648 | 3.502023 |

The candidate reduces median wall time by 6.07% and improves median throughput by **6.46%**. The paired throughput median is **+6.461%**, all 11/11 pairs are positive, and the bootstrap mean 95% CI is +5.514% to +6.497%. Every row produced the same complete action/battle/planner-RNG digest: `5005c2a10a65d5e09a9e570234df68ce6d08c67f589e09ca47d5537659537f12`.

## Production-shaped stationary rollouts

Both workloads used 4 environments, 32 learner decisions per row, 24 untimed warmup decisions, 15 interleaved pairs, exact fast path, and `defense-v2` rewards.

```sh
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n15 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison native-route-goal-row-interval --workload random --seed 9033 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2

env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n15 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison native-route-goal-row-interval --workload strategy --strategy balanced --seed 9033 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2
```

| workload | full-scan seconds | row-interval seconds | full-scan decisions/s | row-interval decisions/s | paired median gain | positive pairs | bootstrap mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 0.658437 | 0.631489 | 194.400 | 202.696 | **+4.182%** | 15/15 | +4.053% to +4.381% |
| balanced strategy | 0.664773 | 0.642888 | 192.547 | 199.102 | **+3.423%** | 14/15 | +2.423% to +3.574% |

Random variants produced exact digest `3d412a1281f8be9c4730dc41d35707d3621ea0c7af72870e9edcff564c00981d`; strategy variants produced `be7ea1cb134abcd09c714dcc05533743002e7b032b7206cb4ec732ce54b4a0f0`.

## Exactness gates

- 10,000 seeded randomized coordinate/range comparisons plus six explicit boundary cases match the retained full scan exactly.
- Full-scan and row-interval modes under scalar/off, shadow, and optimized/on all produce fixed-seed digest `6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e`.
- Each shadow variant records one comparison and zero mismatches.
- 744 route/path/river/bridge/enabled-interaction/targeting/collision/action-mask tests pass.
- Ruff passes for the owned tests and benchmark drivers and for `pathfinding.py` excluding its pre-existing `BLE001`/`UP037` findings.
- `pathfinding.py` mypy retains only its four pre-existing optional-Numba/nested-helper findings; no new finding is on an owned line.
- `git diff --check` passes.

## Integration

Cherry-pick the isolated commit. If `pathfinding.py` conflicts, port the `_USE_ROW_INTERVAL_NATIVE_ROUTE_GOAL` switch, `_compute_native_route_goal_cell_units_row_interval`, the two separately bounded caches, and the small dispatch in `native_route_goal_cell`. The existing `_cached_native_route_goal_cell_units` name intentionally remains the production cache for compatibility with cache metrics/tests. No observation, action, reward, legal mask, RNG, CLI, fingerprint, checkpoint, or corpus format changes are required.
