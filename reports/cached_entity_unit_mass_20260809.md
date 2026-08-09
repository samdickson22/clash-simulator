# Cached exact Entity collision mass

Date: 2026-08-09

## Scope

Native troop collision and avoidance repeatedly resolved collision mass from the
same immutable card/character data. Every `Entity` now publishes that exact
data-driven value once at construction, and the two hot paths reuse it. A
private benchmark switch retains the previous resolver path for matched A/B
evidence. There are no card-name branches in the optimization: construction
still uses the shared `unit_mass()` resolver, including explicit custom
`summonCharacterData.mass` values and its general fallback rules.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13 through `uv`
- single-process CPU only; no MPS/GPU
- candidate-first stationary and crowded probes
- seven alternating oracle repetitions per variant after one warmup state
- nine stationary repetitions per variant after two warmup decisions
- fifteen crowded repetitions per variant; the first route-cache warmup sample
  remains in the emitted rows but the median is unaffected
- all timings below completed before the next training-thread evaluation fan-out

## Exact oracle planner

```bash
PYTHONPATH=src:scripts/perf:. uv run python \
  scripts/perf/benchmark_oracle_cached_unit_mass.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

This hashes the selected actions, planner state key before and after each
selection, battle RNG before and after, and complete final planner RNG state.

| mass resolution | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| runtime resolver | 1.090599 | 1.089434 | 0.004263 | 2.750783 |
| Entity cache | 1.071508 | 1.071697 | 0.002451 | 2.799793 |

The Entity cache improves exact oracle throughput by **1.78%** and reduces
median wall time by 1.75%. Every A/B row produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

Each variant used one environment, 64 decisions, nine repetitions after two
warmup decisions, two Torch threads, exact fast mode, and all preceding
optimizations.

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
  --collision-plane-fields direct --unit-mass {cached,runtime}

# Repeat with --workload strategy --strategy balanced.
```

| workload | runtime seconds / decisions/s | cached seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.414285 / 154.482994 | 0.409296 / 156.366085 | **+1.22%** |
| balanced strategy | 0.486151 / 131.646329 | 0.483189 / 132.453449 | **+0.61%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant with the same shared-engine controls:

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
  --unit-mass {cached,runtime}
```

Runtime resolution measured 0.108674 seconds / 588.915 ticks/s; the cache
measured 0.104931 seconds / 609.926 ticks/s, a **+3.57%** improvement. Both
produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
7 resolver/custom-data/off-shadow-on fixed-seed cases passed
94 targeting/cache/avoidance/collision/action-mask/clone/batched/determinism tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest
  9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349
shadow checks = 1 per trial; shadow mismatches = 0
new test and oracle driver Ruff/format/py_compile clean
existing benchmark-driver additions py_compile clean
git diff --check clean
```

The canonical hash-only trace ran as a unit-sized check after a short external
CPU evaluation fan-out appeared; none of the performance measurements overlap
that fan-out.

## Integration

Cherry-pick this commit after `1a9bc55`. Production changes are limited to the
construction-time cached field and the two existing collision/avoidance mass
reads. Existing stationary and crowded drivers gain `--unit-mass`; the
dedicated oracle driver, fixed-seed test, and this report are standalone.
