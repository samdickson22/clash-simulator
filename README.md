# Clasher

Clasher is a Clash Royale battle simulator with learned policies and search bots. The Python engine is the behavior reference. A Rust core accelerates qualified simulation and search workloads; reinforcement learning, imitation learning, and screen-only perception are separate research tracks.

## Status and results

These are simulator results on specific card pools, decks, opponents, and seeds. They do not establish official-client strength or complete game fidelity.

- **Fair public-information search:** the player derives elixir, hand, and cycle information from public history, then samples unresolved hidden state and future randomness. The 896-game evaluation passed its public-information checks. The policy-proposal variant scored 204/256 on holdout and 33/64 on Hog26; Hog26 remained a weakness. See [the report](reports/strategy_council_20260928/srp-public/REPORT.txt).
- **Search tuning:** the selected three-style opponent mixture scored 161/256 against the previous public player in a preregistered head-to-head confirmation. Wins count as 1 and draws as 0.5. See [the configuration, paired intervals, and limitations](reports/strategy_council_20260928/search-tuning/RESULTS.md).
- **Rust acceleration:** the P16 Stage 3 report measured a 75.66x aggregate complete-call speedup with exact candidate traces. Later stages extend card and controller coverage to C56. Each stage has its own scope and parity gates; these timings are not a blanket speed or fidelity claim. See [engine-speed reports](reports/strategy_council_20260928/engine-speed/README.md).

Training experiments include unsuccessful results. A lower imitation loss or faster search does not by itself establish a stronger policy. Screen-only perception and live-loop work remain research, separate from the simulator benchmarks above.

## Architecture

1. [`src/clasher/`](src/clasher/) implements battle state, cards, entities, movement, combat, and deterministic stepping in Python.
2. [`engine-rs/`](engine-rs/) exposes the Rust simulation core through PyO3. Python remains the default and the parity reference.
3. The [public search player](reports/strategy_council_20260928/srp-public/DESIGN.md) reconstructs a public board and searches sampled completions. [Search tuning](reports/strategy_council_20260928/search-tuning/DESIGN.md) defines proposals and opponent models.
4. [`src/clasher/rl/`](src/clasher/rl/) contains observations, action masks, policies, PPO, imitation, and evaluation. Actor and privileged critic inputs have distinct roles.
5. [`src/clasher/vision/`](src/clasher/vision/) and the [live-loop reports](reports/strategy_council_20260928/live-loop/) study screen observations and their uncertainty.

## Quickstart

Use Python 3.12 or newer for the optional Rust extension, which targets the Python 3.12 stable ABI. Run commands from the repository root.

```sh
git clone https://github.com/samdickson22/clash-simulator.git
cd clash-simulator
uv sync
```

Alternatively, install with pip:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

With pip, replace `uv run python` in the following commands with `python`.

```sh
# Inspect data paths.
uv run python scripts/run_clasher.py paths

# Run one bounded headless simulation with random legal actions.
uv run python scripts/run_clasher.py gym-smoke -- --episodes 1 --max-steps 128 --seed 17

# Open a pygame battle window on a desktop with a display.
uv run python examples/random_battle.py

# Run the Python suite.
uv run python -m pytest
```

Some research tests require local frozen artifacts, recordings, or checkpoints that are not distributed in Git. See [verification notes](docs/history/public-cleanup-verification.md) for the checkout baseline and the before/after comparison. The headless smoke command does not need a policy checkpoint.

To build the Rust extension, install a Rust toolchain with Cargo, then:

```sh
bash engine-rs/build.sh
PYTHONPATH=engine-rs:src uv run python -B engine-rs/test_parity.py
# Remove only this checkout's Cargo intermediates after verification.
cargo clean --manifest-path engine-rs/Cargo.toml
```

See [engine-rs](engine-rs/README.md) for backend admission limits. Training and checkpoint evaluation commands are in the [usage guide](docs/usage.md). `CLASHER_ROOT` can override the data root; the CLI's `paths` command shows what it resolves.

## Repository map

| Path | Contents |
| --- | --- |
| `src/clasher/` | Python simulator, RL, search, and perception code |
| `engine-rs/` | Optional Rust core, adapters, and parity tests |
| `tests/` | Python regression suite |
| `examples/` | Interactive battle examples |
| `scripts/` | Data, training, evaluation, analysis, and vision utilities; see [index](scripts/README.md) |
| `configs/` | Experiment and training configurations |
| `reports/` | Research designs, results, and reproduction commands; see [index](reports/README.md) |
| `docs/design/` | Pipeline and calibration design |
| `docs/history/` | Dated handoffs and maintenance records |
| `experiments/` | Historical experiments with pinned source/path contracts; see [retention notes](experiments/README.md) |
| `gamedata.json`, `decks.json`, `hitboxes.json` | Simulator inputs |

Generated datasets, checkpoints, native binaries, runtime snapshots, and captures are local artifacts. References to them in historical reports do not imply that they ship with this repository. Research papers are linked in [references](docs/references.md).

## Terms and attribution

This project is for research. Automating the official client violates [Supercell's Terms of Service](https://supercell.com/en/terms-of-service/), which prohibit bots and automation software. The simulator benchmarks do not require connecting to the official game.

Clasher is not affiliated with or endorsed by Supercell. This material is unofficial and is not endorsed by Supercell. For more information, see [Supercell's Fan Content Policy](https://supercell.com/en/fan-content-policy/). Clash Royale and its game assets belong to Supercell. The repository's code license is in [LICENSE](LICENSE).
