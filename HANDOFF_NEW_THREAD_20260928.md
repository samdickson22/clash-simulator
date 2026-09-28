# Clasher handoff — 2026-09-28

## Start here

Sam is clearing a very large chat thread. This file preserves the work state; writing it did not resume collection or training. Resume from this file, then read the fidelity worktree's PIPELINE_DESIGN.md and relevant tail of HANDOFF.md. Prefer durable receipts over old chat or narrative status.

- Main checkout: `/Users/sam/Desktop/code/clasher`, branch `codex-enabled-deck-parity-handoff`, HEAD `20cc861b`.
- Current simulator workspace: `/Users/sam/.codex/worktrees/clasher-simulator-fidelity-20260913`, branch `codex/simulator-fidelity-20260913`, HEAD `93fcace5`. Extensive uncommitted simulator, scripts, tests and reports matter. Do not reset, clean, or remove this worktree.
- Older research workspace: `/Users/sam/.codex/worktrees/clasher-event-policy`, branch `codex/hog26-event-policy-redesign`, HEAD `93fcace5`. Inactive since September 13 at last review, but uncommitted research/code/data still matter.
- Goal checked September 28: `usageLimited`, not complete, objective strong human-level Clash Royale play. Goal tooling reported 19,984,328 tokens used. Do not infer that a worker is running from a goal record or old session handle.
- Process check September 28: no reference qemu emulator, prospective collector, launcher or operational monitor running.
- Disk September 28: Data volume about 17 GiB available, 96% used. Recheck before allocating output.

## Objective and user preferences

Build a strong human-level bot, not a routine scripted bot. A simulator and public game-state representation are central. Train/evaluate across varied decks and card interactions, including procedural and professional-style decks, even if deployment initially uses Hog 2.6. Small harmless trajectory differences are acceptable; the target is mechanically credible play and preserved decision quality, not bit-exact swarm paths.

Public-state calibration and counterfactual-ranking gates precede policy training, PPO, self-play, search, promotion, reserved collection and paid compute. No paid compute without explicit allocation. Preserve frozen campaigns, their missing-case rules, source hashes and the paused scheduler. Passing opened development regressions is not fresh acceptance, official-client parity or demonstrated playing strength. The native reference is the pinned Null’s 15.535.86 runtime; do not claim official equivalence.

## Verified latest state: v7 failed, not live

`/Users/sam/.codex/worktrees/clasher-simulator-fidelity-20260913/reports/calibration_acceptance_20260922_v7/launch-state.json` currently says:

```json
{"stage":"campaign-terminal","exit_code":1,"training_authorized":false}
```

This supersedes the September 22 tail of fidelity/HANDOFF.md, which still describes live collection and obsolete session handles. Failure cause and frozen final evaluation have not been established in this handoff. Preserve the one attempted campaign; do not restart or replace missing cases to obtain a pass.

V7 was prepared for 64 families / 128 configurations across 16 base cards, unchanged v6 criteria. Frozen protocol SHA: `41c1034c3308eaa7c2ff3e5548ecc6062dc36b8de10a6ad41681ae527e287e85`. Generator seed 1515600; configuration seeds 1515601+, root seeds 1515800+, response seeds 1515900+. Inspect manifests and current hashes before any production edits; do not assume the old freeze is still intact.

## Latest completed development evidence

Evidence below was recorded September 22 in fidelity/HANDOFF.md and receipts under `reports/calibration_development_20260915/acceptance-v6-failure/`; tests were not rerun for this handoff.

- Fixed retained movement route after stun-to-attack transition. Family 028 five reacting branches matched native winner/HP margin; fixed a 112 HP discrepancy.
- Opened v6 recheck: 70 configurations / 35 families, zero bad families or clear regressions; 24 clear improvement families.
- Opened historical v5 recheck: 127 configurations / 64 families, zero bad families or clear regressions; 48 improvements.
- Opened historical v3 recheck: 86 configurations / 44 families, zero bad families or clear regressions; 27 improvements.
- Broad simulator suite: 1,380 tests passed across 101 files.
- End-horizon runner fix verified for 4 candidates across native/scalar (8 branches): finalized at tick 6001 without actions or decisions at/after 6001; no branch failure, source/attestation checks passed.
- Public policy control validation integrated: action dtype/range, finite float32 rewards, strict boolean masks/starts, observation shapes. 45 focused tests passed; refreshed actual-production public contract diagnostic. Additional vocabulary/control/horizon suite: 35 tests passed.
- These are development results, not authorization for training. Expert adapter, camera/perception transfer, recurrent policy, PPO/opponent league, validated search/distillation and independent human evaluation remain.

