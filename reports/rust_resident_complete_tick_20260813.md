# Resident Rust complete-tick milestone

## Scope

Commit `c76c434b` introduced the first atomic resident complete-tick transaction
for its declared fail-closed capability subset. The transaction owns clock/player,
direct combat, exact ground movement, building lifetime, modifiers, globally
ID-ordered character/point-projectile object work, cleanup, Crown synchronization,
and conditional win refresh. Unsupported mechanics reject before mutation.

## Machine and toolchain

- Mac mini, Apple M4 Pro, 12 CPU cores (8 performance + 4 efficiency), 24 GB RAM
- macOS 26.5.2 (25F84)
- Python 3.12.13
- rustc 1.97.1
- single process, CPU only; no MPS/GPU and no worker pool
- Rust extension built with `maturin develop --release`

## Connected fixed-seed workload

The fixed fixture uses `BattleState(rng=random.Random(9917))`, the six standard
Crown Towers, and one fully deployed mechanic-free Knight per player at connected
positions. Each arm advances 250 exact 50-ms logic ticks. Root construction and
Python/Rust cloning are outside the timed interval. Three warmups preceded nine
repetitions. Timing used `time.perf_counter_ns()`; confidence intervals are
two-sided 95% Student-t intervals for the repetition mean (8 degrees of freedom).

```text
uvx maturin develop --release --manifest-path rust/clasher-core/Cargo.toml
PYTHONPATH=src:. .venv/bin/python <inline fixed-seed complete-tick driver>
```

| Arm | Median wall time / 250 ticks | Mean (95% CI) | Ticks/s |
|---|---:|---:|---:|
| optimized Python scalar | 0.022725541 s | 0.022845671 s [0.022541049, 0.023150293] | 11,000.84 |
| resident Rust release | 0.002404625 s | 0.002428574 s [0.002387135, 0.002470013] | 103,966.31 |

Resident Rust is **9.4508x** faster for this connected declared-capability workload.
This is a whole-battle tick measurement, but not yet an end-to-end RL rollout
claim: Python observation/action/reward publication and broader mechanic coverage
remain outside the resident boundary.

The final timed states were compared through every available exact component
projection: clock, players, locked combat, movement/routes, building lifetime,
modifiers, character object state, point projectiles, roster/IDs, complete MT19937
state, tower/winner state, and dirty-win state. No tolerance was used.

```text
resident RNG SHA-256:
c9a6b294d884aab918807db9e080b65f8a5e4365d098332a4adeb54d73355621

resident entity-state SHA-256:
496a6bfe534da08d54a2f4547bb5942d7d6ef801a892220540227649d2848ae4
```

The earlier debug-profile measurement showing a connected-path slowdown is
rejected as non-production build evidence. Release-profile attribution is the
authoritative measurement for the Rust boundary.

## Gates at the milestone plus targeting follow-up

```text
610 tests/test_rust_*.py passed
cargo fmt --check passed
cargo clippy --all-targets -- -D warnings passed
Ruff and targeted mypy passed for optimizer-owned Python files
```

The resident runtime remains fail-closed. This evidence does not enable Rust-on
for unsupported cards and does not authorize silent fallback after a battle starts.
