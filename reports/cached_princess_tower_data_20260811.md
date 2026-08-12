# Cached Princess Tower support data

Date: 2026-08-11

## Change

Every `BattleState` parsed the complete game-data JSON to extract the same
`King_PrincessTowers.statCharacterData` payload. The game-data file is already
treated as a process-local immutable revision for card definitions. The
support-tower payload now uses the same file-revision key (`path`, `mtime_ns`,
and byte size), parses once, and returns a deep copy for every battle.

The copy retains exact battle-local mutation isolation. A rewritten game-data
file receives a different cache key. The uncached behavior remains behind a
private benchmark switch. No stat, mechanic, action, observation, reward,
seed trace, card identity, or enabled-deck behavior changed.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `ec77ec9426120d9ac656377e8c4a257ac377c95f`
- one process, `nice -n 15`, one Torch/BLAS/OpenMP/VecLib thread
- RoadForge occupied one CPU core; no exclusive window was requested
- no Clasher training or MPS process was active during timing
- fixed seeds and alternating paired order

## Ready-battle initialization

Command (output: `/tmp/cached_princess_initialization_final.json`):

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_battle_initialization.py \
  --comparison princess-data --battles 8 --repetitions 21 --seed 2301
```

Each timed row constructs eight exact fast-path battles. The first cached row
includes the process's cold cache miss; later cached rows represent the normal
warm process after its first battle.

| Variant | Median seconds / 8 battles | Median ready battles/s |
| --- | ---: | ---: |
| parse JSON per battle | 0.099790 | 80.169 |
| revision cache + isolated copy | 0.001764 | 4,536.325 |

- paired gain: **+5,566.187% median, +5,301.720% mean**
- mean 95% bootstrap CI: **+4,760.958% to +5,648.337%**
- positive pairs: 21/21
- cold-cache first pair: **+594.535%**
- every initial battle-state hash:
  `817a977c13b607f11b3a323aa6381633888227c6405cd1e377a6898396f80698`

## Initialization plus fixed decisions

Both screens timed construction/reset and the complete 8-environment x
16-decision stationary rollout. This deliberately keeps the reset work inside
the measured wall clock.

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison cached-princess-data --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 16 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

| Workload | Parsed median seconds | Cached median seconds | Parsed median decisions/s | Cached median decisions/s | Paired median gain | Positive | Hash |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 0.895048 | 0.808529 | 143.009 | 158.312 | **+11.630%** | 11/11 | `688a582b099968f7bb783780f05055e6d3d5f8d3fb6a87b3df3bedc53c498f17` |
| random | 0.905242 | 0.814221 | 141.399 | 157.206 | **+11.572%** | 11/11 | `7b30368c51234d9d77efc7ec49d4469a0216c2dc97b72544326d4f64b64829d4` |

- strategy mean gain: **+10.940%**, mean 95% bootstrap CI
  **+9.660% to +12.117%**
- random mean gain: **+11.386%**, mean 95% bootstrap CI
  **+10.033% to +12.708%**

This is a reset/corpus-startup optimization. It does not claim a per-label
oracle-search gain once a battle is already running.

## Exactness and gates

- seed 8867, 64 decisions: parsed/cached digest in scalar/off, shadow, and
  optimized/on was
  `ccab7a0e04d4cf82e14fca67932753e60755999421d7373d843a7722136b8e64`
- shadow seed 8831 recorded one check per variant, identical digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  and zero mismatches
- tests prove file-revision invalidation, nested-copy isolation, one parse for
  two battles, scalar/shadow/on fixed-seed parity, battle clone isolation,
  game-data normalization, card mechanics, deck sampling, action masks,
  oracle exactness, and determinism
- **99 focused tests passed**
- changed scripts/tests Ruff clean; source additions have no undefined names;
  `py_compile` and `git diff --check` passed
