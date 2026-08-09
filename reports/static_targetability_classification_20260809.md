# Exact static targetability classification

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

The accelerated target cache republished `Entity.is_targetable_by(...)` for
every live character at each cache refresh and per-character synchronization.
For ordinary alive troops and buildings, every non-stealth gate in that method
is invariant after manager insertion. Calling the complete predicate repeatedly
therefore paid for battle-time conversion, mechanic iteration, and attribute
checks without changing the cached result.

The cache now classifies targets once at structural rebuild time. It retains the
complete dynamic predicate for entities with a hidden-building state, active
death-spawn target immunity, or any mechanic that owns `blocks_targeting`.
Stealth remains exact and independent: its timestamp continues to be republished
and applied by the vectorized selector on every query. Mechanics are attached
before manager insertion, and the classification array is cloned as mutable
battle state. No card name, deck, action, reward, or RNG branch was added.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no optimizer-owned MPS/GPU, checkpoint, training, or corpus write
- full executable-prefix process guard for `run_clasher.py train|eval`, module eval,
  `train_recurrent.py`, and multiprocessing actors
- continuous 30-second quiescence window before accepted timing groups and a
  second process guard after each command

The main training pipeline launched a 64-environment/12-worker MPS population
phase and several later CPU evaluation waves during this work. Every source/test
action respected those workers. One oracle timing and one stationary-strategy
timing overlapped newly launched eval workers; their post-guards rejected them,
and neither result appears below.

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_targetability_refresh.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates full/classified order across five matched repetitions.
Its digest includes before/after planner state keys, both selected actions,
battle RNG before/after every label, and complete final planner RNG.

| targetability refresh | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| full predicate | 1.254620 | 1.254143 | 0.002071 | 2.391163 |
| static classification | 1.213604 | 1.214251 | 0.003056 | 2.471976 |

Classification improves exact oracle label throughput by **3.38%** and reduces
wall time by 3.27%. All ten accepted rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Crowded exact engine

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_crowded_engine.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 11 \
  --mode on --clear-route-cache-per-mode --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh {full,classified}
```

| targetability refresh | median seconds / 64 ticks | ticks/s |
| --- | ---: | ---: |
| full predicate | 0.128729 | 497.166701 |
| static classification | 0.124056 | 515.895178 |

The crowded engine improves by **3.77%** in ticks/s and 3.63% in wall time.
Both variants produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Production-shaped stationary rollouts

Each command used one environment, 64 decisions, seven repetitions after two
untimed warmup decisions, two Torch threads, and the exact fast engine.

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 7 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh {full,classified}

# Repeat with --workload strategy --strategy balanced.
```

| workload | full seconds / decisions/s | classified seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.438049 / 146.102418 | 0.431594 / 148.287468 | **+1.50%** |
| balanced strategy | 0.507344 / 126.147151 | 0.501746 / 127.554463 | **+1.12%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

```text
7 direct static/dynamic/stealth/clone/off-shadow-on cases passed
88 target/collision/action-mask/clone/batched-cache focused tests passed
622 enabled troop-interaction tests passed
3 determinism tests passed
scalar/off = shadow = optimized/on digest
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks = 1; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions checked with inherited EXE001/UP012 excluded
git diff --check clean
```

## Integration

Cherry-pick the isolated commit. If `battle.py` conflicts with the training
branch's dirty cache work, port only the `_USE_STATIC_TARGETABILITY_CLASSIFICATION`
switch, `_target_requires_targetability_check` array, classification helper,
and the guarded predicate assignments in rebuild/refresh/sync. Include the new
array in any explicit clone/cache parity list. The two existing benchmark drivers
only gain a `--targetability-refresh` selector; the dedicated oracle driver and
test are otherwise standalone.
