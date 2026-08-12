# Exact cached strategy tile fits

Date: 2026-08-11

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

After direct canonical action geometry, a strategy opponent still recomputed
the same defense and enemy-cluster Gaussian fits for every legal hand-slot
action at a canonical tile. Deployment grids overlap heavily between slots.

The candidate allocates one 576-entry selection-local list and publishes the
exact `(defense_fit, cluster_fit)` pair the first time a canonical tile is
scored. Later legal slots at the same tile reuse that tuple. Cache lifetime is
one `select_action` call, so public situation changes cannot stale it.

Scores, stable action-ID tie breaking, legal actions, observations, rewards,
battle state, RNG, and policy semantics are unchanged. The mechanism is shared
by all six strategy modes and contains no card-name or deck-specific branches.

## Machine and shared-load controls

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM, macOS 26.5.2 arm64
- Python 3.12.13 through `uv`
- all timings single-process CPU-only with two Torch threads for rollouts
- alternating reference/candidate order; commands used `nice -n 15`
- one RoadForge CPU reconstruction shared the host; no optimizer-owned model
  training or MPS work was launched

## Direct balanced-strategy attribution

```bash
nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_strategy_action_geometry.py \
  --comparison tile-fit-cache --strategy balanced --seed 2301 \
  --selections 64 --repetitions 11 --warmup-selections 4
```

| tile fits | median seconds | mean | stdev | median selections/s |
| --- | ---: | ---: | ---: | ---: |
| uncached | 0.055180 | 0.055405 | 0.000534 | 1,159.847 |
| cached | 0.038049 | 0.038209 | 0.000363 | 1,682.043 |

The cache improves median selection rate by **45.02%**. The paired median was
45.02%, mean 45.01%, approximate two-sided 95% interval 44.68% to 45.33%, and
all 11 pairs were positive. Every action sequence matched digest
`5356c3fc1ff9b65b14a546c11873ca10a7c7d7f305dce605fbd2274110bbc88e`.

## Production-shaped stationary rollouts

Both screens fixed the previously verified direct canonical geometry on and
alternated only uncached/cached tile fits.

```bash
nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_strategy_action_geometry_rollout.py \
  --comparison tile-fit-cache --strategy balanced --seed 2301 \
  --num-envs 8 --rollout-steps 16 --repetitions 11 \
  --warmup-steps 8 --torch-threads 2 --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_strategy_action_geometry_rollout.py \
  --comparison tile-fit-cache --strategy balanced --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 7 \
  --warmup-steps 8 --torch-threads 2 --engine-fast-path on
```

| workload | uncached seconds / decisions/s | cached seconds / decisions/s | median-rate gain | paired median | positive pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 envs x 16 decisions | 0.635614 / 201.380 | 0.616794 / 207.525 | **+3.05%** | +3.17% | 11/11 |
| 1 env x 64 decisions | 0.451969 / 141.603 | 0.443045 / 144.455 | **+2.01%** | +2.40% | 7/7 |

The eight-environment paired mean interval was +2.71% to +3.85%; the
one-environment interval was +1.62% to +3.21%. The respective full-rollout
digests were
`d87bdd871c9bb012c55aff818085f7da385061d83e445c632a601bdb23737590`
and
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

Random opponents do not execute `StrategyBot`; no change is claimed there.

## Exactness gates

The direct test compares every legal score for all six strategies and both
players, verifies complete environment NumPy RNG state, and proves the cache
contains fewer entries than legal actions. Fixed action traces cover six
successive joint decisions for every strategy in scalar/off, shadow, and
optimized/on modes.

```text
84 tile-cache, direct-geometry, strategy, and PFSP tests passed
all score floats and action traces matched exactly
Ruff and py_compile clean for owned files
strategy_bots.py mypy clean
git diff --check clean
```

Uncached/cached and scalar/shadow/on 32-decision rollouts all produced digest
`500a76e31cb0d8112664d047b445afa16d695d8adf0e68965fe94ede2a75c475`.
Shadow performed one comparison per variant with zero mismatches.

## Integration

As with `76727f9`, `strategy_bots.py` is an inherited untracked pipeline file
in f872. The isolated handoff commit therefore carries the exact test, updated
benchmark support, and this report without capturing unrelated PFSP source.
Manually port these narrow changes into the authoritative tracked file:

1. add `_USE_CACHED_STRATEGY_TILE_FITS = True` beside the geometry A/B switch;
2. in `select_action`, allocate `[None] * NUM_TILES` when enabled and pass the
   same list into every `_score_action` call for that selection;
3. add an optional `tile_fit_cache` parameter to `_score_action`;
4. obtain `tile = action_id % NUM_TILES` in both geometry branches;
5. look up the tile before the two existing `_gaussian_distance` calls, publish
   their exact pair on a miss, and unpack it on a hit.

No CLI, corpus, metadata, checkpoint, observation, reward, or PPO-policy format
change is required.
