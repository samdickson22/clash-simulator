# Exact atomic-value card-wrapper deepcopy

## Change

The specialized `CardStatsCompat.__deepcopy__` from `9797076` still routed
every scalar attribute through generic `copy.deepcopy` and assigned it through
`setattr`. The follow-up copies only exact Python atomic built-in types
(`None`, booleans, integers, floats, complex numbers, bytes, and strings) by
identity, exactly as the standard-library deepcopy dispatch does, while every
other value retains recursive memo-aware deepcopy. It publishes copied values
directly into the new wrapper's ordinary instance dictionary, matching generic
reconstruction semantics.

No tuple, frozen dataclass, mapping, sequence, NumPy array, mechanic, or other
potentially nested value is classified atomic. Standalone wrapper deepcopy and
BattleState's existing frozen-definition memo contract are unchanged.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed three-snapshot workload, alternating preceding/all-values and atomic
  order
- clone microbenchmark: 11 matched pairs, 300 clones per row
- production Oracle screen: 11 clean matched pairs, depth 6, 32 simulations,
  64 sampled actions, three labels per row

| workload | all-values deepcopy | atomic-value deepcopy | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Three-snapshot clone loop | 0.183657 s / 1633.48 clones/s | 0.175672 s / 1707.73 clones/s | +4.7540% | 11/11 | +4.1275% to +4.8972% | clone-isolation gate |
| Exact Oracle, 3 labels | 1.590099 s / 1.88667 labels/s | 1.588019 s / 1.88915 labels/s | -0.0041% | 5/11 | -0.6235% to +1.0634% | `15061705f9646af95226addfabaf7a734d21bba3e5e478414bfc027d60d5e514` |

Acceptance is limited to the exact clone primitive. The clean Oracle screen is
unresolved, so no end-to-end planner gain is claimed. A separate 21-pair run
was contaminated by large alternating host swings; although its paired median
was +0.3645% with 16/21 positive pairs, it is not used as evidence.

## Oracle command

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison card-wrapper-atomic-deepcopy --seed 8999 \
  --planner-seed 1999 --states 3 --state-stride 4 --repetitions 11 \
  --decision-interval 8 --planner-depth 6 --planner-simulations 32 \
  --planner-action-samples 64 --engine-fast-path on
```

Raw clean Oracle output:

- `/tmp/card_wrapper_atomic_oracle_clean11.json`

## Exactness and focused gates

- Preceding/atomic Oracle runs in scalar/off, shadow, and optimized/on mode
  all produced
  `15061705f9646af95226addfabaf7a734d21bba3e5e478414bfc027d60d5e514`.
- Seed 8831, 64-decision shadow rollouts in both modes produced
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  one comparison, and zero mismatches.
- Existing wrapper and active-entity tests cover generic-equivalent values,
  mutable nested payload isolation, independent active wrappers, and sharing
  only loader-owned frozen definitions.
- 54 focused wrapper/clone/cache/planner tests passed. New benchmark code is
  Ruff-clean; changed Python files compile and `git diff --check` is clean.
- `card_types.py` retains four inherited mypy findings and has no finding at a
  candidate-changed line.
