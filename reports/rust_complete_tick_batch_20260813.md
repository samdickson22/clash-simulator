# Resident Rust decision-interval batching

## Scope

This milestone adds `advance_complete_ticks(N)`, which clones the mutable
resident battle once, advances the entire exact tick window transactionally,
and commits once. The prior public loop called `advance_complete_tick()` `N`
times and therefore cloned the resident battle `N` times. The one-tick API is
retained for shadow-mode first-divergence diagnostics.

The same milestone adds Python-compatible `_shield_break_count` state. A shield
transition from positive HP to zero increments the entity-owned counter exactly
once; partial hits and later hits against an already-broken shield do not. The
counter is included in semantic shadow state (schema version 3).

## Machine and toolchain

- Mac mini, Apple M4 Pro, 12 CPU cores, 24 GB RAM
- macOS 26.5.2 (25F84)
- Python 3.12.13
- rustc 1.97.1
- single process, CPU only; Rust extension built with `maturin develop --release`

## Fixed workload and method

The fixed fixture uses `BattleState(rng=random.Random(9422))`, the six standard
Crown Towers, a deployed Knight for player 0, and a deployed Musketeer for
player 1. Each decision interval advances exactly 32 resident 50-ms ticks.
Root construction and the common outer `root.fork()` are outside the timed
interval, so the comparison isolates the transaction clone count:

- baseline: 32 calls to `advance_complete_tick()`;
- candidate: one call to `advance_complete_ticks(32)`.

Five alternating warmups preceded 30 alternating repetitions. Timing used
`time.perf_counter_ns()`. Confidence intervals are two-sided 95% Student-t
intervals for the repetition mean (29 degrees of freedom).

```text
uvx maturin develop --release --manifest-path rust/clasher-core/Cargo.toml
PYTHONPATH=src:. .venv/bin/python <inline fixed-seed 32-tick batch driver>
```

| Arm | Median wall / decision | Mean wall (95% CI) | Decisions/s | Ticks/s |
|---|---:|---:|---:|---:|
| repeated one-tick transactions | 0.000130480 s | 0.000139581 s [0.000133277, 0.000145885] | 7,164.32 | 229,258.17 |
| clone-once 32-tick transaction | 0.000078688 s | 0.000082386 s [0.000079330, 0.000085442] | 12,137.96 | 388,414.72 |

The clone-once boundary is **1.6942x faster** and reduces mean resident wall
time per 32-tick decision interval by **40.98%**. This is resident-boundary
attribution, not an end-to-end RL rollout claim; Python action ingress,
observation/reward publication, and unsupported mechanics remain outside this
measurement.

The final repeated and batched states matched exactly, including complete
MT19937 state:

```text
resident semantic state SHA-256:
61e35e10e575fcdddf50ab6fb5cf738bc794a40bb27923c8c4dfe081c0d843cc

resident RNG SHA-256:
b18f13a1f11862a9956b27878d3c868ed0101ab6c3f0cf039ee4b807eed18e8c
```

## Correctness gates

- batch equals repeated Python ticks for fixed connected battles;
- terminal ticks count once and later batched calls are exact no-ops;
- zero/negative windows do not mutate resident state;
- shield direct/projectile breaks, partial hits, post-break HP damage, complete
  ticks, semantic shadow snapshots, and RNG state are exact;
- unsupported complete-tick states remain transactionally fail-closed.
