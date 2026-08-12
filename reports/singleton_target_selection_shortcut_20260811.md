# Exact singleton target selection shortcut

## Change

`Entity._select_first_nearest_target` now returns the only candidate directly.
A one-element candidate set has no distance comparison or tie to resolve, so
the general minimum and native building-tie machinery cannot alter the result.
Multi-candidate selection remains on the existing path.

The optimization is entity- and card-general. It changes no target eligibility,
candidate order, distance, legal action, observation, reward, battle mutation,
or RNG call.

## Attribution

The optimized-stack oracle profile at `/tmp/clasher_oracle_current.prof`
recorded 74,896 selector calls and 135 ms cumulative selector time in a
10.895-second profiled process. The paired benchmark toggles only the singleton
return while retaining all preceding verified optimizations.

Machine: Apple M4 Pro (12 CPU cores), 24 GiB RAM, macOS 26.5.2 arm64,
Python 3.12.13. Oracle and strategy use 11 alternating matched pairs; random
uses 21 pairs after a clean-window extension. The confidence interval is a
deterministic 95% bootstrap interval for the paired mean. Thread limits were
`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, and
`VECLIB_MAXIMUM_THREADS=1`.

| workload | general | shortcut | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 3.02799 labels/s | 3.10049 labels/s | +2.4051% | 11/11 | +2.0874% to +2.5470% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| Strategy rollout, 256 decisions | 196.02375 decisions/s | 197.33467 decisions/s | +0.6653% | 11/11 | +0.5957% to +1.5756% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| Random rollout, 256 decisions | 189.00971 decisions/s | 191.19648 decisions/s | +0.9993% | 21/21 | +1.0829% to +1.9605% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

The first random series and one replacement overlapped unrelated training or
evaluation work and are excluded. The 21-pair row above ran only after those
processes and all actor children had exited; direct process checks before and
after found only an old idle tmux server at 0% CPU.

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison singleton-target-selection --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --planner-simulations 32 \
  --planner-depth 6 --planner-action-samples 64 --decision-interval 8 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison singleton-target-selection --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

Raw clean oracle output: `/tmp/singleton_target_selection_oracle.json`.
Raw clean strategy output: `/tmp/singleton_target_selection_strategy_final.json`.
Raw clean random output: `/tmp/singleton_target_selection_random_21_final.json`.

## Exactness gates

- The focused test proves a singleton bypasses tie classification and returns
  the same object as the general path.
- A multi-candidate equal-distance test pins native encounter-order behavior.
- Seed 8921, 64 decisions, both switch settings: off/shadow/on digest
  `58a90eaab393a97f5f9370245fa8ea790fa67cef09c7b3653804ff908bf05e67`.
- Seed 8831, 64 decisions, both switch settings: off/shadow/on digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`.
  Shadow performed one comparison in each switch setting with zero mismatches.
- 156 selector, scalar/vector targeting, target-switching, cache, collision,
  action-mask, gather, and determinism tests passed in 10.91 seconds.
- The benchmark drivers and new test are Ruff-clean; all four Python files
  compile; `git diff --check` is clean.
- `entities.py` retains its pre-existing lint/type backlog (including two
  unrelated F-series findings and 47 mypy findings); neither tool reports an
  issue at the changed selector or switch lines.
