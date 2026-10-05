# Pilot ruleset authority audit

The discrepancy is real. The default training/benchmark path and the current readiness scalar path load different game-data bytes. It survives normalization, level scaling, actual entity construction and the actor's static semantic descriptors. This is a ruleset binding issue, not evidence that these balance differences teach ineffective play.

| Pilot card | Workspace default | Opened capture input | Actual level-11 spawned entity |
| --- | --- | --- | --- |
| IceSpirit | Base HP 90 | Base HP 84 | HP 230 versus 215; damage 110 in both |
| Goblins | Base damage 47 | Base damage 49 | Damage 120 versus 125; HP 202 in both |

The other fourteen cards have identical normalized card payloads, selected loaded mechanics and v4 card semantic vectors: Archers, Cannon, DarkPrince, Fireball, Giant, HogRider, IceGolem, Knight, Log, Musketeer, Prince, Skeletons, Tesla and Zap. All sixteen deployment probes were accepted. This audit checks the loaded definitions and newly created effects; it is not a gameplay-strength or dynamics-equivalence test.

IceSpirit changes semantic-v4 column 5, the legacy HP descriptor. Goblins changes columns 6, 16 and 27, named damage, DPS and spell_damage by the existing feature schema. Exact values and spawned-entity records appear in `comparison.json`. These are not differences caused by a mocked fixture.

The two file pins are:

- Workspace `gamedata.json`: `3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a`.
- Opened `reports/calibration_development_20260915/expanded-deck-development/forward-0/gamedata.json`: `daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3`.

The capture path resolves through the existing archival compatibility link into `artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/...`. The audit did not alter either path or file.

`CardDataLoader()` resolves the workspace default through `paths.gamedata_path`. `SelfPlayBattleEnv.reset` constructs `BattleState` without an explicit loader. Its default observation builder, the benchmark's explicit `StructuredObservationBuilder`, the training entry builder and worker builders likewise use the default loader. A direct instantiated default environment confirmed both battle and observation builder use workspace `gamedata.json`.

In contrast, `scripts/run_readiness_v2.py::components` constructs `CardDataLoader(capture / "gamedata.json")`, passes it to `public_reference_builder`, and returns it to the runner. `scripts/compare_reacting_public_branches.py::scalar_initial` passes that loader into `BattleState`. The audit called that actual constructor on the opened initial/config files and confirmed capture-loaded IceSpirit has level-11 HP 215. The capture declares both level cap and minimum card level 11.

There is one separate loader bypass to account for when binding a ruleset. At nominal level 11, `BattleState.resolve_card_play` takes spells from the process-global `SPELL_REGISTRY`, whose lazy initialization calls `load_dynamic_spells()` with the default data file. Supplying a different `BattleState.card_loader` alone does not bind those spell instances. For this exact pilot comparison Fireball, Log and Zap have identical normalized payloads and effective spell values in both files, so the bypass creates no observed spell discrepancy. It should still be included in the provenance check rather than claiming the explicit card loader controls every effect.

The smallest operational binding is an immutable future training package whose bundled default `gamedata.json` has the same hash as the data used by the admitted scalar run. This naturally binds the existing default card loaders, spell registry and actor metadata together. Keep the current workspace file and opened capture intact, pin the package's effective data hash plus source/config hashes, and reject a resumed checkpoint or worker with a different pin. Do not point `CLASHER_ROOT` at the archived capture, which also changes default output paths.

If future jobs must select data in place, add one explicit path/hash binding and pass it consistently to environment, observation/semantic builders, worker configuration, teachers and evaluation. Ensure spell resolution uses that same bound source or validates equality for the admitted spell scope. Checkpoint static feature buffers also need the recorded ruleset pin because loading weights restores their saved values.

An equally valid prospective choice is to evaluate the workspace ruleset and train on it. That requires declaring the scalar data pin separately from the native observation data, using the intended scalar builder/loader in the gate, and completing that gate before learning. Neither option requires changing combat mechanics or deciding these two numerical differences are harmful. What is unsupported is transferring admission from one effective ruleset to an unrecorded other one.

Reproduce with `OMP_NUM_THREADS=1 .venv/bin/python reports/strategy_council_20260928/m0/data-authority/audit.py`. The script reads existing inputs and writes only this audit directory. No source edits, native collection or policy fitting occurred.
