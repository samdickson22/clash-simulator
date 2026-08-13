# Rust simulator evidence gate

Date: 2026-08-13  
Worktree: `/Users/sam/.codex/worktrees/rust-clasher`  
Branch: `codex/rust-simulator-prototype`

## Decision

Stop before a simulator rewrite. The evidence rejects a fine-grained Rust
boundary, and the first boundary large enough to plausibly meet the predeclared
20% end-to-end gain is the complete native tick. Porting that boundary requires
targeting, collision and avoidance, movement and pathing, combat, projectiles,
status/death/spawn callbacks, pending queues, cache publication, and exact update
ordering. That is already the central simulator rewrite and needs a staged design
review before implementation.

No Rust production mode is claimed. The checked-in Rust crate measures the FFI
boundary only. Python remains the sole simulator implementation and fallback.

## Provenance and factorial baseline

The worktree was created from current committed training HEAD `20cc861` without
modifying `/Users/sam/Desktop/code/clasher`. The optimized-Python arm applies the
source/test delta `20cc861..2787705`; the patch SHA-256 is
`e93b3ba0c9a73c040d1edd34b38fd45e40856ebcdb3c8371964225e8ead52db5`.
The relevant files were byte-verified against `2787705` before final tests and
measurements.

This arm includes the verified optimizer lineage through:

- exact action-mask gathering and occupancy caching;
- stationary-opponent observation/mask reuse;
- preallocated CPU observation buffers and scalar structured-observation clips;
- dense routes/buckets, exact spatial collision/avoidance pruning, and path caches;
- incremental target/cache refresh and Crown fallback reductions;
- exact specialized battle/player/entity/card clone paths;
- oracle root/action/node/backup/scalar-leaf allocation reductions.

Dirty reward, model, learner, checkpoint, corpus, and report changes from the
training checkout were not copied. A temporary wholesale copy of selected current
training files was measured and rejected as a baseline construction because those
files intentionally contain only hand-integrated subsets and overwrite later
verified optimizer commits. Those rejected cold and warm measurements are not used
for Rust acceptance.

Rust acceptance is therefore defined against the verified `2787705`
optimized-Python arm, not stale `20cc861`. No Rust candidate reached the point of
an acceptance timing.

## Phase 1: differential parity harness and generated coverage

Commits:

- `6e67fe8`: exact per-tick differential snapshot and first-mismatch dump;
- `d9d72b2`: deterministic data-driven interaction catalog and shard manifests;
- `0aba076`: executable interaction battle construction and shard runner.

The snapshot schema encodes exact binary64 values with `float.hex()`, complete
battle RNG state, players, every entity and mechanic field, pending effects,
fast-path arrays/caches, and optional observations/masks. Entity references inside
caches are normalized to stable entity IDs. Immutable card definitions are
represented by catalog revision metadata. Comparisons use no float tolerance and
stop at the first differing path. Mismatch artifacts are atomically published.

The enabled deck file resolves to 46 troop/champion cards. Generated coverage is:

| Catalog | Declared coverage | Cases |
|---|---|---:|
| 1v1 | all 46x46 ordered roles, two mirrored placements, scalar and fast | 8,464 |
| 2v2 | all unordered matchups of 1,081 two-card team multisets | 584,821 |

For 2v2, spawn order, target order, placement geometry, scalar/fast mode,
simultaneous attack/death, stun, slow, rage, death payload, projectile, retarget,
and allied-collision axes are **systematic, not exhaustive Cartesian coverage**.
The manifest says this explicitly. The full generated catalogs were not executed
against Rust because no simulator candidate passed the boundary gate. Executed
coverage in this prototype was 25 harness/matrix/scenario tests plus a two-case
shard smoke run. Its digest was
`231174fe5be58b9ba6b7ca887e5b8797a53790058cdd2ed913b1aaa50d822e7f`.

The generator also inventories every existing top-level Python test file and its
static test functions without pretending that static AST counts equal pytest's
parameter-expanded count.

## Phase 2: FFI and marshalling evidence

Commit `9d237419` adds a minimal PyO3 `abi3-py310` extension, optional Python
wrapper, exact reference tests, and a reproducible benchmark. It does not mutate
battle state.

Machine and method:

