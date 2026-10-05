# Unadmitted training staging

This 3.1 MB staging package binds the default engine, spell registry, stat-scaling table and semantic loader to the readiness capture's game data. It contains no copied production source and grants no training authorization. The only executable path is a short no-fit proof, plus a verify-only mode.

The copied input hash is `daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3`. The original workspace `gamedata.json` remains untouched. The training, development and acceptance deck-role files retain their roles-v2 hashes. The default `inputs/decks.json` is an exact copy of the training role file, so an omitted deck argument cannot select acceptance data.

`launch.py` verifies the 332 production Python files, project metadata, dependency lock, installed local entry-point metadata, staged data, role files and proof helpers. It starts a fresh process with `CLASHER_ROOT` and its working directory both set to `inputs/`. Setting the working directory matters because relative deck paths check the current directory before the project root. `PYTHONPATH` points to the pinned workspace source, and source hashes are checked again after the proof. A later source edit makes this staging revision fail verification rather than silently changing it.

The launcher uses `-B` and an empty package-local bytecode location. Temporary, NumPy/Numba and Torch cache paths stay under `runtime/`. Inputs, manifest and helper scripts are read-only. The package depends on the current local virtual environment; it is a verified local launcher, not a self-contained remote container image. Installed dependency versions and interpreter identity are recorded in `runtime/proof.json`.

Static-asset inspection found the relevant runtime readers use game data and deck JSON. The game-data file supplies card definitions, the lazy spell registry, Common level multipliers and Princess Tower payloads. Arena path rows and balance/tower constants are embedded in pinned Python source. The proof observed no read of workspace `gamedata.json` or workspace `decks.json`. It did observe the local editable-install entry-point metadata, which is included in the pin manifest. No hitbox JSON or native CSV was read by this scoped path; those unused assets were not copied.

The completed proof imported 92 project modules from the pinned source tree and verified:

- Default engine IceSpirit level-11 HP is 215 and Goblins damage is 125.
- Default Fireball, Log and Zap spell instances use the staged default data, with damage 688, 268 and 192.
- The semantic descriptors use IceSpirit base HP 84 and Goblins base damage 49.
- A public-v4 observation with levels/confidence and public legality survives sequence construction and one fresh policy forward pass. Model weights remain unchanged.
- Modified source, data and deck-role hashes are rejected using in-memory negative controls. Neither the source nor the pinned files was changed for these controls.

Run from any directory with the existing virtual environment:

```sh
/Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/training-package/launch.py --verify-only
```

Omit `--verify-only` to repeat the bounded proof. Other arguments are rejected. Results are in `runtime/proof.json`, `runtime/proof.stdout.log` and `runtime/pin-rejection-proof.json`. Earlier harness failures are retained in `runtime/attempt*.stderr.log`; they concern the audit's handling of `/dev/null`, namespace packages and editable-install metadata. The final proof passes.

A future admitted training launcher can reuse this data/source binding after adding its frozen recipe, approved execution limits, checkpoint ruleset checks and training entry point. This staging package deliberately has no such entry point. There were no labels, optimizer steps, policy fitting, native calls, commits or changes outside this report directory.
