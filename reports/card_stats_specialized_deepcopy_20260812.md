# Specialized exact card-wrapper deepcopy

## Change

`BattleState.clone()` must isolate every mutable `CardStatsCompat` wrapper
while sharing only loader-owned frozen `CardDefinition` objects through its
existing deepcopy memo. Generic `copy.deepcopy` reconstructs each wrapper via
Python's general reduce protocol. The candidate implements the same memo-aware
attribute-by-attribute deep copy directly on the compatibility wrapper,
removing generic reconstruction setup without changing which nested values are
copied or shared.

The method is card- and deck-agnostic. Standalone `copy.deepcopy(wrapper)`
still deep-copies its definition and nested raw payload; `BattleState.clone()`
shares a definition only when the battle clone's existing memo has already
classified that loader definition as frozen.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed three-snapshot workload, alternating generic/specialized order
- clone microbenchmark: 15 matched pairs, 300 clones per row
- production oracle: 21 matched pairs, depth 6, 32 simulations, 64 sampled
  actions, three labels per row

| workload | generic deepcopy | specialized deepcopy | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Three-snapshot clone loop | 0.176269 s / 1701.95 clones/s | 0.164535 s / 1823.32 clones/s | +7.1311% | 15/15 | +6.7973% to +7.2612% | clone-isolation gate |
| Exact Oracle, 3 labels | 1.226369 s / 2.44624 labels/s | 1.225849 s / 2.44728 labels/s | +0.4999% | 17/21 | +0.0717% to +0.6251% | `0f3fe3bed2169ba2cf0a08cb517844e0619adf3296053047ed6cf37add0c77fa` |

The Oracle ratio of independently selected medians is only +0.0425%; the
claim uses the matched-pair median and reports the paired-mean confidence
interval. No stationary-rollout gain is claimed because PPO rollout does not
clone battle states.

## Production Oracle command

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison card-wrapper-deepcopy --seed 8997 --planner-seed 1997 \
  --states 3 --state-stride 4 --repetitions 21 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The clone microbenchmark uses the same `_snapshots` helper and temporarily
deletes/restores `CardStatsCompat.__deepcopy__` for the generic reference. Each
timed row performs 100 clones of each of the three fixed snapshots; the full
command and all row values are recorded in the optimizer-thread transcript.

Raw Oracle output:

- `/tmp/card_wrapper_deepcopy_oracle_21.json`

## Exactness and focused gates

- Generic/specialized Oracle runs in scalar/off, shadow, and optimized/on mode
  all produced
  `0f3fe3bed2169ba2cf0a08cb517844e0619adf3296053047ed6cf37add0c77fa`.
- Seed 8997, 64-decision generic/specialized scalar/off, shadow, and
  optimized/on rollout hashes were all
  `3fc9a28231c3795990de6ddc202957cb4e0a1af951ee705d8d6f16d7ed0c4f8b`.
  Seed 8831 shadow produced `747f97fc...efe8e`, one comparison, and zero
  mismatches in both modes.
- Wrapper tests compare generic/specialized public values, prove nested raw
  payload isolation, and prove an active cloned entity owns its wrapper while
  sharing only the loader's frozen definition.
- Existing battle-clone, lazy-loader, RNG, entity/player, target cache, Crown
  cache, NumPy cache, and fast-bucket isolation gates remain in scope.
- 64 focused clone/cache/planner/collision tests passed. New tests and the
  benchmark driver are Ruff-clean; changed Python files compile and
  `git diff --check` is clean.
- `card_types.py` retains four inherited mypy findings and has no finding at a
  candidate-changed line.
