# Stage 1 spike: no-go for Stage 2

2026-10-03. Stage 0 admitted this experiment on its fixed repeated measurement,
with the substantial timing variance disclosed in `STAGE0.md`.

The experimental `engine-rs/clasher_core` crate builds and imports through Pyo3.
It has independent native state and `step`, `clone`, `apply_action`, `digest` and
snapshot methods. Ticks do not call Python. Card statistics and the arena cost
map are imported before timing; immutable configuration is shared by clones.
Python remains the default and authoritative engine.

The port includes Knight, Archers, Giant and Musketeer, towers, ordered A*, route
goals, integer movement, collision/avoidance phases, ordinary attack clocks,
projectiles, elixir/refill and MT19937 state import. This is an incomplete parity
prototype, not an accepted backend. There is no learner or evaluation integration.

## Gate evidence

`engine-rs/differential.py` compares the same `es_common.battle_digest` byte format
after every tick. Twelve games vary lane and deployment depth, with all deployments
restricted to the four-card slice. Initial imported state digests match. Scripted
command acceptance also matches on every command.

| Card | Python scenario ticks | Mismatching boundaries | First divergent ticks across three games |
|---|---:|---:|---|
| Knight | 6,600 | 5,623 | 438, 261, 275 |
| Archers | 5,885 | 4,559 | 426, 443, 460 |
| Giant | 2,589 | 934 | 536, 553, 569 |
| Musketeer | 6,600 | 4,647 | 640, 641, 669 |
| Total | 21,674 | 15,763 | |

All cards exceed the 2,000-tick coverage floor, but **byte identity fails**.
These are mismatching tick boundaries, not 15,763 independent root causes.

The final one-core timing sums are 1,300.09 Python ticks/core-s and 95,301.42
native ticks/core-s. Their nominal ratio is 73.30x. **This does not pass the 30x
gate:** the trajectories, entity populations and outcomes diverge, so the native
runtime is doing different work. No accepted same-trajectory 30x result exists.

Clone took **1.344 microseconds** in Rust versus 1,197.995 microseconds in Python,
over 1,000 calls on the same imported 16-entity root. The immediate clone digest
matched and stepping the clone left its parent unchanged. This narrow prototype
clone measurement passes the 20-microsecond threshold; it does not establish the
cost of a future complete state representation.

Primitive differential checks passed separately:

- MT19937: 2,000 32-bit values, 2,000 double draws and 600 bounded draws, zero differences.
- A*: 2,000 routes with dynamic cost overlays, zero differences.

**Decision: no-go for Stage 2.** Retain Stage 0. The Rust crate is reviewable
experimental work, and must not generate training data, teacher labels or evals.

## Verified remaining blocker

A short replay isolates the first Knight-game divergence. At tick 436, Python
towers 1 and 5 mark their targets as pending-lethal. When those targets disappear
at tick 437, Python sets `_resume_pending_hit=True` and keeps finish time at zero.
The Rust prototype instead installs finish work of 1 ms. At tick 438 Python
acquires targets 28 and 26; Rust waits with no target and a 51 ms finish counter.
The saved evidence is `results/stage1_first_difference_detail.json`.

The next parity work must carry the pending-projectile reservation and retained
hit state through targeting, object-phase impacts and removal callbacks. A broad
"clear target on death" rule is insufficient. Giant cases additionally show
different movement and target IDs after Crown-state changes; their exact first
dumps are preserved, but that branch has not been reduced to an independent cause.

The spike also exposed and corrected finite tower preload, right-lane Archer
formation ordering, projectile muzzle/public-target representation, ordered
avoidance buckets, collision-vector composition, target-removal callbacks, King
activation phases and continued projectile flight after target removal. These
corrections improved the matching prefixes but did not close the gate.

## Revised estimate and artifacts

Planning estimate: allow **8 to 12 engineer-days for a parity-complete Stage 1**,
up from 5 to 8, then the original 20 to 30 days for Stage 2. That puts the 16-card
engine at roughly 28 to 42 engineer-days, excluding the public script and C56.
This is an estimate, not permission to start Stage 2 or evidence that parity is
close. Re-admission requires zero differences on the full slice before timing
can count toward the speed gate.

Source and build instructions are in `engine-rs/README.md`. Final data:
`results/stage1_differential.json`, `logs/stage1_differential_final.log`, and
`results/stage1_first_difference_detail.json`. Earlier replay results are retained
as diagnostics and do not replace the final receipt. The initial replay's saved
Python hand lists aliased live state; that reporting bug was fixed before the
expanded and final replays.

Pyo3's macOS linker flags and explicit `strip = "none"` make the local extension
load successfully. The loader issue matches the upstream
[Rust report](https://github.com/rust-lang/rust/issues/157750). Build logs are retained.
The binary remains local and Git-ignored; Cargo intermediates are cleaned after
copying it. Neither the Python engine nor protected/frozen files were changed
during Stage 1.
