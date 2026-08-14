# Resident Rust action-plus-interval ceiling

## Scope

This benchmark measures the resident ceiling after commits `7c62ecb5` (shared
card catalog and exact joint single-troop actions) and `7a9e98bb` (clone-once
complete-tick batching). It includes joint-action shuffle, validation, hand and
elixir mutation, two troop deployments, and a closed 32-tick simulation window.
It intentionally excludes Python observation, legal-mask, reward, and state
publication costs, so it is attribution evidence rather than an end-to-end RL
rollout claim.

## Machine and toolchain

- Mac mini, Apple M4 Pro, 12 CPU cores, 24 GB RAM
- macOS 26.5.2 (25F84)
- Python 3.12.13
- rustc 1.97.1
- single process, CPU only; Rust extension built with `maturin develop --release`

## Fixed workload and method

The fixture uses `BattleState(rng=random.Random(9423))`, standard Crown Towers,
four Knights in each hand, ten elixir, and deterministic Knight placements for
both players. Every timed decision performs the exact CPython two-player shuffle,
applies both actions, then advances 32 native 50-ms ticks. Root cloning is outside
the timed region for both arms.

Five alternating warmups preceded 30 alternating repetitions. Timing used
`time.perf_counter_ns()`. Confidence intervals are two-sided 95% Student-t
intervals for the repetition mean (29 degrees of freedom).

```text
PYTHONPATH=src:. .venv/bin/python <inline fixed-seed action-plus-32-tick driver>
```

| Arm | Median wall / decision | Mean wall (95% CI) | Decisions/s | Ticks/s |
|---|---:|---:|---:|---:|
| optimized Python scalar | 0.003546625 s | 0.003593282 s [0.003498227, 0.003688337] | 278.30 | 8,905.51 |
| resident Rust action + batch | 0.000129667 s | 0.000136407 s [0.000126913, 0.000145901] | 7,331.00 | 234,592.01 |

The resident boundary is **26.3424x faster** and reduces mean simulator/action
wall time by **96.20%** for this declared-capability decision workload. The final
Python and Rust states matched exactly across player state, entity order/IDs,
combat, movement/routes, modifiers, objects, shield/death opcodes, complete
MT19937 state, and the semantic projection:

```text
resident semantic state SHA-256:
bf1f559f19f9b3329f21ea8e298aa9b3fccf5bd6f7846623aa9281dc4067729f

resident RNG SHA-256:
bf37271f210f2b683fdc096ca61936b95b05c78f885ffa6a4a4d33712f5c92c1
```

This result establishes enough native headroom for the Rust boundary. The next
acceptance question is whether exact decision-boundary publication plus Python
observation/mask/reward consumers retains at least the required 20% end-to-end
gain.
