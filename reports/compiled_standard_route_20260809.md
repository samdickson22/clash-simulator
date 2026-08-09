# Exact compiled standard-route heap

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

The immutable standard-arena route cache still had 711 unique entries after a
12-label sequential oracle probe, well below its 2,048-entry capacity. Cache
size was therefore not the bottleneck. On misses, the exact Python
first-discovery binary heap remained allocation-heavy: 137 calls consumed
0.233 seconds inside one profiled production-shape label.

The candidate implements the same fixed neighbor order, first-discovery rule,
priority recurrence, right-before-left heap comparison, equal-priority
retention, and parent-chain reconstruction in a Numba dense-array kernel. The
existing Python implementation remains the exact fallback when Numba is
unavailable and is selectable by a private benchmark switch. Numba is already
a declared project dependency and is already used by the simulator's placement
mask kernel.

The kernel reads an immutable cached terrain-cost array and returns only route
cell indices. It does not observe or mutate battle state and consumes no RNG.
There are no card, deck, player, or enabled-interaction branches.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, macOS 26.5.2 arm64, Python 3.12.13, Numba
0.63.1. Every timing command was single-process CPU-only. A full-command-line
guard immediately before each command rejected live Clasher training,
evaluation, DAgger, and multiprocessing workers. Numba compilation was warmed
outside measured rows. Variant order alternated for the oracle benchmark.

### Production-shape exact oracle

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_compiled_route.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

Each variant starts every row with an empty 2,048-entry route cache. Both have
exactly 141 misses and 229 hits per row. The three snapshots include the
initial state and deterministic random-action successors. The digest includes
before/after planner state keys, joint action labels, complete input-battle RNG
before/after each label, and complete final planner RNG.

| route heap | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| Python dense heap | 1.806694 | 1.805532 | 0.008109 | 1.660492 |
| compiled dense heap | 1.710262 | 1.706705 | 0.015090 | 1.754118 |

The compiled heap improves exact cold-route oracle throughput by **5.64%** and
reduces wall time by 5.34%. Every row produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

### Warm stationary controls

The existing stationary driver used seed 2301, one environment, 64 decisions,
eleven repetitions, eight warmup decisions, two Torch threads, and the exact
fast path. Separate fresh processes selected the route implementation; the
warmup and repeated rollouts populate the shared route LRU, so this is a
steady-state cache-hit control rather than a cold-route workload.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_compiled_route.py \
  --route-kernel {python,compiled} --workload random --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on

PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_compiled_route.py \
  --route-kernel {python,compiled} --workload strategy --strategy balanced \
  --seed 2301 --num-envs 1 --rollout-steps 64 --repetitions 11 \
  --warmup-steps 8 --torch-threads 2 --engine-fast-path on
```

| workload | Python seconds | compiled seconds | Python decisions/s | compiled decisions/s | change |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.537816 | 0.541147 | 118.999733 | 118.267419 | -0.62% |
| balanced strategy | 0.597292 | 0.595319 | 107.150197 | 107.505335 | +0.33% |

These noise-sized controls show no claimable warm-cache throughput change, as
expected: an LRU hit returns before either route heap executes. Both random
variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
both strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

The dedicated kernel test compares Python and compiled routes for 162 fixed
start/goal/lane/jump combinations, including both corners and start-equals-goal.
The broader rollout gate pins scalar/off, shadow, and optimized/on hashes against
the generic mapping-based route reference.

```text
17 dedicated compiled/reference/cache/cost-map tests passed
83 route/path/river/bridge interaction tests passed
52 targeting/collision/action-mask/scalar-shadow tests passed
pinned scalar/off, shadow, and optimized/on rollout digest unchanged
shadow checks > 0; shadow mismatches = 0
Ruff and py_compile clean for owned source, tests, and benchmark drivers
pathfinding mypy retains only the same three pre-existing nested-helper Any errors
git diff --check clean
```

## Integration

Cherry-pick the isolated commit. The production source change is confined to
`pathfinding.py`; the remaining files are an exactness test, two reproducible
benchmark drivers, and this report. No CLI, observation, action, reward,
fingerprint, corpus, or checkpoint-format change is required.
