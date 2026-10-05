# Clasher worktree consolidation — 2026-09-28

All three checkout states have been consolidated into local main at `/Users/sam/Desktop/code/clasher`. Only this checkout remains registered. No push was made.

## Preserved source history

- `cb2fed25`: original main checkout's uncommitted code, configs, tests, tools and tracked changes.
- `d02a24ba`: event-policy worktree's uncommitted experiments, handoffs and tracked report changes.
- `b86e434a`: fidelity worktree's simulator repairs, policy contracts, scripts, fixtures and tests.
- `647dc14d`: event-policy merge with main's additional training features.
- `2329a0b7`: fidelity merge.
- `0f6e8d2b`: merge of the former main branch history; its tree introduced no extra source changes.

All source snapshots are ancestors of main. Pre-consolidation base refs remain under `archive/pre-consolidation-20260928-*`. Other historical branches from previously removed worktrees were left intact.

## Conflict resolution

Preserved main's sampling, structured identity, causal spatial rehearsal and hazard helpers alongside event-policy's event accumulator, action-value head, teacher and temperature support. Retained fidelity public-policy v2 handling, movement and combat fixes. Removed duplicate definitions and CLI arguments introduced by textual merging. The native route cache now keys on building occupancy and flight status, and retains fidelity's effective approach range and scan order. The dependency lock was refreshed for the combined project requirements.

## Artifacts and cleanup

Original reports, datasets and checkpoints were renamed into `artifacts/worktree-data/<former-worktree-name>/`, preserving their directory inodes and hardlinks. They are excluded from Git as bulk local evidence. Unique artifact groups are exposed through links in main; same-name artifacts retain their separate source directories. A colliding untracked main vocabulary report was preserved under `reports/worktree_consolidation_20260928/main-untracked-collisions/` before merge.

Old worktree paths now contain only symlinks to those data directories. Their source/config links point back to main. This keeps recorded absolute paths usable without retaining duplicate source checkouts. Historical frozen code must be recovered from its commit if needed; current main is a new combined source identity.

An idle adb server with no connected devices held a worktree cwd; it was stopped before removal. Both extra worktree registrations and their merged task branches were removed. Unique data was not deleted. Checkout removal recovered about 0.10 GiB; this was consolidation, not a purge of the roughly 36 GiB of preserved experimental evidence.

## Validation

- Native, public-state and merged policy suite: 1,598 passed in 243.86 seconds.
- Additional training/inference and collector-interface tests: 56 passed.
- Route-cache tests: 9 passed, including changing building occupancy.
- Python compilation, focused F821/F811 checks, CLI help and dependency lock checks passed.
- These tests do not establish fresh calibration acceptance, training authorization or playing strength. V7 remains failed; follow the updated handoff before resuming development.

Receipts and logs: `reports/worktree_consolidation_20260928/`.
