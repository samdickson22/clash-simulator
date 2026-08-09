# Allocation-free exact bucket candidate ordering

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `2ea83d7`

## Change

`BattleState.iter_entities_in_radius` already owns a newly built candidate
list. Restoring native entity encounter order with `sorted(out, key=lambda ...)`
allocated a second list and a fresh lambda on every target, collision, and
avoidance radius query. The fast path now sorts `out` in place with one shared
`operator.attrgetter("id")` key and returns that same list.

The key, ascending order, stable tie behavior, candidates, and caller-visible
result values are unchanged. There are no card, deck, policy, action, reward,
or enabled-interaction branches.

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
  scripts/perf/benchmark_oracle_bucket_sort.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates allocated/in-place order. Its digest includes
before/after planner state keys, both selected actions, battle RNG before/after
every label, and the complete final planner RNG.

| bucket ordering | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| second allocated list | 1.145957 | 1.147098 | 0.002493 | 2.617899 |
| in-place list | 1.137686 | 1.137241 | 0.002457 | 2.636932 |

In-place ordering improves exact oracle throughput by **0.73%** and reduces
wall time by 0.72%. All fourteen rows produced digest
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
  --inactive-stealth-time deferred --bucket-id-sort {allocated,inplace}

# Repeat with --workload strategy --strategy balanced.
```

| workload | allocated seconds / decisions/s | in-place seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.422706 / 151.405513 | 0.420480 / 152.207062 | **+0.53%** |
| balanced strategy | 0.495772 / 129.091544 | 0.492859 / 129.854484 | **+0.59%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Allocated measured 0.123726 seconds / 517.272 ticks/s;
in-place measured 0.124008 seconds / 516.094 ticks/s, a **−0.23%** result.
Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.
This small-list crowded microcase does not benefit; the improvement is
attributed to allocation-heavy oracle and stationary rollout workloads.

## Exactness gates

```text
4 direct ordering and off-shadow-on fixed-seed cases passed
92 targeting/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest remains
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks are positive; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions checked with inherited EXE001/UP012 excluded
git diff --check clean
```

## Integration

Cherry-pick after `2ea83d7`. The production source change is limited to the
shared ID key, benchmark switch, and in-place sort branch in
`iter_entities_in_radius`. Existing stationary/crowded drivers only gain the
`--bucket-id-sort` selector. The dedicated oracle driver and test are
standalone. If `battle.py` conflicts, do not port the unrelated live-building
cache hunk from this optimizer worktree.
