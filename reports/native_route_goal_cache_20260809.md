# Exact native route-goal cache

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

`native_route_goal_cell` is a pure integer geometry function of mover
coordinates, target coordinates, and required range on the immutable standard
arena. Exact oracle branches revisit the same geometry across cloned states,
but the engine previously repeated the complete y-major/x-minor candidate scan
for every visit.

The calculation is now extracted into an unchanged integer reference function
and wrapped by a bounded 32,768-entry LRU. The key contains exactly five
integers: mover x/y, target x/y, and required range in logic units. Target
identity, card name, deck, policy, collision radius, and RNG do not participate
because the native route-goal rule itself does not consult them. Eviction can
only cause an exact recomputation.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU or checkpoint/corpus writes
- fixed battle seed 2301 and oracle seed 901
- five paired repetitions with alternating reference/candidate order
- complete trainer/actor/module-eval process guard before and after accepted runs

Several earlier runs were discarded: two overlapped newly launched training or
module-form evaluation workers, and one post-guard matched quoted process text
rather than an executable. The accepted runs followed a continuous 30-second
quiescence window and used an executable-prefix guard for actual `uv`/Python
Clasher commands. Their low variance and pre/post guards were clean.

## Cold-cache exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_route_goal_cache.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on --cache-state cold
```

Every candidate row began with an empty cache. The digest includes before/after
planner state keys, both action labels, battle RNG before/after every label,
and the complete final planner RNG.

| mode | median seconds / 3 labels | mean | stdev | median labels/s | hits / misses | final entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| uncached | 1.450416 | 1.450926 | 0.002959 | 2.068372 | 0 / 0 | 0 |
| cold cache | 1.278808 | 1.279968 | 0.003331 | 2.345935 | 5,146 / 2,463 | 2,463 |

The cold-cache exact oracle rate improves by **13.42%** with a 67.6% hit rate
inside each independent three-label row. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Warm-cache exact oracle labels

The same driver with `--cache-state warm` populated all fixed snapshots once
before timing and preserved the cache across reference rows.

| mode | median seconds / 3 labels | mean | stdev | median labels/s | hits / misses | entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| uncached | 1.461257 | 1.473010 | 0.024679 | 2.053026 | 0 / 0 | 2,463 |
| warm cache | 1.235482 | 1.246003 | 0.022376 | 2.428202 | 7,609 / 0 | 2,463 |

The warmed exact oracle rate improves by **18.27%**. Every paired candidate was
faster, and all rows produced the same complete digest as the cold run.

## End-to-end stationary rollouts

Each process began with an empty cache and ran eleven repetitions after eight
untimed warmup decisions.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_route_goal_cache.py \
  --native-route-goal-cache {off,on} --workload random --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on

PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_route_goal_cache.py \
  --native-route-goal-cache {off,on} --workload strategy \
  --strategy balanced --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 11 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on
```

| workload | uncached seconds | cached seconds | uncached decisions/s | cached decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.457613 | 0.440051 | 139.856243 | 145.437743 | **+3.99%** |
| balanced strategy | 0.510652 | 0.503458 | 125.329950 | 127.120717 | **+1.43%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

```text
8 direct range/boundary/cache-hit/scalar-off/shadow/optimized-on cases passed
109 native-path/route/river/bridge/lane tests passed
99 targeting/collision/action-mask/pathfinding exactness tests passed
pinned scalar/off, shadow, and optimized/on rollout hashes unchanged
shadow checks > 0; shadow mismatches = 0
Ruff and py_compile clean excluding inherited UP037/BLE001 findings
pathfinding.py has only the same Numba-stub plus 9 dynamic Entity field mypy findings
git diff --check clean for owned changes
```

## Integration

Cherry-pick the isolated commit. If `pathfinding.py` conflicts, port the
`_USE_NATIVE_ROUTE_GOAL_CACHE` switch, integer reference helper, bounded cached
wrapper, and the small public adapter that constructs the five-integer key.
The remaining files are the direct test, two bounded benchmark drivers, and
this report. No observation, action, reward, policy, RNG, checkpoint, corpus,
or fingerprint format changes are required.
