# Resident Rust target-acquisition optimization

## Scope

This milestone replaces temporary troop/building/crown candidate vectors in the
resident direct-combat target-acquisition path with exact encounter-order minima.
It preserves the Python category order (troops before native building targets),
strict first-nearest comparisons, the `1e-6` symmetric-building window, the
owner-relative building key, and princess-before-King fallback. It does not
change the Python simulator or broaden the resident capability predicate.

## Machine and toolchain

- Mac mini, Apple M4 Pro, 12 CPU cores (8 performance + 4 efficiency), 24 GB RAM
- macOS 26.5.2 (25F84)
- Python 3.12.13
- rustc 1.97.1
- single process, CPU only; no MPS/GPU and no worker pool

## Fixed workload

The benchmark constructs one resident battle from `BattleState(rng=random.Random(9917))`
with 48 deployed, mechanic-free Knights (24 per player) in a crowded fixed grid.
Every actor starts without a target and with a non-firing cooldown. Each timed
iteration forks the same immutable resident root and advances exactly one complete
direct-combat phase, forcing crowded target acquisition while holding fork cost
constant across arms.

Each arm used 20 untimed warmups followed by 9 repetitions of 800 phases. Timing
used `time.perf_counter_ns()`. The reported confidence interval is the two-sided
95% Student-t interval for the repetition mean (8 degrees of freedom). The command
shape was:

```text
PYTHONPATH=src:. .venv/bin/python <inline fixed-seed crowded-acquisition driver>
```

The baseline used commit `c76c434b`; the candidate changed only
`rust/clasher-core/src/lib.rs`. The extension was rebuilt before each arm with:

```text
uvx maturin develop --manifest-path rust/clasher-core/Cargo.toml
```

## Results

| Arm | Median wall time / 800 phases | Mean (95% CI) | Phases/s | Actor decisions/s |
|---|---:|---:|---:|---:|
| `c76c434b` baseline | 0.154765834 s | 0.154655097 s [0.153688663, 0.155621532] | 5,169.10 | 248,116.78 |
| allocation-free candidate | 0.131929666 s | 0.132019657 s [0.131351653, 0.132687662] | 6,063.84 | 291,064.18 |

The candidate is **1.1731x / +17.31% throughput** on this acquisition-attribution
workload and reduces median wall time by 14.76%. This is not claimed as whole-RL
rollout speedup; steady locked-target battles spend much less time acquiring.

Parity evidence is exact for both arms:

```text
locked direct-combat state SHA-256:
410cc640d746851af53ddd9289207c4281bafbe28189c0dfbce15d53c81428b6

complete resident RNG SHA-256:
c9a6b294d884aab918807db9e080b65f8a5e4365d098332a4adeb54d73355621
```

## Gates

```text
111 targeting/complete-tick/scalar parity tests passed
610 tests/test_rust_*.py passed
cargo fmt --check passed
cargo clippy --all-targets -- -D warnings passed
Ruff passed for the changed Python test
mypy passed for the changed Python test (untyped/import errors disabled only)
git diff --check passed for the three optimizer-owned files
```

The focused cases include encounter-order troop ties, a building inserted before
an equidistant troop, a strictly closer building, mirrored owner-relative building
ties, data-driven Crown fallback, target switching, and complete resident RNG
invariance.
