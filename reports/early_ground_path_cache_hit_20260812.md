# Exact early retained-route cache hit (2026-08-12)

## Result

`ground_path_waypoint` now checks an ordinary ground unit's retained route as
soon as the desired goal cell and immutable route traits are known. A hit no
longer computes mover-to-reference origin distance, allocates the backwards
route closure, quantizes the mover's start cell, or recomputes the same cache
key later in the function. Route misses, hovering units, invalid goals, route
construction, node consumption, and backwards-path classification retain the
established code path.

The exact stable-root oracle improves **1.682% paired median** (11/11 positive,
bootstrap mean 95% confidence interval **1.582% to 2.029%**). Production-shaped
random rollout improves **0.798% paired median** (14/15, CI +0.500% to
+2.893%); balanced strategy improves **0.400%** (14/15, CI +0.130% to
+0.684%).

## Machine and controls

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- one process, one Torch/BLAS/OpenMP/Accelerate thread, `nice -n 15`
- no live Clasher/RoadForge worker during measurements
- alternating fixed-seed reference/candidate pairs after warmup

## Commands

Production-shaped random, then `strategy --strategy balanced`:

```text
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison early-ground-path-cache-hit --workload random --seed 9075 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2
```

Warm exact stable-root oracle:

```text
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 \
  uv run python scripts/perf/benchmark_oracle_route_goal_cache.py \
  --comparison early-ground-path-cache-hit --seed 9075 \
  --planner-seed 2075 --states 2 --state-stride 4 --repetitions 11 \
  --decision-interval 8 --planner-depth 6 --planner-simulations 32 \
  --planner-action-samples 64 --cache-state warm --engine-fast-path on
```

The oracle warmup runs every fixed snapshot before timing. All measured rows
record 17,203 route-goal cache hits, zero misses, and cache size 3,136; an
earlier confounded run that allowed one reference row to warm 425 entries is
excluded from attribution.

## Timings

| workload | late seconds | early seconds | late rate | early rate | paired median | positive pairs | bootstrap mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| exact oracle | 1.069936 | 1.052982 | 1.8693 labels/s | 1.8994 labels/s | **+1.682%** | 11/11 | +1.582% to +2.029% |
| random rollout | 0.705747 | 0.701703 | 181.368 decisions/s | 182.413 decisions/s | **+0.798%** | 14/15 | +0.500% to +2.893% |
| balanced strategy | 0.664025 | 0.660833 | 192.764 decisions/s | 193.695 decisions/s | **+0.400%** | 14/15 | +0.130% to +0.684% |

Reference/candidate random variants share digest
`47bc9674160db84ce73bee4b703453901ecda4af416544574bc4fa19c54f51aa`;
strategy variants share
`f4cce001d77f20060b8baddf22302ee0b0ac7994e539475796ebd5454376955c`;
oracle variants share the exact action/state/planner-RNG digest
`f0416f67fb50a59ad922367bf811f070ec138f24986341d8f7650890731fca15`.

## Exactness gates

- Late/early variants under scalar/off, shadow, and optimized/on all produce
  fixed-seed digest
  `6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e`.
  Each shadow run records one legacy action-mask check and zero mismatches.
- Focused tests prove retained-route state/waypoint parity and that the early
  hit does not quantize the mover start; off/shadow/on fixed-seed tests pass.
- 980 path/route/river/bridge/enabled-interaction/targeting/collision/
  action-mask/idle tests pass in 18.18 seconds.
- Owned test/benchmark files pass Ruff and benchmark drivers `py_compile`.
  `pathfinding.py` reports only the inherited optional-Numba/UP037 Ruff and
  existing dynamic Entity mypy findings; none is on an owned line.
- `git diff --check` passes.

## Integration

Cherry-pick the isolated commit. If `pathfinding.py` conflicts, port the
`_USE_EARLY_GROUND_PATH_CACHE_HIT` switch and the early block at the top of
`ground_path_waypoint`; leave the later reference block intact behind the
switch. The generic rollout driver gains one comparison mode and the oracle
route-cache driver gains a reusable `--comparison` selector.