- Apple M4 Pro, macOS 26.5.2 arm64;
- Python 3.12.13, Rust 1.97.1;
- release build through maturin/PyO3;
- nine repetitions;
- 200,000 calls per no-op repetition;
- 20 calls per state-buffer repetition;
- representative exact snapshot size: 364,337 bytes.

Command:

```bash
source .venv/bin/activate
uvx maturin develop --release --manifest-path rust/clasher-core/Cargo.toml
uv run python scripts/perf/benchmark_rust_boundary.py \
  --repetitions 9 --calls 200000 --state-calls 20 \
  --json-out reports/rust_boundary_20260813.json
```

| Boundary | Median latency | Calls/s |
|---|---:|---:|
| Python loop assignment control | 9.0 ns | 111,698,027 |
| Python to Rust no-op | 92.3 ns | 10,834,114 |
| Python FNV scan of state bytes | 17.902 ms | 55.9 |
| Python-to-Rust buffer plus Rust scan | 375.7 us | 2,661.9 |

The Rust and Python FNV results match exactly. A Python-to-Rust call itself is
cheap, but materializing and moving the full causal state every tick is not. A hot
boundary must keep compact mutable state resident in Rust for at least a complete
tick or decision interval.

## Production-shaped Python attribution

### Warm single-process random rollout profile

Workload: eight environments, 64 two-player random-legal decisions after four
warm-up decisions, eight native ticks per decision, engine fast path on. cProfile
recorded 3.569 s cumulative wall for the driver.

| Inclusive component | Cumulative seconds | Share of driver |
|---|---:|---:|
| environment step | 3.177 | 89.0% |
| native logic ticks | 3.061 | 85.8% |
| troop movement component | 0.843 | 23.6% |
| target selection | 0.590 | 16.5% |
| troop combat component | 0.646 | 18.1% |
| troop collision accumulation | 0.293 | 8.2% |
| structured observations | 0.345 | 9.7% |
| action masks | 0.048 | 1.3% |

Shares are inclusive and overlap. Even deleting target selection completely would
not meet the 20% end-to-end gate. Targeting also calls mechanic-owned validity,
stealth, pending-projectile, plane, Crown fallback, and range semantics, so it is
not an isolated pure kernel.

### Warm oracle profile

Workload: seed 2301, oracle seed 901, depth 6, 32 simulations, 64 sampled actions,
eight-tick planner decisions, optimized fast path. One warmed selection took
0.973 s under cProfile.

| Inclusive component | Cumulative seconds | Share of selection |
|---|---:|---:|
| joint action plus interval advancement | 0.877 | 90.1% |
| native logic ticks | 0.820 | 84.3% |
| movement component | 0.202 | 20.8% |
| target selection | 0.134 | 13.8% |
| collision accumulation | 0.114 | 11.7% |
| battle cloning | 0.037 | 3.8% |
| legal masks | 0.035 | 3.6% |

The existing exact clone and planner allocation work has moved the bottleneck into
the same complete tick as production rollouts.

### Five-repetition 12-process factorial

Each mode used 12 forked CPU workers, eight warm-up decisions per worker, then 96
fresh fixed-seed decisions per worker. Seeds were 48,139 through 48,150, decision
interval 8, max ticks 2,048. The interval is a two-sided t interval over five
matched aggregate-throughput repetitions. No MPS, learner, checkpoint, or file
mutation ran.

```text
scalar/off median  1,995.7 decisions/s, mean 1,944.7, 95% CI [1,851.3, 2,038.2]
fast/on median     2,840.6 decisions/s, mean 2,836.9, 95% CI [2,772.5, 2,901.4]
shadow median      2,845.8 decisions/s, mean 2,827.7, 95% CI [2,667.9, 2,987.6]
```

All twelve worker hashes match exactly across off, shadow, and on. A separate
2,048-decision shadow audit performed 29 scalar comparisons and recorded zero
mismatches. Raw rows and hashes are in
`reports/rust_12worker_factorial_20260813.json` (SHA-256
`63ed5d48a7bf23bcbc4957e2bcb44c0edce97f754ea274e542677bc1a83a847b`).

Existing inherited evidence also covers stationary strategy, crowded exact-engine,
oracle clone, action-mask occupancy, and observation-buffer workloads. In
particular, balanced strategy improved 21.65% from stationary observation/mask
reuse; crowded exact-engine trait/collision work improved 19.14% scalar and 18.35%
fast; battle clone improved 27.7x and the fixed oracle probe 2.13x. Those results
are provenance evidence for the optimized arm, not new Rust measurements.

