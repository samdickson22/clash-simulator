# Scalar deferred Crown slots

## Change

The exact deferred native Crown selector previously allocated a Princess list
for every fallback query even though valid native layout metadata permits at
most two Princess objectives. The optimized path stores those objectives in
two scalar references, preserves iteration order, and retains the complete
list implementation behind a reference switch. Duplicate King slots, more
than two Princess slots, and unclassified/custom objectives still return the
same unhandled sentinel and use the complete compatibility path. The change
is driven entirely by semantic slot metadata and has no card-name or deck
special case.

## Profile attribution

The `0b7da75` production-shaped oracle profile
`/tmp/clasher_oracle_0b7da75.prof` recorded 70,194 deferred Crown queries in
the matched reference/candidate driver. The previous path allocated its
Princess list on every query; the scalar path allocates a temporary list only
for the rare symmetric two-Princess distance tie.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots and seeds, alternating list/scalar order
- 11 matched pairs per workload; deterministic 95% bootstrap interval for the
  paired mean

| workload | list slots | scalar slots | ratio-of-medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 3.34332 labels/s | 3.35232 labels/s | +0.2691% | +0.2393% | 6/11 | -0.6646% to +1.0874% | `8170e14a8b70925957f07eb03d20abf6ad11b81a3e0c35234a45c83b55ea2666` |
| Strategy rollout, 256 decisions | 207.77733 decisions/s | 208.31805 decisions/s | +0.2602% | +0.2853% | 9/11 | +0.1260% to +0.7153% | `20c1885ea84a7159989207dcc0ef6c35d6a317b7883be3000701b425a76f7fe2` |
| Random rollout, 256 decisions | 215.07780 decisions/s | 215.60189 decisions/s | +0.2437% | +0.2550% | 10/11 | +0.2220% to +1.7101% | `a70f813f54309aaab49d7adcd5dc7cf037a046a773e30a5dae3edfed54b3f2d1` |

The Oracle sample is positive by both medians but is not statistically
resolved because of first/last host-noise outliers. Acceptance is based on the
two production rollout workloads, where paired medians agree and paired-mean
confidence intervals are positive. No statistically resolved Oracle gain is
claimed.

## Commands

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison scalar-crown-slots --seed 8991 --planner-seed 1991 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison scalar-crown-slots --workload WORKLOAD \
  --strategy balanced --seed 8991 --num-envs 8 --rollout-steps 32 \
  --warmup-steps 8 --repetitions 11 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

Raw outputs:

- `/tmp/scalar_crown_slots_oracle_11.json`
- `/tmp/scalar_crown_slots_strategy_11.json`
- `/tmp/scalar_crown_slots_random_11.json`

## Exactness and focused gates

- Seed 8991, 64 decisions: list/scalar and scalar/off, shadow, and optimized/on
  all produced
  `95373cdf842e88350ea01e07ad3d9c84353ef12d669e5c4200393160c5e854b1`.
- Seed 8831, 64 decisions: every corresponding digest was
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`;
  shadow recorded one check and zero mismatches in both modes.
- Existing native slot, custom fallback, duplicate/multiplicity, dead Crown,
  validation order, and direct/listed selection tests cover the structural
  equivalence of both collectors.
- 207 Crown, targetability, collision, action-mask, clone, and determinism
  tests passed. New tests and drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `entities.py` retains 46 inherited mypy errors and has no finding at a
  candidate-changed line.
