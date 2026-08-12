# Exact inline building-overlap geometry

## Change

Movement and legal-placement building overlap checks converted the combined
radius and both coordinate deltas through three tiny Python fixed-point helper
calls for every candidate building. The hot loop now performs the identical
`round(float(value) * LOGIC_UNITS_PER_TILE)` arithmetic inline. Membership,
collision-radius fallback, movement-radius cap, ignored building ID, and the
strict squared-distance overlap comparison are unchanged. The shared geometry
contains no card/deck special case.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process at `nice -n 15`; BLAS/OpenMP/VecLib limited to one thread
- fixed seed 9017; planner seed 2017; alternating reference/candidate order

| workload | helper conversions | inline conversions | ratio of medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Exact Oracle, depth 6 / 32 sims / 64 samples, 3 labels, 11 pairs | 1.372351 s / 2.18603 labels/s | 1.359561 s / 2.20659 labels/s | +0.9407% | +0.9923% | 11/11 | +0.6073% to +1.0807% | `a038ed6019b5f58e14d1a24062f873e8384f4570a0c1e9b8971fa200715c10fd` |
| Random stationary, 4 envs x 32 steps, 15 pairs | 0.687298 s / 186.237 d/s | 0.686424 s / 186.474 d/s | +0.1273% | +0.1428% | 12/15 | +0.0388% to +0.5636% | `a393baad40ff6b6e394affecd54d0f5f31e6c735da16691210d21f9e0a9026d7` |
| Balanced strategy, 4 envs x 32 steps, 15 pairs | 0.669825 s / 191.095 d/s | 0.667207 s / 191.844 d/s | +0.3923% | +0.2837% | 13/15 | -0.7296% to +0.4794% | `b104b06490f96793acaeda30b1bfee9a9ba1005b6b17e14bdc0bd55b520dbf1b` |

The strategy rows contain one -4.89% host outlier. The paired median and 13/15
pairs are positive, but the confidence interval crosses zero; no strategy gain
is claimed.

Commands:

```bash
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison inline-building-overlap --states 3 --repetitions 11 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --decision-interval 8 --seed 9017 --planner-seed 2017 \
  --engine-fast-path on

env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison inline-building-overlap --workload random --seed 9017 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2
```

The strategy command replaces `--workload random` with `--workload strategy
--strategy balanced`.

## Exactness

- Unit tests compare helper/inline results at positive and negative half-unit
  boundaries, multiple mover radii, the movement-radius cap, distant points,
  and ignored IDs.
- Helper/inline Oracle action/state/planner-RNG digests match exactly.
- Seed 9017, 64-decision helper/inline scalar/off, shadow, and optimized/on
  rollouts all produced
  `427072bfd7b4db64744aca4d1041ef7e30cef50191cd10532d1e14d156f47d44`.
- Pinned seed 8831 shadow remains
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`
  in both modes, with one check and zero mismatches.

Raw outputs:

- `/tmp/inline_building_overlap_oracle.json`
- `/tmp/inline_building_overlap_random.json`
- `/tmp/inline_building_overlap_strategy.json`