## Rejected Rust boundaries

| Boundary | Reason for rejection |
|---|---|
| Per scalar/math helper | 92 ns FFI is unnecessary; hot share is too small |
| Per entity target query | target selection is only 16.5% of rollout and 13.8% of oracle; cannot meet 20% even at zero cost |
| Per entity collision query | only 8.2% of rollout; state changes between sequential movement components |
| Route/path kernel only | existing exact compiled/path caches already reduce it; oracle share is below gate |
| Clone/serialization only | clone is 3.8% of warmed oracle after the 27.7x Python optimization |
| Full state marshalled each tick | 375.7 us for a 364 KB buffer before simulation work |

The smallest plausible boundary is a resident Rust battle core advanced for one
complete tick or decision interval. That is not a bounded hot-path port.

## Design required before a whole-tick prototype

### State ownership

Rust must own all mutable players, entities, mechanic state, pending casts and
impacts, component queues, IDs, spatial/target caches, tower/win state, and battle
timers for the lifetime of a battle. Python may submit joint actions and request
observations/snapshots. Python object graphs cannot remain authoritative between
ticks.

### RNG equivalence

The battle core must import/export Python `random.Random` MT19937 state and match
Python's `random`, `choice`, and `shuffle` bit consumption exactly. Planner NumPy
RNG remains Python-owned until the planner itself moves. Shadow comparison must
include both complete RNG states after every tick.

### Numeric semantics

Use integer logic units and integer work accumulators where Python already does.
Keep remaining binary64 fields as strict Rust `f64` with no fast-math or reassociation.
Implement Python-compatible rounding, truncation, signed zero, infinity, operation
order, and fixed 50 ms component boundaries. No tolerance is allowed in parity.

### Mechanics and callbacks

Normalized game data should compile to versioned data-driven mechanic opcodes. A
Rust tick cannot call back into Python per entity or mechanic. Any unsupported
reachable mechanic must fail preflight and keep the entire battle on Python; it
must never silently fall through. There are no card-name exceptions.

### Serialization and mismatch dumps

The hot path needs a compact versioned binary representation, not JSON. The
checked-in canonical JSON schema remains the diagnostic format. Shadow mode should
fail on the first differing path and atomically write initial, expected, and actual
snapshots plus actions and RNG state.

### Runtime modes and fallback

Future integration must expose `off`, `shadow`, and `on`:

- `off`: Python only;
- `shadow`: Python and Rust advance from identical state and compare every tick;
- `on`: Rust only after deck/mechanic preflight succeeds.

Fallback occurs only before a battle starts. Mid-battle fallback would require an
exact reverse conversion and could conceal drift.

### Build and packaging

The prototype uses maturin, PyO3, and `abi3-py310`. Wheels need macOS arm64 first,
then the project's supported platforms. Import failure or unsupported platform
must leave Python `off` mode available. The optional extension cannot become a
mandatory install until parity and packaging gates pass.

## Gates run

```text
Rust unit tests: 1 passed
Rust boundary tests: 11 passed
Harness/matrix/scenario focused tests: 25 passed
Restored optimized-arm focused gate: 94 passed
Enabled/reachable/projectile/spell/targeting/path/action-mask gate: 870 passed,
  1 infrastructure failure because committed 20cc test expected an uncommitted
  training-only reward_profile argument intentionally excluded from this worktree
Ruff: optimizer-owned Python files clean
Mypy: optimizer-owned Python files clean
Shadow: 29 checks, 0 mismatches over 2,048 decisions
12-worker hashes: off == shadow == on for all 12 seeds and all 5 repetitions
```

The one excluded failure is not a simulator mismatch: the test calls
`compute_rollout_digest(..., reward_profile="defense-v2")`, while the intentionally
excluded dirty reward/self-play API is absent from committed `20cc861`. No golden
hash was changed and no tolerance was weakened.

## Review gate

Do not begin the whole-simulator port from this branch without reviewing the
resident whole-tick design above. A reviewed next phase should first implement a
small, mechanics-complete subset selected by serialized capabilities, run all
8,464 generated 1v1 cases relevant to that subset plus the systematic 2v2 shards,
and then measure matched end-to-end production rollouts. If the candidate does not
improve decisions/s by at least 20% versus the optimized-Python arm, reject it
without expanding the Rust boundary.
