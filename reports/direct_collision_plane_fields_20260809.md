# Direct exact Entity collision-plane fields

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `e18434e`

## Change

Every production call to `uses_air_collision_plane` receives an `Entity`,
which owns required `is_air_unit` and immutable data-driven `_is_hover_unit`
fields. The hot helper now reads those fields directly while retaining the
same dynamic river-jump and airborne-leap predicates. Its defensive path
remains available for A/B parity and non-production compatibility.

There are no card, deck, policy, action, reward, or enabled-interaction
branches. Hover classification remains centralized in `unit_traits.py` and is
still derived from exported data plus the existing general fallback table.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no checkpoint or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guards before accepted timing commands
- seven alternating oracle repetitions; candidate-first production confirmation

A first timing attempt overlapped a main-thread MPS repair fit and was
discarded in full. The values below were collected only after that fit and its
following CPU eval shards exited, with consecutive clean cooldown polls.

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_direct_collision_plane.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 7 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates defensive/direct order. Its digest includes before/after
planner state keys, both selected actions, battle RNG before/after every label,
and the complete final planner RNG.

| collision-plane fields | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| defensive reflection | 1.080319 | 1.080578 | 0.003782 | 2.776957 |
| direct Entity fields | 1.077352 | 1.077965 | 0.002621 | 2.784607 |

Direct fields improve exact oracle throughput by **0.28%** and reduce median
wall time by 0.27%. All fourteen rows produced digest
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
  --mover-hover-trait cached --avoidance-candidates bucketed \
  --collision-plane-fields {defensive,direct}

# Repeat with --workload strategy --strategy balanced.
```

| workload | defensive seconds / decisions/s | direct seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.417570 / 153.267563 | 0.411488 / 155.532980 | **+1.48%** |
| balanced strategy | 0.485249 / 131.891004 | 0.483794 / 132.287595 | **+0.30%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Defensive measured 0.106763 seconds / 599.461 ticks/s;
direct measured 0.106521 seconds / 600.822 ticks/s, a **+0.23%** improvement.
Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
12 ground/hover/air/river/leap/off-shadow-on fixed-seed cases passed
170 targeting/avoidance/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest
  9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349
shadow checks = 1 per trial; shadow mismatches = 0
unit_traits.py mypy clean
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions py_compile clean
git diff --check clean
```

`unit_traits.py` retains only its three pre-existing PLC0208 set-iteration
findings; the edited import block is Ruff-isort clean and no new finding was
introduced.

## Integration

Cherry-pick after `e18434e`. The production source change is limited to the
benchmark switch and direct required Entity fields in
`uses_air_collision_plane`. Existing stationary/crowded drivers only gain
`--collision-plane-fields`; the dedicated oracle driver and test are
standalone.
