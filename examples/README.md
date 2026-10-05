# Battle examples

Run from the repository root after installing the dependencies:

```sh
uv run python examples/random_battle.py
uv run python examples/visualize_battle.py
```

Both use pygame and require a display. `random_battle.py` deploys cards automatically; `visualize_battle.py` provides the base battle viewer. The root `visualize_battle.py` compatibility link preserves the import used by the policy viewer and older local tools.

For a headless simulation, use `uv run python scripts/run_clasher.py gym-smoke -- --episodes 1 --max-steps 128`. More training and viewing commands are in [usage](../docs/usage.md).
