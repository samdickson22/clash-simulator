# Cached exact Entity collision radius

Date: 2026-08-09

## Scope

An updated oracle profile on the `4b247d4` baseline attributed 223,877 calls
and 71 ms to `Entity.get_collision_radius()`. Collision radius comes from
immutable normalized card data, so every `Entity` now publishes the exact
existing `float(radius or 0.5)` result once at construction. The public helper
remains compatible, and a private switch retains the prior resolver for
matched A/B checks. The change is shared and data-driven; it contains no card
or enabled-deck branch.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13 through `uv`
- single-process CPU only; no MPS/GPU
- candidate-first stationary and crowded probes
- seven alternating oracle repetitions per variant after one warmup state
- nine stationary repetitions per variant after two warmup decisions
- fifteen crowded repetitions per variant

## Exact oracle planner

```bash
PYTHONPATH=src:scripts/perf:. uv run python \
  scripts/perf/benchmark_oracle_cached_collision_radius.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The digest covers selected actions, state key before and after selection,
battle RNG before and after, and final complete planner RNG state.

| radius resolution | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| runtime resolver | 1.057920 | 1.057442 | 0.002829 | 2.835753 |
| Entity cache | 1.052700 | 1.053640 | 0.002231 | 2.849816 |

The cache improves exact oracle throughput by **0.50%** and reduces median
wall time by 0.49%. Every A/B row produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 9 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership cached \
  --crown-distance-order preferred-first \
  --inactive-stealth-time deferred --bucket-id-sort inplace \
  --targetability-fields direct --bucket-scan-order row-major \
  --bucket-geometry cached --building-membership trusted \
  --mover-hover-trait cached --avoidance-candidates bucketed \
  --collision-plane-fields direct --unit-mass cached \
  --collision-radius {cached,runtime}

# Repeat with --workload strategy --strategy balanced.
```

| workload | runtime seconds / decisions/s | cached seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.402517 / 158.999660 | 0.398951 / 160.420670 | **+0.89%** |
| balanced strategy | 0.475762 / 134.520948 | 0.475489 / 134.598159 | **+0.06%** |

The strategy result is neutral within run noise and is not counted as a
meaningful gain. Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_crowded_engine.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 15 \
  --mode on --target-cache-refresh reuse --building-cache-refresh reuse \
  --targetability-refresh classified --crown-fallback-membership cached \
  --crown-distance-order preferred-first --inactive-stealth-time deferred \
  --bucket-id-sort inplace --targetability-fields direct \
  --bucket-scan-order row-major --bucket-geometry cached \
  --building-membership trusted --mover-hover-trait cached \
  --avoidance-candidates bucketed --collision-plane-fields direct \
  --unit-mass cached --collision-radius {cached,runtime}
```

Runtime resolution measured 0.103182 seconds / 620.261 ticks/s; the cache
measured 0.102871 seconds / 622.136 ticks/s, a **+0.30%** improvement. Both
produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
7 resolver/custom-data/off-shadow-on fixed-seed cases passed
101 targeting/cache/avoidance/collision/action-mask/clone/batched/determinism tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest
  9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349
shadow checks = 1 per trial; shadow mismatches = 0
new test and oracle driver Ruff/format/py_compile clean
existing benchmark-driver additions py_compile clean
git diff --check clean
```

## Integration

Cherry-pick after `4b247d4`. Production source is limited to one immutable
cached field, its construction-time initialization, and the established public
radius helper. Existing stationary and crowded drivers gain
`--collision-radius`; the dedicated oracle driver, fixed-seed test, and this
report are standalone.
