# V7 recovery, September 28

V7 remains failed. The original collection completed 12 of 128 configurations and stopped in configuration 13, `74d4eefb...`, when scalar prefix replay rejected owner 0's Goblins at tick 1350. The child log contains an assertion failure, not a disk or emulator error. No collection, emulator, training, search, or paid job was started during recovery.

## Frozen evaluation and consolidation paths

The protocol still hashes to `41c1034c3308eaa7c2ff3e5548ecc6062dc36b8de10a6ad41681ae527e287e85`. All 307 pinned source files match preserved commit `b86e434ae1031443f4615c13292768d861bbc605`. They were extracted into `frozen-source/` and checked before running the original evaluator. Current main at `95feeb0e525ee1665360df6e28116b01c3436ecf` differs in 18 pinned files. See `source-recovery.json`.

`frozen-evaluation.json` is the original evaluator's result against the authoritative registry. It fails all 64 families because consolidation moved the capture directories: saved ledger paths no longer equal the paths returned by `Path.resolve()`. All 13 collected captures fail that binding check, and 115 configurations are missing. The original registry now records evaluation exposure for all 64 families. That exposure was not erased or reset.

To inspect surviving evidence, a separate SQLite copy of the pre-evaluation registry maps only v7 collection and branch output paths to their current resolved locations. `relocation-diagnostic-map.json` records all 141 mappings. No source, protocol, outcome, artifact hash, or authoritative ledger path was changed. The unchanged evaluator then ran against this diagnostic copy. Its raw output is `relocation-diagnostic-raw.json`; despite the evaluator's built-in role label, this is an opened-evidence diagnostic, not replacement acceptance.

The diagnostic admits all 12 complete configurations across six families. Their public-state checks and decision rankings pass, with four clear improvement families and no clear regression. The remaining 58 families fail because configuration 13 has no completed scalar artifact receipt and 115 configurations are absent. Criteria and missing-case rules are unchanged. Both evaluations report acceptance false and training unauthorized.

## Reproduced scalar failure

`replay_prefix.py` replays only the recorded prefix using local scalar code. `frozen-prefix.json` and `main-prefix.json` reproduce the rejection on both the frozen producer and current main. `main-prefix-towers.json` adds the saved native tower states.

At tick 1350, Goblins are in hand and the player has 2.03 elixir. The submitted position is `[14.5, 6.5]`, the owner's right Princess Tower center. Native has already lost that tower; scalar still has 128 HP. Scalar rejects the deployment in `Arena.can_deploy_at` because a living tower occupies it.

Recorded command-time comparisons for that tower:

| Tick | Native HP | Scalar HP |
|---|---:|---:|
| 450 | 1200 | 1200 |
| 570 | 43 | 296 |
| 1260 | 0 | 128 |
| 1350 | 0 | 128 |

This established an earlier combat divergence that changes placement legality. The subsequent investigation isolated it to movement bounds, as described below. Placement legality checks remain intact.

## Repair and verification

Scalar movement incorrectly reused the quarter-tile spawn margin. Native movement permits centers throughout the outer half-cell, from 0 to 17999 on x and 0 to 31999 on y. The Goblin stopped at scalar x17750 while native reached17789, changing pressure on nearby troops and their later targets. Retained native disassembly confirms the bounds; an in-memory counterfactual reproduced all 381 recorded phase positions in the investigated interaction. This preserves the Giant's final 253-damage hit. See `scalar-inspection/README.md` and the independent `native-inspection/README.md` review.

The shared scalar clamp and corresponding tensor movement and physical-knockback clamps now use those bounds. Spawn margins remain unchanged. Two obsolete tensor mass-method calls were replaced with the shared card-mass helper so actual scalar-to-tensor adapter tests could run. The ledger path checks now resolve both recorded and supplied existing directories, preserving family, protocol, root, candidate, and engine bindings. The authoritative ledger was not rewritten; read-only validation passes all 13 capture and 128 branch claims.

Validation completed:

- 1,644 simulator/public-contract tests passed across 124 files.
- 91 focused tensor/spawn/impulse tests passed, 15 skipped. These cover CPU movement phases, not full resident-engine or accelerator acceptance.
- New scalar and ledger regression tests fail for the expected reasons when only the original functions are restored in memory. All 10 new tensor cases fail with the old bounds.
- The formerly failing prefix accepts all 41 recorded commands through tick2610, including Goblins at1350.
- All 13 opened native captures completed 64 reacting scalar branches with unchanged producer source hashes. No bad decision families or clear regressions were found under the original decision criteria. All five branches for the formerly failed configuration match native winner and remaining tower-HP margin exactly.

These are opened development results. The original v7 attempt and evaluation remain failed, its 115 unstarted configurations remain missing, and no acceptance replacement was collected. Reports are under `opened-v7-scalar-recheck/`; test receipts are `broad-tests-complete.json`, `ledger-path-validation.json`, and `tensor-movement-validation.json`. The reference emulator remains off. No training, search, paid compute, commit, or push occurred.

## Direction after this repair

The user clarified that balance updates and mixed card levels are useful comparisons for acceptable simulator variation. A different tower outcome under identical replayed commands does not by itself demonstrate a bad learned strategy. A policy can observe the changed board and respond. Prioritize basic adaptive playing competence and investigate systematic ranking errors or repeatable simulation-only advantages. Do not expand this repair into an indefinite effort to match every close interaction. Any changed readiness criteria must be defined prospectively; v7's criteria and failure history remain intact.

Machine-readable result and artifact hashes: `diagnosis.json`.
