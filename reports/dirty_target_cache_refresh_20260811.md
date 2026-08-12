# Dirty exact target-cache refresh

Date: 2026-08-11

## Change

Fast-path movement already publishes every changed entity position, target
plane, stealth timestamp, and dynamic targetability predicate at its exact
component boundary. The shared cache publication nevertheless rescanned every
target at every tick start and at the end of every batched decision window.

The optimized path now records structural target-cache invalidation and uses
it only at trusted internal tick boundaries. A structural change still runs
the complete identity scan/rebuild. A clean cache refreshes only entries whose
data or attached mechanics make targetability or stealth volatile. Direct
callers of the existing refresh helpers retain the defensive full scan, which
also preserves same-size external entity replacement and direct Crown Tower
death behavior.

The volatile subset is selected from shared entity/mechanic capabilities. No
card name, deck list, legal action, observation, reward, or RNG branch was
added.

## Profile attribution

The current exact-oracle cProfile sample recorded:

- 13,897 shared fast-cache publications
- 131,353 full target dynamic refreshes
- 216 ms in `_refresh_target_cache`
- 141 ms in `_refresh_fast_target_dynamic_values`

All 13,897 calls came from the shared tick path: 12,352 tick starts and 1,544
batched-window final publications, plus battle initialization. The candidate
therefore targets production simulation work rather than a standalone helper.

## Machine and protocol

- Mac mini, Apple M4 Pro, 12 cores (8 performance, 4 efficiency), 24 GB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `d6a117f`
- one process, `nice -n 15`, one Torch/BLAS/OpenMP/VecLib thread
- no Clasher training/evaluation/MPS process and no RoadForge process was
  active during the final timing series
- fixed seeds, warmups outside reported rows, alternating paired order
- 11 repetitions per variant and nonparametric bootstrap mean 95% intervals

## Exact oracle screen

Output: `/tmp/dirty_target_cache_oracle_final.json`

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison dirty-target-cache --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 \
  --planner-action-samples 64 --engine-fast-path on
```

| Variant | Median seconds / 3 labels | Median labels/s |
| --- | ---: | ---: |
| defensive full scan | 1.029672 | 2.913550 |
| dirty/volatile refresh | 1.011838 | 2.964901 |

- paired gain: **+1.717% median, +1.682% mean**
- positive pairs: **11/11**
- mean 95% bootstrap CI: **+1.425% to +1.919%**
- every label/state/planner-RNG hash:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Production-shaped stationary rollouts

Outputs: `/tmp/dirty_target_cache_strategy_final.json` and
`/tmp/dirty_target_cache_random_final.json`.

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison dirty-target-cache --workload WORKLOAD --strategy balanced \
  --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 11 \
  --warmup-steps 8 --torch-threads 1 --engine-fast-path on \
  --reward-profile defense-v2
```

| Workload | Full median s | Dirty median s | Full decisions/s | Dirty decisions/s | Paired median gain | Positive | Hash |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 1.327564 | 1.317621 | 192.834 | 194.290 | **+0.633%** | 11/11 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random | 1.368147 | 1.360024 | 187.114 | 188.232 | **+0.939%** | 11/11 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

- strategy paired mean: **+0.916%**, mean 95% bootstrap CI
  **+0.565% to +1.509%**
- random paired mean: **+1.276%**, mean 95% bootstrap CI
  **+0.623% to +2.097%**

## Exactness and gates

- seed 8921, 64 decisions: full/dirty digest in scalar/off, shadow, and
  optimized/on was
  `58a90eaab393a97f5f9370245fa8ea790fa67cef09c7b3653804ff908bf05e67`
- pinned shadow seed 8831 recorded one check per mode, identical digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  and zero mismatches
- **124** dirty/static/stealth/targeting/collision/action-mask tests passed
- **16** focused death-spawn immunity, spirit, Tesla, Archer Queen, and Royal
  Ghost tactical tests passed
- tests cover ordinary scan suppression, capability-selected volatile
  refresh, same-size replacement, direct Crown death, and clone isolation
- changed scripts/tests Ruff clean; source additions have no undefined names;
  `py_compile` and `git diff --check` passed
- focused `battle.py` mypy retains its 21 pre-existing untyped-import,
  dynamic-entity-attribute, and legacy annotation errors; none points to a
  changed line or new cache field
