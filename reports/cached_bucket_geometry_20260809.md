# Rebuild-published exact bucket geometry

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `9d2b662`

## Change

Every fast radius query recomputed the bucket inverse cell size, arena maximum
dimension, and integer grid bounds even though all are invariants of the bucket
grid currently being queried. `_rebuild_entity_buckets` now publishes those
values alongside the grid. Queries reuse the geometry produced by the same
rebuild, including custom cell sizes and arena dimensions.

The cache is mutable clone-owned state. Candidate cells, bucket contents,
final ID order, collisions, targets, and fallback behavior are unchanged.
There are no card, deck, policy, action, reward, or enabled-interaction
branches.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, training, checkpoint, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guards before and after accepted commands
- alternating oracle order plus both candidate-first and reverse-order
  stationary-random checks

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_bucket_geometry.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates recomputed/cached order. Its digest includes before/after
planner state keys, both selected actions, battle RNG before/after every label,
and the complete final planner RNG.

| geometry | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| recomputed per query | 1.127335 | 1.128072 | 0.001278 | 2.661143 |
| rebuild-published cache | 1.117667 | 1.118081 | 0.001644 | 2.684162 |

Cached geometry improves exact oracle throughput by **0.86%** and reduces
median wall time by 0.86%. All fourteen rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

Each variant used one environment, 64 decisions, two untimed warmup decisions,
two Torch threads, exact fast mode, and all preceding optimizations. The random
result below uses the conservative 11-repetition reverse-order confirmation;
the earlier candidate-first check measured +3.25%.

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 11 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership cached \
  --crown-distance-order preferred-first \
  --inactive-stealth-time deferred --bucket-id-sort inplace \
  --targetability-fields direct --bucket-scan-order row-major \
  --bucket-geometry {recomputed,cached}

# Strategy used nine repetitions with --workload strategy --strategy balanced.
```

| workload | recomputed seconds / decisions/s | cached seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.457358 / 139.934194 | 0.451933 / 141.613820 | **+1.20%** |
| balanced strategy | 0.539613 / 118.603508 | 0.535782 / 119.451540 | **+0.71%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Recomputed measured 0.126179 seconds / 507.216
ticks/s; cached measured 0.126463 seconds / 506.078 ticks/s, a **−0.22%**
result. Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.
The gain is attributed to oracle and production-shaped stationary rollouts,
not the small crowded microcase.

## Exactness gates

```text
7 custom-cell-size/clone/off-shadow-on fixed-seed cases passed
110 targeting/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest remains
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks are positive; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions checked with inherited EXE001/UP012 excluded
git diff --check clean
```

## Integration

Cherry-pick after `9d2b662`. Port the benchmark switch, four private bucket
geometry fields, rebuild publication, and guarded query reads. Existing
stationary/crowded drivers only gain `--bucket-geometry`; the dedicated oracle
driver and test are standalone. If `battle.py` conflicts, exclude the unrelated
live-building cache hunk from this optimizer worktree.
