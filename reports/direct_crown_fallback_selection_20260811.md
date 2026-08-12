# Direct exact Crown fallback selection

## Change

The active exact fast path already caches the live Crown objectives and their
data-driven semantic `left`, `right`, and `king` slots. When no ordinary target
is in sight, `Entity.get_nearest_target` now selects directly from those slots
instead of allocating Crown, Princess, King, preferred, adjusted-distance, and
selection lists.

The direct selector is enabled only under the active serialized fallback
globals and exact BattleState cache ownership. It preserves identity,
targetability mechanic, target plane, x-preference, adjusted-distance, and
native symmetric building-tie rules. Unclassified objectives, duplicate King
slots, more than two Princess objectives, alternate globals, non-live caches,
and caller-supplied entity collections use the full compatibility path. The
implementation contains no card-name or deck-specific branch.

## Profile attribution

The optimized `d0b13cf` oracle profile
`/tmp/clasher_oracle_d0b13cf.prof` recorded 73,196 calls and 782 ms cumulative
time in `_single_pass_cached_crown_fallback` during a 10.660-second profiled
process. This candidate removes that helper and its downstream list selection
from native cached layouts.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots, seeds, and alternating reference/candidate order
- 11 matched pairs per workload; deterministic 95% bootstrap interval for the
  paired mean
- direct process and file-timestamp checks excluded overlapping training and
  evaluation attempts; the three result files below completed in clean gaps

| workload | listed reference | direct selection | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 2.94251 labels/s | 3.05045 labels/s | +3.6568% | 11/11 | +3.1895% to +3.9503% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| Strategy rollout, 256 decisions | 190.50732 decisions/s | 192.46250 decisions/s | +1.0225% | 11/11 | +0.8731% to +1.9007% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| Random rollout, 256 decisions | 190.78929 decisions/s | 192.40168 decisions/s | +0.8461% | 11/11 | +0.6918% to +1.8672% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison direct-crown-selection --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison direct-crown-selection --workload WORKLOAD --strategy balanced \
  --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 11 \
  --warmup-steps 8 --torch-threads 1 --engine-fast-path on \
  --reward-profile defense-v2
```

Raw clean outputs:

- `/tmp/direct_crown_selection_oracle_clean.json`
- `/tmp/direct_crown_selection_strategy.json`
- `/tmp/direct_crown_selection_random.json`

## Exactness gates

- Seed 8951, 64 decisions, both switch settings: scalar/off, shadow, and
  optimized/on digest
  `e5637ab38b4d5cd33f6eb7d58c1fa7000150442c994ebfef0469f0e7fde35ba7`.
- Seed 8831, 64 decisions, both switch settings: scalar/off, shadow, and
  optimized/on digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`.
- Each shadow variant performed one action-mask comparison and reported zero
  mismatches.
- 197 Crown fallback, targeting, target-switching, cache, collision,
  action-mask, gather, clone, and determinism tests passed in 12.90 seconds.
- New test and benchmark drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `entities.py` has exactly the same two pre-existing F-series Ruff findings
  before and after the candidate and retains its existing mypy backlog; neither
  tool reports an issue at a changed line.
