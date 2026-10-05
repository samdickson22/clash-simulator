# Gamedata canonicalization

Complete. Ready marker time: 2026-10-04T05:51:20+00:00. No open issues within the requested scope.

Workspace gamedata SHA256: `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`.
Admitted v4/v5/native-final-v7 SHA256, independently verified identical: `daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3`.

Changed `items.spells[30].summonCharacterData.hitpoints`, IceSpirits, 90 -> 84, and all eleven nested Goblin_Stab damage leaves, 47 -> 49. Exact paths are in `canonical/data_diff.json`. Workspace data equals admitted data everywhere except meta. The original fingerprint is retained; the new meta note records canonicalization and admitted SHA. Original bytes remain in `canonical/gamedata.base-3d99987c.json`.

The P16 and OQ paths explicitly read roles_v2 decks and declared root-bank decks, so the differing root `decks.json` is not used.

## Identity results

| Mode | Coverage | Mismatches |
|---|---|---|
| P16 admitted -> workspace | 12 episodes, 15,949 boundaries | 0 |
| Recorded admitted -> workspace | 8 confirmations across all holdout opponent/seat cells | 0 |
| Random admitted -> workspace | 24 episodes, 7,198 boundaries, all 16 cards | 0 |
| C56 canonical-data control | 7 episodes, 2,900 boundaries | 0 |

P16, recorded and random baselines were recorded with explicit v5 `PYTHONPATH` and `CLASHER_ROOT`. Original P16 baseline is preserved; the new admitted baseline is byte-identical. Recorded checks require original outcome, both crowns, ticks and planner_calls. Workspace rows were actually replayed in disjoint groups, then checked against the full admitted baseline.

Random episodes cap at 1,800 ticks; twelve fixtures open both left Princess territories through normal tower death. Successful pocket placements total 118 for seat 0 and 113 for seat 1. C56 uses current C56 source with admitted data, since v5 predates C56 extensions. Saved old data reproduces the historical C56 baseline exactly; canonical data intentionally changes five episodes. The old baseline is retained.

The old P16 tool hardcoded admitted gamedata during workspace checks. It now loads the active runtime data and rejects missing episodes/branches or changed outcome metadata. Broader checks pin all non-meta data; the old-data negative control fails before replay. Rust receipt fingerprints now include gamedata. Run `bash reports/strategy_council_20260928/engine-speed/check_identity.sh LABEL` for all four modes.

## Rust re-verification

| Gate | Exact passing coverage |
|---|---|
| Full games | 64, 303,198 tick boundaries |
| Live imports | 512, 102,400 continuation ticks |
| Placements | 8,177, 523,328 paired ticks; both-seat pockets |
| Planner parity | 50 calls, 999 candidates, 159,840 continuation ticks |
| Full native-script games | 8, 42,950 ticks, 16,904 independent choices |
| Production native planner flag | All 8 original OQ games, 666 planner calls |

Zero unresolved mismatches. Fresh canonical games supply the planner corpus; old pickled card stats are not reused. Imports use the authorized reduced count of 512 versus historical 2,048. Step speed is 47.20x Python; maximum per-root clone mean is 6.73 us.

Canonical game 1 exposed a Rust omission at tick 5369: later combat lowers a Knight from 490 to 406 HP while arrows reserve 448 damage. Python revalidates pending-lethal status before Archer movement; Rust did not. A 13-line Rust guard restores parity. No Python engine behavior changed; removing only this guard in memory reproduces the previous Rust source hash. Failure/phase receipts and preservation proof are in `canonical/`. The new regression and all 37 existing Stage 1/2 regressions pass. Syntax, focused Ruff, Cargo formatting and scoped diff checks pass.

The release extension was rebuilt with `engine-rs/build.sh`; Cargo clean removed 116.9 MiB and retained the tested binary. All task-owned workers exited. Frozen runtimes, pilot, c56/data, srp-dagger and oracle-qualification were not edited.

## Files and receipts

Changes comprise `gamedata.json`; the P16 tool/new baseline; `broad_identity.py`, `check_identity.sh` and three new identity baselines; Rust `src/lib.rs`, `stage2.py`, `stage2_snapshots.py`, `test_stage3.py`, `test_stage3_rollouts.py`, new `test_canonical_data.py`, and rebuilt extension; this report, PROGRESS.md, canonical receipts/runners and the ready marker. Summary: `canonical/summary.json`. Re-run Rust gates with `canonical/restart_rust.sh` through `pilot/detach.sh`.
