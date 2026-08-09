# Trusted exact alive-building cache membership

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `7e28654`

## Change

Fast building-occupancy queries refresh `_alive_buildings`, whose contract and
construction guarantee that every member is a live `Building`. The subsequent
loop nevertheless repeated `isinstance` and `is_alive` checks for every cached
member. The fast candidate now trusts membership immediately after the exact
refresh; scalar and reference paths retain both defensive checks. Ignore-ID
and collision geometry remain unchanged.

There are no card, deck, policy, action, reward, or enabled-interaction
branches.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, training, checkpoint, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guards before and after accepted commands
- alternating oracle order and candidate-first plus reverse-order production
  checks; a visibly rate-collapsed strategy run was discarded

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_building_membership.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 11 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates defensive/trusted order. Its digest includes before/after
planner state keys, both selected actions, battle RNG before/after every label,
and the complete final planner RNG.

| membership | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| defensive rechecks | 1.101632 | 1.101627 | 0.002732 | 2.723231 |
| trusted refreshed cache | 1.098572 | 1.099479 | 0.002255 | 2.730817 |

Trusted membership improves exact oracle throughput by **0.28%** and reduces
median wall time by 0.28%. All twenty-two rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

Each variant used one environment, 64 decisions, eleven repetitions after two
untimed warmup decisions, two Torch threads, exact fast mode, and all preceding
optimizations.

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
  --bucket-geometry cached --building-membership {defensive,trusted}

# Repeat with --workload strategy --strategy balanced.
```

| workload | defensive seconds / decisions/s | trusted seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.414226 / 154.504997 | 0.411799 / 155.415722 | **+0.59%** |
| balanced strategy | 0.533077 / 120.057609 | 0.532570 / 120.171912 | **+0.10%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Defensive measured 0.125069 seconds / 511.716
ticks/s; trusted measured 0.125327 seconds / 510.666 ticks/s, a **−0.20%**
result. Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.
The gain is narrowly attributed to stationary-random collection and oracle
rollouts.

## Exactness gates

```text
7 cache-contract/defensive-parity/off-shadow-on fixed-seed cases passed
117 targeting/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest remains
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks are positive; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions checked with inherited EXE001/UP012 excluded
git diff --check clean
```

## Integration

Cherry-pick after `7e28654`. The production source change is limited to the
benchmark switch and guarded membership check in
`is_position_occupied_by_building`. Existing stationary/crowded drivers only
gain `--building-membership`; the dedicated oracle driver and test are
standalone. This commit does not include the optimizer worktree's separate
alive-building refresh-reuse candidate.
