# Lazy per-battle card-wrapper materialization

Date: 2026-08-11

## Change

`BattleState.__post_init__` eagerly created all 171 mutable
`CardStatsCompat` wrappers even though RL environments initially need only the
cards in two sampled hands. `CardDataLoader.get_card` already provides exact
per-loader lazy materialization and stable wrapper identity. Battle creation
now relies on that existing path; the eager behavior remains behind a private
benchmark switch.

Card definitions remain process-global and frozen, while each battle still
gets independent mutable wrappers on first lookup. No definition, stat,
mechanic, action, observation, reward, or deck behavior changed.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `29320255a469d13fead883444e51a605ea16088f`
- one process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- RoadForge occupied one CPU core; no exclusive window was requested
- fixed seeds and alternating paired order

## Ready-battle initialization

Command (output: `/tmp/lazy_battle_initialization.json`):

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_battle_initialization.py \
  --battles 8 --repetitions 21 --seed 2301
```

The immutable definition snapshot was warmed once in both variants. Each
timed row constructs eight exact fast-path battles; card wrappers remain
battle-local.

| Variant | Median seconds / 8 battles | Median ready battles/s |
| --- | ---: | ---: |
| eager 171 wrappers/battle | 0.099831 | 80.135 |
| lazy wrappers on lookup | 0.094200 | 84.926 |

- paired gain: **+5.505% median, +8.064% mean**
- mean 95% bootstrap CI: **+5.472% to +11.494%**
- positive pairs: 21/21
- every initial battle-state hash:
  `817a977c13b607f11b3a323aa6381633888227c6405cd1e377a6898396f80698`

## Initialization plus fixed decisions

Both production-shaped screens timed construction/reset and the complete
8-environment x 16-decision stationary rollout. This intentionally keeps the
reset work inside the wall-clock interval.

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison lazy-card-materialization --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 16 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

| Workload | Eager median | Lazy median | Paired median | Positive | Hash |
| --- | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 138.494 decisions/s | 139.156 decisions/s | **+0.443%** | 7/11 | `688a582b099968f7bb783780f05055e6d3d5f8d3fb6a87b3df3bedc53c498f17` |
| random | 149.354 decisions/s | 149.578 decisions/s | **+0.151%** | 8/11 | `7b30368c51234d9d77efc7ec49d4469a0216c2dc97b72544326d4f64b64829d4` |

Shared-host variance made the short rollout mean confidence intervals cross
zero. The robust claim is the 21/21 initialization/reset improvement; the
fixed-decision screens establish no regression and show its expected
amortization over longer episodes. This change does not claim an oracle
per-label speedup; it reduces oracle/corpus process and environment startup.

## Exactness and gates

- seed 8861, 64 decisions: eager/lazy digest in scalar/off, shadow, and
  optimized/on was
  `f59d8dbcf2658921adb8dba1e714f753306458dd8a95d5adb2491c9a94521144`
- shadow seed 8831 recorded one check per variant, identical digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  and zero mismatches
- tests prove lazy lookup identity, eager/lazy stat equality, cross-battle
  wrapper isolation, clone isolation, gamedata normalization, card mechanics,
  deck sampling, action masks, oracle exactness, and determinism
- **87 focused tests passed**
- changed scripts/tests Ruff clean; `py_compile` and `git diff --check` passed
