# Cached exact mover hover trait

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `b60c362`

## Change

Every `Entity` already classifies its data-driven hover movement trait once in
`Entity.__post_init__`. The hot `BattleState.is_ground_position_walkable`
predicate nevertheless reopened the immutable serialized card dictionaries and
normalized fallback names on every call. It now reuses the entity-owned boolean.

The reference path remains available to the benchmark and parity tests. There
are no card, deck, policy, action, reward, or enabled-interaction branches; the
classification source and fallback rules are unchanged.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, training, checkpoint, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guards before accepted timing commands
- seven alternating oracle repetitions; candidate-first production confirmation

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_cached_hover_trait.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates runtime/cached order. Its digest includes before/after
planner state keys, both selected actions, battle RNG before/after every label,
and the complete final planner RNG.

| hover classification | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| serialized runtime lookup | 1.114008 | 1.115201 | 0.003746 | 2.692980 |
| entity-cached trait | 1.105165 | 1.108397 | 0.009080 | 2.714527 |

Cached classification improves exact oracle throughput by **0.80%** and
reduces median wall time by 0.79%. All fourteen rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

Each variant used one environment, 64 decisions, nine repetitions after two
untimed warmup decisions, two Torch threads, exact fast mode, and all preceding
optimizations. The candidate ran before the reference in each workload.

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
  --mover-hover-trait {runtime,cached}

# Repeat with --workload strategy --strategy balanced.
```

| workload | runtime seconds / decisions/s | cached seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.425548 / 150.394433 | 0.417512 / 153.288915 | **+1.93%** |
| balanced strategy | 0.495042 / 129.282058 | 0.489722 / 130.686478 | **+1.09%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Runtime measured 0.122911 seconds / 520.704 ticks/s;
cached measured 0.121616 seconds / 526.246 ticks/s, a **+1.06%** improvement.
Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
6 data-lookup/avoidance/off-shadow-on fixed-seed cases passed
154 targeting/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest
  9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349
shadow checks = 1 per trial; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions py_compile clean
git diff --check clean
```

`battle.py` retains 21 pre-existing mypy findings (untyped numba plus existing
dynamic entity attributes); this change adds no finding at the edited lines.

## Integration

Cherry-pick after `b60c362`. The production source change is limited to the
benchmark switch and cached `_is_hover_unit` read in
`BattleState.is_ground_position_walkable`. Existing stationary/crowded drivers
only gain `--mover-hover-trait`; the dedicated oracle driver and test are
standalone. If `battle.py` conflicts, exclude the optimizer worktree's separate
uncommitted alive-building refresh-reuse hunk.
