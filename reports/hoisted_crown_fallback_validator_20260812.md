# Hoisted exact Crown fallback validator

## Change

The deferred native Crown selector called the same dynamic target predicate
through a newly allocated nested closure for every fallback query. The
candidate moves that predicate to one module-level helper and passes the
attacker and cached attack-plane booleans explicitly. The selection order,
targetability predicate, pending-projectile handling, mechanic filters, and
air/ground checks are unchanged. The reference switch retains the nested
closure for matched timing and digest comparisons.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots and seeds, alternating closure/hoisted order
- 11 matched pairs per workload; deterministic 95% bootstrap interval for the
  paired mean

| workload | nested closure | hoisted helper | ratio-of-medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 2.45722 labels/s | 2.47557 labels/s | +0.7465% | +0.6145% | 9/11 | +0.0167% to +0.7674% | `9332801ccd356b1af77b24426b796f6078394daab58f95c0da61b385bb9359e3` |
| Strategy rollout, 256 decisions | 211.25891 decisions/s | 211.94985 decisions/s | +0.3271% | +0.2550% | 10/11 | +0.1340% to +1.3046% | `68f8de364fd6b82227dca90adb3a36bdd3d16c574abd4ea5f144aa21538ccd35` |
| Random rollout, 256 decisions | 208.82008 decisions/s | 209.11561 decisions/s | +0.1415% | +0.1493% | 8/11 | +0.0017% to +1.2705% | `ed2ac661326a0f7348c123114cab931b1529983b8bc9d9d88050651fe509c9a2` |

The first rollout pair was a wider roughly 4% host/cold outlier. Attribution
uses the paired medians and reports the complete confidence intervals rather
than treating that first pair as representative.

## Commands

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison hoisted-crown-validator --seed 8983 --planner-seed 1983 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison hoisted-crown-validator --workload WORKLOAD \
  --strategy balanced --seed 8983 --num-envs 8 --rollout-steps 32 \
  --warmup-steps 8 --repetitions 11 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

Raw outputs:

- `/tmp/hoisted_crown_oracle_accurate_11.json`
- `/tmp/hoisted_crown_strategy_accurate_11.json`
- `/tmp/hoisted_crown_random_accurate_11.json`

## Exactness and focused gates

- Seed 8983, 64 decisions: nested/hoisted and scalar/off, shadow, and
  optimized/on all produced
  `85f05b1721f3c5d1af2c2e6f399165c6c21e394e5b3d905849faec68acd9aaea`.
- Seed 8831, 64 decisions: every corresponding digest was
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`;
  shadow recorded one check and zero mismatches in both modes.
- 52 candidate and Crown-selection tests passed. The wider target/collision/
  action-mask/clone run passed 210 tests; its sole failure is an inherited
  `test_preferred_crown_filter_avoids_discarded_distance_work` expectation
  from the preceding deferred-validation commit (it expects one distance call,
  while that existing path now performs zero). The hoisted/reference modes
  behave identically.
- New tests and benchmark drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `entities.py` retains 46 inherited mypy errors and has no finding at a
  candidate-changed line.
