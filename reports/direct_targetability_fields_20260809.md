# Direct exact Entity targetability fields

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `32f963a`

## Change

The hot `Entity.is_targetable_by` predicate called
`_has_death_spawn_target_immunity` and defensively resolved the guaranteed
`mechanics` dataclass field with `getattr` for every candidate. It now reads
the same Entity-owned state directly. The death-spawn expression retains the
same global gate and nonnegative elapsed-time test; mechanic iteration retains
the same order and `blocks_targeting` behavior.

Alive, owner, entity-kind, hidden-building, mechanic, and stealth predicates
remain in their original order. There are no card, deck, policy, action,
reward, or enabled-interaction branches.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, training, checkpoint, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guards before and after accepted commands
- alternating oracle order and candidate-first production confirmation

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_direct_targetability.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates defensive/direct order. Its digest includes before/after
planner state keys, both selected actions, battle RNG before/after every label,
and the complete final planner RNG.

| field access | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| defensive helper/getattr | 1.174739 | 1.174282 | 0.002614 | 2.553759 |
| direct Entity fields | 1.163417 | 1.163779 | 0.002256 | 2.578610 |

Direct fields improve exact oracle throughput by **0.97%** and reduce wall
time by 0.96%. All fourteen rows produced digest
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
  --targetability-fields {defensive,direct}

# Repeat with --workload strategy --strategy balanced.
```

| workload | defensive seconds / decisions/s | direct seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.464498 / 137.783056 | 0.462849 / 138.274075 | **+0.36%** |
| balanced strategy | 0.536449 / 119.303084 | 0.532890 / 120.099880 | **+0.67%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Defensive measured 0.127473 seconds / 502.065 ticks/s;
direct measured 0.125674 seconds / 509.256 ticks/s, a **+1.43%** improvement.
Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
5 direct helper/death-immunity/mechanic/off-shadow-on cases passed
97 targeting/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest remains
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks are positive; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions checked with inherited EXE001/UP012 excluded
git diff --check clean
```

## Integration

Cherry-pick after `32f963a`. The production source change is limited to the
benchmark switch plus direct death-spawn/mechanics reads in
`Entity.is_targetable_by`. Existing stationary/crowded drivers only gain the
`--targetability-fields` selector. The dedicated oracle driver and test are
standalone.
