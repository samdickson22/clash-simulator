# Single-pass exact Crown fallback selection

Date: 2026-08-11

## Change

Live exact-fast-path target selection already obtains the three-or-fewer
opposing Crown objectives from BattleState's identity-checked membership
cache. The old fallback then allocated and scanned additional Crown,
Princess, King, preferred, and distance lists on nearly every no-local-target
selection.

Under the active native globals, the candidate validates each cached member
once and partitions it using the existing semantic `_crown_tower_slot`
metadata. It retains the same native x-preference, King fallback, target-plane,
mechanic, identity, and adjusted-distance rules. Alternate globals,
caller-supplied collections, and any custom Crown objective without semantic
slot metadata fall back to the full compatibility algorithm. No card name or
enabled-deck special case was added.

The oracle profile motivating this change recorded 73,196 Crown fallback
calls with 1.083 seconds cumulative cost.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `36daa3a6b4da04691fea75686686f0345f354acc`
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- RoadForge occupied one CPU core; no exclusive window was requested
- every comparison used fixed snapshots/seeds and alternating paired order

## Exact oracle attribution

Command (output: `/tmp/semantic_crown_oracle.json`):

```sh
nice -n 15 env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison crown-fallback --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

| Variant | Median seconds | Median decisions/s |
| --- | ---: | ---: |
| partitioned reference | 1.161564 | 2.5827 |
| semantic single pass | 1.148292 | 2.6126 |

- paired gain: **+1.217% median, +1.421% mean**
- mean 95% bootstrap CI: **+0.688% to +2.407%**
- positive pairs: 10/11
- every action/state hash:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Production-shaped stationary rollouts

Command shape:

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison crown-fallback --workload WORKLOAD --strategy balanced \
  --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions REPETITIONS \
  --warmup-steps 8 --torch-threads 1 --engine-fast-path on \
  --reward-profile defense-v2
```

| Workload | Pairs | Reference median | Candidate median | Paired median | Positive | Hash |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 11 | 163.976 decisions/s | 166.246 decisions/s | **+0.640%** | 7/11 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random | 7 | 161.302 decisions/s | 162.775 decisions/s | **+1.029%** | 6/7 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

Shared-host outliers made the rollout mean confidence intervals cross zero;
the conservative claim is therefore the paired median, supported by the
positive, tight oracle attribution and identical hashes.

## Exactness and gates

- seed 8849, 64 decisions: reference/candidate digest in scalar/off,
  shadow, and optimized/on was
  `f631acf2794644b259e9105ec3db82ea30d3d8f6e2d3c6e40d5b1d7d0d3d6deb`
- shadow seed 8831 recorded one reference and one candidate action-mask check,
  identical digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  and zero mismatches
- exhaustive focused tests cover left/center/right attackers, every single
  dead Crown slot, custom unclassified Crown fallback, fixed rollout modes,
  targeting, collision, action-mask, and clone behavior
- **135 focused tests passed**
- Ruff passed for the changed benchmark/test files with only their inherited
  non-executable-shebang finding excluded; whole-file `entities.py` mypy
  retains its 47 pre-existing errors after the candidate-specific iterable
  type was corrected; `py_compile` and `git diff --check` passed
