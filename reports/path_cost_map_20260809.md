# Immutable standard-arena path-cost map optimization

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Profile finding

A production-shape depth-6, 32-simulation oracle profile spent 0.639 seconds in
137 cold `_native_grid_route` calls. Each expanded neighbor recomputed an
immutable standard-arena movement cost through a Python lambda,
`_standard_pathfinder_tile_cost`, bounds checks, blocked-tile lookup, and lane
row decoding.

Standard-arena tile costs depend only on `(lane_id, jump_height)`. The candidate
lazily builds an immutable `MappingProxyType` cost map for that movement profile
and passes its C-level `get` method to the unchanged native route algorithm. A
16-entry LRU bounds memory even for unusual future lane identifiers. Route
discovery, heap topology, parents, priorities, neighbor order, and returned
route cells are unchanged.

There are no card names or enabled-deck branches.

## Benchmark

Machine: Apple M4 Pro, 24 GiB RAM, Darwin arm64, Python 3.12.13.

Command:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_path_cost_map.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 7
```

The single-process benchmark alternates baseline/candidate ordering. Every run
starts with an empty 2,048-route cache; candidate runs also start with an empty
cost-map cache, so lazy map construction is included. Each run has 187 route
misses.

| mode | median seconds | mean seconds | stdev | median ticks/s |
| --- | ---: | ---: | ---: | ---: |
| reference per-neighbor cost | 0.405881 | 0.405645 | 0.000954 | 157.681750 |
| immutable cost map | 0.313528 | 0.313774 | 0.001039 | 204.128743 |

This is a 29.46% crowded-engine throughput gain. All 14 measured runs produced
the established exact crowded-state hash:

```text
d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb
```

An 80-route fixed-seed kernel probe separately measured 0.218292 seconds for
the reference and 0.129238 seconds for the warmed cost map, identical route hash
`1884d3bd3ad00afabf6caec49d1a803dd2b49d5c6e678a073cf1279414256197`.

On a broader three-state oracle A/B, the median change was only +0.32% amid high
run variance. Attribute the measured material gain specifically to route-miss-
heavy simulation, not all corpus states.

## Exactness

The map test exhaustively compares all standard cells for lane IDs 0, 1, and 2
with both jump-height values, checks out-of-bounds behavior, and proves the map
is immutable. Cached route tests compare complete routes against the reference
algorithm.

Fixed rollout configuration: seed 4321, 64 decisions, 8 ticks, defense-v2.
Reference, scalar/off, shadow, and optimized/on all produced:

```text
6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
```

Shadow checks: 1; shadow mismatches: 0.

Focused gates:

```text
46 route/river/bridge/hover tests passed
44 targeting/target-switch/action-mask tests passed
1 explicit reference/off/shadow/on digest test passed
Ruff clean excluding the same pre-existing UP037 forward annotations
py_compile clean for benchmark_path_cost_map.py
mypy adds no errors; pathfinding retains its same 9 dynamic Entity attributes
git diff --check clean
```

## Integration

Cherry-pick the isolated commit. It changes only:

- `src/clasher/pathfinding.py`: add `_standard_path_cost_map` and use its `.get`
  inside `_cached_standard_grid_route`;
- exact route and fixed-seed parity tests;
- the bounded reproducible benchmark and this report.

No CLI, corpus metadata, fingerprint, simulator semantics, or checkpoint format
changes are required. Existing route-cache clear controls remain valid; the
cost-map cache is independent static arena data and can be cleared explicitly in
attribution benchmarks through `_standard_path_cost_map.cache_clear()`.
