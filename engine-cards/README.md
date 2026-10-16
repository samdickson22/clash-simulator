# Experimental pilot Rust core

Stage 2 passes all requested gates for the 16 pilot cards: 64 terminal games with zero digest/action/RNG mismatches, 2,048 live imports with 200-tick continuations, and exhaustive public-mask placement checks. Final stepping is 50.08x Python; the largest measured per-root native clone mean is 5.72 microseconds. See `../reports/strategy_council_20260928/engine-speed/STAGE2.md` for scope, root causes and receipts.

Stage 3 also passes native SRP admission: 256 live mask/feature roots, 32 native-driven full games, 200 searchable planner calls with 3,999 exact candidate traces, and 46 regressions. Final complete-call CPU is 2.306219 seconds in Python versus 0.030481 seconds natively, a 75.660x aggregate speedup. See `../reports/strategy_council_20260928/engine-speed/STAGE3.md` for receipts and scope.

Python remains authoritative and is the default. With `PYTHONPATH=engine-rs:src`, opt in using `ScriptRolloutPlanner(..., backend="native")`. The qualified backend supports level-11 P16, standard tournament rules, canonical public-v4 with the untyped OQ vocabulary, defense-v2 and either the same public script or default balanced StrategyBot. Candidate generation stays in Python. The srp-dagger kit and training entrypoints were not changed.

## API and live import

The Pyo3 class exposes `step(ticks=1)`, `clone()`, `apply_action(player, card, x, y)`, `digest()`, `snapshot()`, `debug_step()` and `rng_state()`. Stepping and cloning are native and never call Python. Immutable card/arena configuration is shared across native clones.

With `PYTHONPATH=engine-rs:src`:

```python
import clasher_core
from differential import config, snapshot
from stage2_matches import PILOT

cfg = config(PILOT)  # once per immutable ruleset
native = clasher_core.BattleState(snapshot(python_battle, cfg))
branch = native.clone()
branch.apply_action(0, "Knight", 4.5, 10.5)
branch.step(200)
digest = branch.digest()
```

`snapshot()` restores live tick/action-boundary roots, including pending Zap casts, all pilot clocks/effects, active projectiles, and frozen stopped routes. `live_snapshot.py` contains the read-only adapter. Native leaf evaluation additionally needs the unslowed public movement modes; the planner wrapper imports these with `set_public_movement_speeds` so charge and slow transitions retain exact reward values. Card names absent from the imported configuration raise an error.

## Build and checks

```sh
bash engine-rs/build.sh
PYTHONPATH=engine-rs:src nice -n 10 .venv/bin/python -B engine-rs/test_parity.py
PYTHONPATH=engine-rs:src nice -n 10 .venv/bin/python -B engine-rs/test_stage2.py
bash engine-rs/evidence-stage2/final_games.sh
bash engine-rs/evidence-stage2/run_snapshots.sh
```

The long runners use atomic per-game/per-root receipts and source/binary fingerprints. Launch them through `reports/strategy_council_20260928/pilot/detach.sh LOGFILE CMD ARGS...` for restart-safe execution. PROGRESS.md records the current commands and process ownership. Do not replace the extension while any validation process uses it.

To trace a known full-game transition:

```sh
PYTHONPATH=engine-rs:src nice -n 10 .venv/bin/python -B engine-rs/stage2_matches.py --case 62 --trace-tick 2291 --output /tmp/clasher-transition.json
```

`differential.py` retains the Stage 1b four-card diagnostic suite and defaults; its historical `stage2_go` field means admission to Stage 2 implementation, not completion of Stage 2. Final Stage 2 admission is recorded in STAGE2.md and `stage2_manifest.json`.

`build.sh` uses one Cargo job and nice 10. Its default target directory is `engine-rs/target` in this checkout; `CARGO_TARGET_DIR` and `PYO3_PYTHON` can override the build directory and Python interpreter. Keep the copied extension and clean only this checkout's intermediates when idle:

```sh
cargo clean --manifest-path engine-rs/Cargo.toml
```

Some regression and full-game checks require frozen deck files, snapshots, and checkpoints that are not distributed in Git. The [public cleanup verification notes](../docs/history/public-cleanup-verification.md) distinguish checkout-only failures from checks supplied with local fixtures. Stage reports retain the historical admission scope and receipts.
