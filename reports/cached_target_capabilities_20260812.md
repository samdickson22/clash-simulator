# Cached data-driven target-plane capabilities

## Change

Attacker air/ground capability is immutable normalized card data for an
entity's lifetime. The engine previously decoded `target_type`, `attacks_air`,
and `attacks_ground` through nested `getattr` calls every time targeting,
combat, splash, or fallback selection checked a plane. `Entity.__post_init__`
now classifies the two booleans once with shared data-driven helpers, and the
hot methods return those values directly. There are no card names or
enabled-deck branches.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process at `nice -n 15`; BLAS/OpenMP/VecLib limited to one thread
- fixed seed 9013; planner seed 2013; alternating reference/candidate order

| workload | runtime decode | cached fields | ratio of medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Exact Oracle, depth 6 / 32 sims / 64 samples, 3 labels, 11 pairs | 1.299845 s / 2.30797 labels/s | 1.290789 s / 2.32416 labels/s | +0.7015% | +0.8254% | 11/11 | +0.6240% to +1.7863% | `290392b2b9ca23cb1d3286b5c2702331d7e7bfe6688f65ff854ec555dff806e0` |
| Random stationary, 4 envs x 32 steps, 15 pairs | 0.633938 s / 201.913 d/s | 0.631904 s / 202.562 d/s | +0.3218% | +0.0784% | 11/15 | -0.0592% to +0.5630% | `b19c85bab61931ca81503ee7c0566998003e9869f83d1b65a61cbb071dc7d8b7` |
| Balanced strategy, 4 envs x 32 steps, 15 pairs | 0.611424 s / 209.347 d/s | 0.607811 s / 210.592 d/s | +0.5944% | +0.4426% | 13/15 | +0.1855% to +0.6970% | `41c1e6c776313b39ba823b0a372003d9ba60db140493acfbbcbe9deefacf5a4a` |

The random result is exact and shows no measured regression, but its paired
confidence interval crosses zero; no random-throughput gain is claimed.

Commands:

```bash
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison cached-target-capabilities --states 3 --repetitions 11 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --decision-interval 8 --seed 9013 --planner-seed 2013 \
  --engine-fast-path on

env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison cached-target-capabilities --workload random --seed 9013 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2
```

The strategy command replaces `--workload random` with `--workload strategy
--strategy balanced`.

## Exactness and gates

- Runtime/cached Oracle action, state, battle-RNG, and planner-RNG hashes are
  identical.
- Seed 9013, 64-decision runtime and cached scalar/off, shadow, and optimized/on
  rollouts all produced
  `b66bf4f4e5cb2f1c5c0bad7b1f5037fb1d065fedb39d19cf5b8eb93173ac12dc`.
  Both shadow runs recorded one comparison and zero mismatches.
- Capability helpers and spawned troop/building caches are tested against the
  normalized card data. Enabled troop, spell, projectile, reachable-child,
  targeting, action-mask, and Oracle suites passed: 863 tests.
- New tests and benchmark code are Ruff-clean and `git diff --check` passes.

Raw outputs:

- `/tmp/cached_target_capabilities_oracle.json`
- `/tmp/cached_target_capabilities_random.json`
- `/tmp/cached_target_capabilities_strategy.json`
