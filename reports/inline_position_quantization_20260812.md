# Exact inline position quantization

## Change

Every combat and movement component commits entity coordinates to the native
1/1000-tile grid. The established implementation routed each coordinate
through `tiles_to_logic_units()` and `logic_units_to_tiles()`, adding four
Python calls per commit. `Entity.quantize_logic_position()` now performs the
identical arithmetic directly:

```python
round(float(value) * LOGIC_UNITS_PER_TILE) / LOGIC_UNITS_PER_TILE
```

This is shared fixed-point engine math with no card, deck, or interaction
special case.

## Machine and method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process at `nice -n 15`; BLAS/OpenMP/VecLib limited to one thread
- alternating reference/candidate order after warmup
- fixed seed 9011; Oracle planner seed 2011

| workload | helper conversions | inline conversion | ratio of medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Exact Oracle, depth 6 / 32 sims / 64 samples, 3 labels, 11 pairs | 0.905075 s / 3.31464 labels/s | 0.889760 s / 3.37170 labels/s | +1.7213% | +1.6029% | 11/11 | +1.1799% to +1.7110% | `2b13a1b343d417d962b70b6ef8498973f1fe8e8bef5dbb4797ce2eebfc709a6d` |
| Random stationary, 4 envs x 32 steps, 15 pairs | 0.711256 s / 179.963 d/s | 0.703264 s / 182.009 d/s | +1.1364% | +0.9367% | 14/15 | +0.8100% to +2.5954% | `e5b630d3fd68355cea2e3b455e9f99422805615319aa026ad3600f13cb09ac26` |
| Balanced strategy, 4 envs x 32 steps, 15 pairs | 0.694689 s / 184.255 d/s | 0.691764 s / 185.034 d/s | +0.4229% | +0.6049% | 14/15 | +0.3812% to +0.8984% | `570ae830e303a96f4dfb4bf8c638d3b5bb96e2f1aca55e1a3c8d6376e13d35ef` |

Commands:

```bash
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison inline-position-quantization --states 3 --repetitions 11 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --decision-interval 8 --seed 9011 --planner-seed 2011 \
  --engine-fast-path on

env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n 15 uv run python \
  scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --workload random --seed 9011 --num-envs 4 --rollout-steps 32 \
  --repetitions 15 --warmup-steps 24 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

The strategy command is identical with `--workload strategy --strategy
balanced`.

## Exactness

- Boundary tests cover positive/negative half-unit ties, negative zero,
  fractional values, and wide finite coordinates against the established
  helper composition.
- Reference and candidate Oracle action/state/planner-RNG digests match.
- Seed 9011, 64-decision reference and candidate scalar/off, shadow, and
  optimized/on rollouts all produced
  `658105d5bbf6947ffceef09a43632026c094ec5fa54f7c3d4a57fea49b8c929b`.
  Both shadow runs recorded two comparisons and zero mismatches.

Raw outputs:

- `/tmp/inline_quant_oracle.json`
- `/tmp/inline_quant_random_clean.json`
- `/tmp/inline_quant_strategy_clean.json`
