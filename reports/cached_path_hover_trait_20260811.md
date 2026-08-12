# Cached path hover trait

Date: 2026-08-11

## Change

Every `Entity` already classifies the immutable data-driven hover movement
trait into `_is_hover_unit` during initialization. Native path selection still
called `is_hover_unit_card` on the same card data at every waypoint request in
both `ground_path_waypoint` and `Troop._get_pathfind_target`. Those two hot
paths now read the exact entity-owned trait.

The runtime classification remains behind private benchmark switches. No
card name, card list, route, legal action, observation, reward, battle state,
or RNG behavior changed.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `8c9566eab14f1a725c98566d9da68472f9005649`
- one process, `nice -n 15`, one Torch/BLAS/OpenMP/VecLib thread
- RoadForge occupied one CPU core; no exclusive window was requested
- no Clasher training or MPS process was active during timing
- fixed seeds and alternating paired order

The preceding production profiles attributed 20,311 runtime hover
classifications (55.25 ms cumulative) to the oracle screen and 4,804
(14.01 ms) to the stationary strategy screen.

## Exact oracle screen

Command (output: `/tmp/cached_path_hover_oracle.json`):

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison path-hover-trait --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 \
  --planner-action-samples 64 --engine-fast-path on
```

| Variant | Median seconds / 3 labels | Median labels/s |
| --- | ---: | ---: |
| runtime classification | 1.181368 | 2.539 |
| cached entity trait | 1.166186 | 2.572 |

- paired gain: **+1.017% median, +0.625% mean**
- positive pairs: 8/11
- mean 95% bootstrap CI: **-0.107% to +1.235%**
- every label/state/planner-RNG hash:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

The oracle point estimate agrees with the profiler attribution, but the mean
confidence interval crosses zero under shared-host variance. The accepted
throughput claim therefore rests on the two end-to-end rollout screens below,
not on oracle timing alone.

## Production-shaped stationary rollouts

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison path-hover-trait --workload WORKLOAD --strategy balanced \
  --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 11 \
  --warmup-steps 8 --torch-threads 1 --engine-fast-path on \
  --reward-profile defense-v2
```

| Workload | Runtime median seconds | Cached median seconds | Runtime median decisions/s | Cached median decisions/s | Paired median gain | Positive | Hash |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 1.518535 | 1.512812 | 168.583 | 169.221 | **+1.099%** | 10/11 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random | 1.464732 | 1.458680 | 174.776 | 175.501 | **+0.439%** | 9/11 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

- strategy mean gain: **+1.280%**, mean 95% bootstrap CI
  **+0.591% to +2.037%**
- random mean gain: **+0.667%**, mean 95% bootstrap CI
  **+0.289% to +1.181%**

## Exactness and gates

- seed 8873, 64 decisions: runtime/cached digest in scalar/off, shadow, and
  optimized/on was
  `2f1d5f6aba6193e33eeae6ba78063f4fb2973ffb38afb28dfc6f960ed9cd9245`
- shadow seed 8831 recorded one check per variant, identical digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  and zero mismatches
- tactical tests compare cached/runtime path results for ordinary and hovering
  entities and prove the cached hot path performs no card-data lookup
- **186 path, route, scalar/fast, targeting, collision, action-mask, idle, and
  oracle tests passed**
- changed scripts/tests Ruff clean; source additions have no undefined names;
  `py_compile` and `git diff --check` passed
- focused mypy adds no hover-field error; it retains pre-existing dynamic
  entity/path attributes and unrelated legacy typing errors
