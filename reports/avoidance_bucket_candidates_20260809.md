# Exact native-avoidance bucket candidates

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `cd1e2de`

## Change and coverage proof

`Troop._update_native_avoidance` scanned every battle entity for each active
movement component. Fast collision and targeting already maintain a spatial
bucket index whose candidate output is restored to exact entity-ID encounter
order. Native avoidance now uses the same index before applying its unchanged
alive/type/plane/distance/direction/mass predicates.

The query is centered on the mover and covers:

- at most 256 logic units from mover center to the forward probe;
- the attacker's probe radius, capped at 500 logic units exactly as before;
- the maximum live troop/building collision radius published by the exact
  target cache.

By triangle inequality, every entity whose collision body can overlap the
forward probe is inside that query. The existing bucket guard band covers
within-tick movement while bucket membership is awaiting its next rebuild, and
the final ID sort preserves the full dictionary scan's encounter order. Scalar
mode still uses the full scan. No card, deck, policy, action, reward, or
enabled-interaction branch was added.

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
  scripts/perf/benchmark_oracle_avoidance_buckets.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates full-scan/bucketed order. Its digest includes
before/after planner state keys, both selected actions, battle RNG before/after
every label, and the complete final planner RNG.

| avoidance candidates | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| full entity scan | 1.088355 | 1.087512 | 0.002313 | 2.756455 |
| exact bucket candidates | 1.064278 | 1.064342 | 0.002407 | 2.818812 |

Bucket pruning improves exact oracle throughput by **2.26%** and reduces
median wall time by 2.21%. All fourteen rows produced digest
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
  --mover-hover-trait cached \
  --avoidance-candidates {full-scan,bucketed}

# Repeat with --workload strategy --strategy balanced.
```

| workload | full-scan seconds / decisions/s | bucketed seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.412893 / 155.003729 | 0.404122 / 158.368213 | **+2.17%** |
| balanced strategy | 0.484626 / 132.060497 | 0.476834 / 134.218617 | **+1.63%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Full scan measured 0.120009 seconds / 533.295 ticks/s;
bucketed measured 0.104735 seconds / 611.067 ticks/s, a **+14.58%**
improvement. Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
4 custom-large-radius/off-shadow-on fixed-seed cases passed
158 targeting/avoidance/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest
  9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349
shadow checks = 1 per trial; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions py_compile clean
git diff --check clean
```

`entities.py` retains 47 pre-existing mypy findings; the explicit
`Iterable[Entity]` candidate type adds no finding at the edited lines.

## Integration

Cherry-pick after `cd1e2de`. The production source change is limited to the
benchmark switch and bounded candidate source in `_update_native_avoidance`.
Existing stationary/crowded drivers only gain `--avoidance-candidates`; the
dedicated oracle driver and test are standalone.