## Next actions when development is resumed

1. Read current AGENTS.md/AGENTS.local.md if present, git status, PIPELINE_DESIGN.md and durable v7 receipts. Preserve all dirty changes.
2. Diagnose v7 terminal failure from launcher/child logs and completion receipts. Separate operational failure from simulator mismatch. Run the original frozen evaluator with missing-case rules when appropriate; do not replace failed cases or silently reuse opened cases as fresh acceptance.
3. Only after preserving/evaluating that attempt, decide repairs and any new frozen campaign. Confirm disk headroom, source identity and native ownership first. The emulator was explicitly shut off by Sam; do not restart merely to inspect status or clean disk.
4. Continue through the documented gates toward training and independently measured playing strength. No credible completion percentage or human-strength claim is currently established.

## Disk cleanup history and what remains

User authorized removal of reproducible artifacts and bad/obsolete models, but preserve source, unique reference evidence and meaningful checkpoints. Recent coordinator requests focused only on native-reference cache. Do not interpret this handoff request as authorization to wipe reports/worktrees.

September 23 cleanup (prior thread record):
- Removed four generated event-policy `.f32` feature arrays, about 10.8 GiB; retained indexes/manifests/source datasets.
- Removed generated HUD images/arrays and derived image/array caches, plus intermediate numbered checkpoints while retaining first/latest, named and referenced models. Second pass recovered about 23.06 GiB at that time.
- Audits: fidelity `reports/cleanup_20260923/deleted-feature-arrays.json`, `output-deletion-authorized.json`, `output-deletion-complete.json`. Cleanup markers in main reports, datasets/derived and checkpoints explain missing artifacts.

September 25 native cache cleanup:
- Removed `~/.cache/clasher-native-reference/ndk-r27d-verified` (compiler only).
- Removed only `apk-decoded-1e505767/assets` and `apk-decoded-1e505767/lib`, after hashing all 9,845 files against the retained original publisher APK.
- Actual free-space increase measured 2.323 GiB; volume then had 18.869 GiB free. File allocation sum was larger; APFS sharing/concurrent writes prevent equating directory sizes with reclaimable space.
- Audit and restoration details: `~/.cache/clasher-native-reference/cleanup-20260925.json`.
- Restore decoded payloads by extracting assets/ and lib/ from retained `nulls-15.535.13-publisher-1e505767.apk` into the decoded directory. No download needed; minutes.
- Restore compiler by downloading URL from `ndk-download-receipt.json` to `android-ndk-r27d-darwin.zip`, then running retained `extract_verified_ndk.py`. It verifies archive SHA1 and safely restores the expected path. NDK r27d / 27.3.13750724; estimated 10–30 minutes depending on download.
- Kept SDK, reference AVD, original APK, patched staging directory, built/signed reference APK, built probe, signing keys, pinned runtime/update backups, decoded logic, captures/screenshots/logs. The compiler is not needed to run the already-built probe. The original decode directory is now intentionally partial.

September 24 inventory (STALE estimates; not current measurements): main datasets 35.53 GiB, fidelity reports 31.93, native cache 16.04 before September 25 cleanup, main .git 8.30, checkpoints 4.01, event-policy 4.17, main reports 2.56, main .venv 1.34, ~/.android 16.55, ~/.local/android-sdk 10.24. Allocated blocks deduplicated by inode within each root; no cross-root hardlinks detected. APFS clone sharing was not established. Fidelity reports are distinct native evidence, not simple copies of main datasets. Older campaigns remain regression inputs and must not be blanket-deleted. Three post-stop scalar output subsets totaled only 0.085 GiB; their larger parent directories contain reference inputs.

## Continuity files

- This handoff: `/Users/sam/Desktop/code/clasher/HANDOFF_NEW_THREAD_20260928.md`
- Detailed chronological engineering log: `/Users/sam/.codex/worktrees/clasher-simulator-fidelity-20260913/HANDOFF.md`
- Pipeline: `/Users/sam/.codex/worktrees/clasher-simulator-fidelity-20260913/PIPELINE_DESIGN.md`
- Latest campaign: fidelity `reports/calibration_acceptance_20260922_v7/`
- Repair/regression evidence: fidelity `reports/calibration_development_20260915/acceptance-v6-failure/`

No code changes, new simulation jobs, emulator startup, goal reset or deletion were performed while creating this handoff.
