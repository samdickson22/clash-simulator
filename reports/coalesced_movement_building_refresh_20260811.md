# Coalesced exact movement-phase building refresh

Date: 2026-08-11

## Change

Ground movement occupancy asks for live-building membership many times within
one controlled movement component phase. The accepted identity/order cache
still rescanned the entity dictionary on every request; the current oracle
profile recorded 49,450 refresh calls and 0.172 seconds cumulative cost.

The candidate performs one exact identity/order publication on the first
movement-phase occupancy request and reuses it only inside that phase. Combat
may have killed a building
after the start-of-frame refresh, so phase entry is always dirty. Building
spawn and both ordinary-damage and intrinsic-lifetime death paths explicitly
invalidate the phase-local publication. A `finally` block disables reuse at
phase exit. Action validation, external queries, clone boundaries, alternate
engine modes, and every query outside controlled movement retain the existing
exact scan.

This is shared engine state with no card names, deck conditions, or policy
branches.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `25faae82feb3808d25603bde2717ebd7c101704a`
- one process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- RoadForge occupied one CPU core; no exclusive window was requested
- fixed seeds/snapshots and alternating paired order

## Exact oracle attribution

Command (output: `/tmp/coalesced_building_oracle.json`):

```sh
nice -n 15 env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison movement-building-refresh --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

| Variant | Median seconds | Median decisions/s |
| --- | ---: | ---: |
| repeated identity scan | 1.102035 | 2.7222 |
| phase-coalesced | 1.088468 | 2.7562 |

- paired gain: **+0.524% median, +0.572% mean**
- mean 95% bootstrap CI: **+0.102% to +1.023%**
- positive pairs: 8/11
- every action/state hash:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Production-shaped stationary rollouts

Command shape:

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison movement-building-refresh --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions REPETITIONS --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

| Workload | Pairs | Reference median | Candidate median | Paired median | Positive | Hash |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 11 | 169.858 decisions/s | 171.451 decisions/s | **+0.668%** | 9/11 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random | 7 | 155.445 decisions/s | 156.156 decisions/s | **+1.215%** | 5/7 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

Strategy's mean bootstrap CI was +0.264% to +2.298%; random's was
+0.242% to +3.502%. The conservative claims above are paired medians.

## Exactness and gates

- seed 8857, 64 decisions: repeated/coalesced digest in scalar/off, shadow,
  and optimized/on was
  `aaedb7c72858f5e49cb2eb2a9254d5e7684450bbf410e1d5c7cebd2daca7ae8e`
- shadow seed 8831 recorded one check per variant, identical digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  and zero mismatches
- focused tests prove one entity scan across repeated phase-local queries,
  immediate invalidation on building spawn/death, exact scalar/shadow/on
  traces, intrinsic building lifetime, placement/action masks, targeting,
  collision, clone, and existing cache edge cases
- **156 focused tests passed**
- changed benchmark/tests Ruff clean with inherited non-executable shebang
  excluded; `py_compile` and `git diff --check` passed
