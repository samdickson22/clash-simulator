# Dense native-route storage optimization

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

The candidate specializes standard-arena routing with fixed row-major storage:

- immutable 2,304-cell cost tuples;
- integer cell IDs in the native binary heap;
- fixed parent/priority lists and a discovered bytearray;
- unchanged native neighbor order and right-before-left heap comparisons;
- fallback to the generic reference route for out-of-bounds endpoints.

It does not change route-cache keys, path retention, movement, or arena data.

There are no card names or enabled-deck branches.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, Darwin arm64, Python 3.12.13. The host had
no live Clasher or RoadForge worker. All benchmarks were single-process CPU
runs. Candidate/reference order alternated by repetition, and lazy cost-grid
construction was included in every run.

Crowded-engine command:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_native_route_grid.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 7
```

Each run had 187 route-cache misses.

| mode | median seconds | mean seconds | stdev | median ticks/s |
| --- | ---: | ---: | ---: | ---: |
| immutable map | 0.310485 | 0.310778 | 0.002113 | 206.128927 |
| dense storage | 0.268761 | 0.268895 | 0.001745 | 238.130157 |

Dense storage improves this route-miss-heavy workload by 15.52%. All 14 runs
produced exact state hash
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

Production-shaped stationary-rollout commands:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_native_route_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 7 --warmup-steps 8 --torch-threads 2
PYTHONPATH=src:. uv run python scripts/perf/benchmark_native_route_rollout.py \
  --workload strategy --strategy balanced --seed 2301 --num-envs 1 \
  --rollout-steps 64 --repetitions 7 --warmup-steps 8 --torch-threads 2
```

| workload | map median seconds | dense median seconds | map decisions/s | dense decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.556473 | 0.546077 | 115.010107 | 117.199535 | 1.90% |
| balanced strategy | 0.591705 | 0.585999 | 108.162029 | 109.215173 | 0.97% |

All 14 random rows produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
all 14 strategy rows produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.
The end-to-end gains are smaller because these workloads incurred only 22 and
5 route misses respectively and include inference, observations, and masks.

## Exactness

```text
16 direct cost/route/hash tests passed
46 route/river/bridge/hover tests passed
44 targeting/target-switch/action-mask tests passed
Ruff clean excluding pre-existing UP037 annotations
mypy retains only the same 9 dynamic Entity attribute errors
py_compile and diff-check clean
```

The reference/off/shadow/on 64-decision fixed-seed digest remains
`6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e`,
with zero shadow mismatches. The crowded hash remains
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

The direct route tests compare the full returned cell sequence for lane IDs 0,
1, and 2, both jump-height profiles, 16 start/goal pairs per profile. Standard
map exactness still exhaustively covers every standard cell.

## Integration

Cherry-pick the isolated commit. It changes only shared pathfinding internals,
focused exact tests, two bounded benchmark drivers, and this report. It does not
change any CLI, corpus metadata, planner configuration, observation, action,
reward, RNG, or checkpoint format.
