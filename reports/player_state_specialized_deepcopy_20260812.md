# Specialized exact `PlayerState` deepcopy

## Change

`BattleState.clone()` copied both player records through Python's generic
reconstruction protocol. `PlayerState.__deepcopy__` now directly copies the
canonical ten-field dataclass layout, including memo-aware exact copies of the
hand, deck, and cycle deque. Built-in lists/deques containing only the declared
atomic card references use their native copy constructors. Subclasses,
extension attributes, container subclasses, and non-atomic payloads retain a
fully recursive generic fallback. No card name, deck, or enabled-interaction
branch is present.

## Machine and method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- one process at `nice -n 15`; BLAS/OpenMP/VecLib fixed to one thread
- fixed seed 2301, three snapshots, alternating generic/specialized order
- clone loop: 15 matched pairs, 500 clones per row
- production Oracle: 21 matched pairs, depth 6, 32 simulations, 64 sampled
  actions, three labels per row

| workload | generic | specialized | ratio of medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Three-snapshot clone loop | 0.175354 s / 2851.38 clones/s | 0.171176 s / 2920.97 clones/s | +2.4403% | +2.4971% | 15/15 | +2.3462% to +5.1775% | clone-isolation gate |
| Exact Oracle, 3 labels | 0.857639 s / 3.49797 labels/s | 0.855169 s / 3.50808 labels/s | +0.2888% | +0.2568% | 14/21 | +0.1110% to +0.5817% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |

Oracle command:

```bash
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison player-deepcopy --states 3 --repetitions 21 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --decision-interval 8 --seed 2301 --planner-seed 901 \
  --engine-fast-path on
```

## Exactness

- Generic and specialized Oracle rows have one exact action/state/planner-RNG
  digest: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`.
- Seed 9009, 64-decision generic and specialized scalar/off, shadow, and
  optimized/on rollouts all produced
  `3e74f97a901143ce967452559bd1fabc3f0b1811c28437387879ab7b26ad80ba`.
  Each shadow rollout recorded one comparison and zero mismatches.
- Direct tests cover canonical and subclass records, arbitrary mutable
  extension data, shared-container memo aliases, exact whole-battle player and
  RNG state, and source/clone isolation.

Raw Oracle output: `/tmp/player_deepcopy_oracle.json`.
