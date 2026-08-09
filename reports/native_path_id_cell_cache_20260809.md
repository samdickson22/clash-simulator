# Exact native path-ID cell cache

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

`nearest_native_path_id` previously rescanned the complete immutable 36x64
standard path map for every no-other-object lookup. In that mode the result
depends only on the source half-tile cell. The candidate caches the exact
first-nearest result by `(source_cell_x, source_cell_y)` and uses a bounded
2,304-entry LRU, matching the standard arena's cell count.

Calls that provide `other_x_units` retain the original full scan because their
center-crossing tie behavior depends on the second object's position. The
cache contains only integer path IDs derived from immutable serialized map
data. It adds no card, deck, policy, or mechanic branch and consumes no RNG.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU or checkpoint/corpus writes
- full-command process guard immediately before every timed invocation
- fixed battle seed 2301 and oracle seed 901

The cold oracle benchmark alternated reference/candidate order for five paired
repetitions. It cleared the candidate cache before every measured row; each
three-label row therefore includes all initial fill work.

## Cold-cache exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_native_path_id_cache.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on --cache-state cold
```

The digest includes before/after planner state keys, both action labels,
battle RNG before/after every label, and the complete final planner RNG.

| mode | median seconds / 3 labels | mean | stdev | median labels/s | hits / misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| full scan | 1.685364 | 1.673011 | 0.033723 | 1.780031 | 0 / 0 |
| cold cell cache | 1.665666 | 1.654362 | 0.051470 | 1.801081 | 39 / 147 |

The conservative cold-cache rate improves by **1.18%**, and the candidate was
faster in all five matched pairs. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Warm-cache exact oracle labels

The first warm attempt was discarded because its reference rows inadvertently
cleared the candidate cache. After the 64-environment population phase exited,
the corrected driver fully warmed all three fixed snapshots once, preserved
the cache across alternating reference rows, and reported per-row deltas.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_native_path_id_cache.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on --cache-state warm
```

| mode | median seconds / 3 labels | mean | stdev | median labels/s | hits / misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| full scan | 1.479835 | 1.479559 | 0.004846 | 2.027253 | 0 / 0 |
| warm cell cache | 1.455054 | 1.455018 | 0.002151 | 2.061779 | 186 / 0 |

The warmed exact oracle rate improves by **1.70%**, and the candidate was
faster in all five matched pairs. All ten rows produced the same complete
digest as the cold run.

## End-to-end stationary rollouts

Each process began with an empty cache and used eleven repetitions with eight
untimed warmup decisions.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_native_path_id_cache.py \
  --native-path-id-cache {off,on} --workload random --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on

PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_native_path_id_cache.py \
  --native-path-id-cache {off,on} --workload strategy \
  --strategy balanced --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 11 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on
```

| workload | full-scan seconds | cached seconds | full-scan decisions/s | cached decisions/s | change |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.460105 | 0.460884 | 139.098533 | 138.863626 | -0.17% |
| balanced strategy | 0.518528 | 0.514688 | 123.426364 | 124.347288 | +0.75% |

The random result is noise-scale and is not claimed as a throughput gain.
Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

```text
5 direct exhaustive/tie/scalar-off/shadow/optimized-on cases passed
101 native-path/route/river/bridge/lane tests passed
91 targeting/collision/action-mask/pathfinding exactness tests passed
every standard cell plus two-cell perimeter matches the full scan
other-object center-crossing tie scan remains on the reference implementation
fixed rollout hashes unchanged; shadow mismatches = 0
native_tilemap.py mypy clean
Ruff and py_compile clean excluding the inherited PLR1730 reference-scan style
git diff --check clean for owned changes
```

## Integration

Cherry-pick the isolated commit. If `native_tilemap.py` conflicts, port the
bounded cell-cache helper and the no-other-object early return; retain the
reference scan unchanged for calls with `other_x_units`. The remaining files
are the direct test, two bounded benchmark drivers, and this report.
