# Coalesced exact target-plane checks

Date: 2026-08-09

## Scope

The post-`e3f1d64` oracle profile showed 1,037,907 calls / 279 ms in the shared
dynamic air/ground predicate. Four general target eligibility paths called
that pure predicate once to reject air and again to reject ground. They now
classify the candidate once per decision and reuse the boolean. The predicate
itself remains unchanged, including permanent air units, river jumps, and
airborne Mega Knight leap phases. A private switch retains the repeated path
for matched A/B proof; there are no card-name or enabled-deck branches.

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
  scripts/perf/benchmark_oracle_coalesced_target_plane.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

| plane classification | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| repeated | 1.033880 | 1.032188 | 0.003200 | 2.901692 |
| coalesced | 1.027611 | 1.027663 | 0.002620 | 2.919393 |

Coalescing improves exact oracle throughput by **0.61%**. Every row produced
the same action, battle state, battle RNG, and final planner RNG digest:
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
  --collision-radius cached --target-plane-checks {coalesced,repeated}

# Repeat with --workload strategy --strategy balanced.
```

| workload | repeated seconds / decisions/s | coalesced seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.401121 / 159.552969 | 0.397332 / 161.074467 | **+0.95%** |
| balanced strategy | 0.471599 / 135.708599 | 0.470272 / 136.091453 | **+0.28%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight probe measured 0.102019 seconds /
627.336 ticks/s coalesced versus 0.101847 seconds / 628.396 ticks/s repeated,
a **-0.17%** result. This is neutral within the short-run noise and is not
claimed as a gain. Both variants produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

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
  --unit-mass cached --collision-radius cached \
  --target-plane-checks {coalesced,repeated}
```

## Exactness gates

```text
3 off/shadow/on fixed-seed A/B cases passed
22 focused air/ground/target-plane cases passed in the preflight
104 targeting/cache/avoidance/collision/action-mask/clone/batched/determinism tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest
  9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349
shadow checks = 1 per trial; shadow mismatches = 0
new test and oracle driver Ruff/format/py_compile clean
existing benchmark-driver additions py_compile clean
git diff --check clean
```

## Integration

Cherry-pick after `e3f1d64`. Production source changes only the four generic
eligibility blocks; the dynamic predicate and all legal targeting rules remain
unchanged. Existing stationary and crowded drivers gain
`--target-plane-checks`; the dedicated oracle driver, fixed-seed test, and
this report are standalone.
