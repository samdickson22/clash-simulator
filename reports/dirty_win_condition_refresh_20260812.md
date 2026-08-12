# Exact dirty win-condition refresh (2026-08-12)

## Result

The ordinary logic-tick path now refreshes public Crown Tower HP and evaluates
win conditions only after a Crown Tower HP mutation or when regulation,
overtime, or tiebreak timing can change match state. Damage, healing, intrinsic
building lifetime decay, and dead-tower cleanup all publish through the shared
Crown Tower slot mechanic; the optimization contains no card names or deck
special cases.

The fixed exact stable-root oracle improves **0.865%** by ratio of medians
(paired median **0.859%**, 10/11 positive pairs, bootstrap mean 95% confidence
interval **+0.341% to +1.077%**). Production-shaped stationary-random rollout
improves **0.491%** by ratio of medians (paired median **0.451%**, 14/15,
bootstrap mean 95% CI **+0.334% to +0.893%**). Balanced-strategy rollout is
directionally positive at **0.614%** by ratio of medians and 12/15 positive
pairs, but its CI crosses zero, so it is not treated as independent proof of a
strategy-workload gain.

## Exactness contract

- `_win_conditions_dirty` starts true and is copied as part of exact battle
  cloning.
- `Entity.take_damage` marks a Crown Tower mutation after actual HP assignment.
- `HealSpell.cast` marks a changed Crown Tower heal.
- `Building._update_intrinsic_lifetime` marks direct lifetime HP decay.
- `_cleanup_dead_entities` marks any Crown Tower removal, including defensive
  handling of externally-killed test/custom entities.
- `_check_win_conditions` remains callable and exact; it publishes all public
  tower HP, evaluates existing match rules, then clears the dirty bit.
- The per-tick reference branch remains available through
  `_USE_DIRTY_WIN_CONDITION_REFRESH` for parity and timing checks.

## Machine and controls

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- one benchmark process, one Torch/BLAS/OpenMP/Accelerate/Numba thread,
  `nice -n 10`; no MPS/GPU use
- fixed seed 9091; oracle planner seed 2091; alternating paired
  reference/candidate order after warmup
- 11 oracle pairs and 15 pairs for each production rollout workload
- another Clasher Python process remained active at low CPU but high resident
  memory during measurement; only within-process paired comparisons are
  attributed

## Commands

Exact stable-root oracle:

```text
env PYTHONPATH=src:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 NUMBA_NUM_THREADS=1 nice -n 10 \
  uv run python scripts/perf/benchmark_dirty_win_condition_oracle.py \
  --seed 9091 --planner-seed 2091 --states 2 --state-stride 4 \
  --repetitions 11 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

Production stationary rollouts (once with `random`, once with
`strategy --strategy balanced`):

```text
env PYTHONPATH=src:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 NUMBA_NUM_THREADS=1 nice -n 10 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison dirty-win-condition-refresh --workload random --seed 9091 \
  --num-envs 4 --rollout-steps 24 --repetitions 15 --warmup-steps 4 \
  --torch-threads 1 --max-ticks 2048 --engine-fast-path on \
  --reward-profile defense-v2
```

## Timing and attribution

| workload | reference seconds | candidate seconds | reference rate | candidate rate | paired median | positive pairs | bootstrap mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| exact oracle | 1.303082 | 1.291904 | 1.5348 labels/s | 1.5481 labels/s | **+0.859%** | 10/11 | +0.341% to +1.077% |
| stationary random | 0.519910 | 0.517368 | 184.647 decisions/s | 185.554 decisions/s | **+0.451%** | 14/15 | +0.334% to +0.893% |
| balanced strategy | 0.509129 | 0.506022 | 188.557 decisions/s | 189.715 decisions/s | +0.593% | 12/15 | -0.101% to +1.065% |

Reference and candidate oracle rows share exact action/state/battle-RNG/planner-
RNG digest
`f259c18c6af8092fbb380edb4a0a8eda84210dba2e414ca746b180a5e8131e05`.
Random rows share rollout digest
`5a7db7049ea8f86e7a91bad47c45f17186b56dfbdb2a4cb44540f15c67c1df1c`;
strategy rows share
`c43a7e82897bb4de8c18d1c161fc0bd668c34b7e5e18f8e418b7b2d0c79c827d`.

## Validation

- Per-tick/dirty variants under scalar/off, shadow, and optimized/on all
  produce fixed-seed digest
  `6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e`.
  Each shadow variant records one legacy action-mask check and zero mismatches.
- Focused tests cover damage publication, heal and cleanup dirty marking,
  regulation-to-overtime transition, and off/shadow/on fixed-seed parity.
- 77 focused win-rule/idle/determinism/reward tests pass.
- 1,025 match-rule/enabled-mechanic/targeting/collision/route/idle/action-mask
  tests pass in 17.29 seconds.
- Owned tests and benchmark drivers pass Ruff; drivers pass `py_compile`; `git
  diff --check` passes. Whole legacy source files retain their pre-existing Ruff
  modernization and mypy findings, with none introduced on an owned line.

## Integration

Cherry-pick the isolated commit. If shared files conflict, port the
`_USE_DIRTY_WIN_CONDITION_REFRESH` switch, `_win_conditions_dirty` field,
logic-tick guard, Crown mutation helper, and dirty reset from `battle.py`; the
damage/lifetime hooks from `entities.py`; and the heal hook from `spells.py`.
The benchmark driver additions and focused test can be ported independently.
