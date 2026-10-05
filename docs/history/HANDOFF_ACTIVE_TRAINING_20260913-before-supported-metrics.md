# Active training continuation — September 13

This supersedes older execution snapshots. The persistent goal is ACTIVE; no model is accepted. Keep working toward the calibrated actor-visible Hog 2.6 outcome model. No search, PPO, policy updates, promotion, or reserved-data access is authorized by the current comparisons.

## Current process

- Worktree: /Users/sam/.codex/worktrees/clasher-event-policy
- Branch: codex/hog26-event-policy-redesign; preserve the dirty tree.
- Active supervisor: PID82765, unified exec session25172.
- Command: experiments/hog26_overlap_margin/supervise.py --mode run
- It fits24 regressors, runs two exact seed reviews concurrently, then scientific closeout.
- Live state: /Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json
- All eight bundles and both exact reviews are complete. Scientific worker10558 is active under supervisor82765. Verify live state rather than relying on these PIDs.
- Do not duplicate or pause the supervisor. Its signal cleanup stops owned workers; no old handoff/paused-parent procedure is needed.
- All older phase, diagnostic, and review processes have finished. No older paused parent remains.

## Frozen current authority

- Plan: reports/hog26_overlap_margin_plan_20260913.json
- SHA256: 9b3b1b3318d1f60c2835f13593008700110e3fc80d149cddb45a0becaf5f741c
- All13 Python files in experiments/hog26_overlap_margin are immutable. Do not edit or add Python there.
- Full-size memory proof passed:1653689/1318176/240204 largest expert rows,2465152 inference rows,10104094720 worker peak RSS.
- Two fixed seeds1279501/1279502, four whole-family folds, three fresh overlapping experts.
- Same814 public features and native HGB absolute residual learner. Gate centers1/6,1/2,5/6; original margin weights multiplied by the public gate and normalized per expert.
- Clip each expert terminal-margin prediction to[-1,1], then take its convex public-clock combination.
- WDL stays the matching unchanged globals checkpoint.
- Configuration was fixed before reading transfer feedback in reports/hog26_overlap_margin_training_hypothesis_20260913.json.
- WDL-statistic reuse passed five tests, all240 real reference-dictionary identities, and changed-margin full-bootstrap equality on22415 late states and325 late representatives.
- Output: reports/hog26_overlap_margin_20260913

## After current comparison finishes successfully

1. Inspect complete.json, exact reviews and scientific-review.json; retain every failing/empty/unsupported slice.
2. Run the pinned overlap boundary audit:
   experiments/hog26_overlap_boundary_audit/supervise.py
   Both Python files are frozen. Pin SHA19763da7808795b708107f72bcdcfc7b980ccc60e8bf3586da6362a5f7212cfa.
   It separates gate and expert contributions at three centers and two old boundaries; it is not action ranking.
3. Run the pinned online encoder audit:
   experiments/hog26_online_value_features/supervise.py --mode audit
   All five Python files are frozen. Pin SHA8d7b7675c3f599edb8d2ea283c68db369a75213c1cee61158c5a1a2e25b70a63.
   Four tests passed; real-game audit is still pending on16 fixed training games.
   This validates a20-frame, cloneable,814-feature public encoder. It is not wired to any live policy.
4. Record complete results before any separately frozen next experiment. Do not alter the existing plans based on opened diagnostic feedback.

Each audit acquires the shared comparison.lock. Wait for the previous supervisor to exit and release it.

## Most important completed findings

- Corpus:6144 complete games,3072 paired scenarios,2465152 rows;4684losses/1460wins/0draws.
- Expanded tree late representative MAE:0.0274 baseline to0.0171–0.0173.
- Public entity history improved early behavior AUC0.9475→0.9591 but worsened early outcome MAE0.2091→0.2107. Preserve that failed result.
- Hard-phase experts improved early/middle margins and reached late representative MAE0.01585856. Late seed predictions are identical, not independent replication.
- Hard-phase early bridge regression shrank, but all-state points still trailed current margin by about0.008–0.0095 with intervals crossing zero.
- A supported late balanced seat1 representative slice regressed versus one previous tree.
- Hard switching caused about0.057 mean same-state change at the first boundary.
- All eight hard-phase transfer diagnostics and exact18-artifact review completed. Overall gains carried, but two supported spell-control slices regressed versus previous trees.
- The opened late diagnostic has21games/16clusters/one win-containing cluster. It cannot authorize fitting or acceptance.
- Four late training phase/seat/style cells still lack support. Natural-draw calibration is unmeasured.
- No playing win-rate improvement is claimed; the behavior policy is unchanged.

Read reports/hog26_training_progress_20260913.md for a short snapshot and reports/hog26_protocol_reassessment_20260908.md for the full chronology.

## Environments

The current function-store prefixes are overlapEnv, overlapBoundaryEnv, onlineValueEnv. For a fresh context, use these exact command prefixes (append the script and arguments):

Overlap:
```sh
PYTHONPATH=experiments/hog26_overlap_margin:experiments/hog26_phase_value_eval:experiments/hog26_phase_margin:experiments/hog26_threaded_value_fit:experiments/hog26_expanded_value_eval:experiments/hog26_scaling_review:experiments/hog26_scaling_eval:experiments/hog26_seed_transfer:experiments/hog26_expanded_value_fit:experiments/hog26_expanded_tree_value:experiments/hog26_expanded_corpus:experiments/hog26_streamed_features:experiments/hog26_parallel_expansion:experiments/hog26_parallel_collection_probe:experiments/hog26_training_expansion:experiments/hog26_data_scaling:experiments/hog26_terminal_auxiliary:experiments/hog26_semantic_margin:experiments/hog26_public_semantics:experiments/hog26_residual_margin:experiments/hog26_scalar_pilot:src:. /Users/sam/Desktop/code/clasher/.venv/bin/python
```

Boundary:
```sh
PYTHONPATH=experiments/hog26_overlap_boundary_audit:experiments/hog26_overlap_margin:experiments/hog26_phase_value_eval:experiments/hog26_phase_margin:experiments/hog26_threaded_value_fit:experiments/hog26_expanded_value_eval:experiments/hog26_scaling_review:experiments/hog26_scaling_eval:experiments/hog26_seed_transfer:experiments/hog26_expanded_value_fit:experiments/hog26_expanded_tree_value:experiments/hog26_expanded_corpus:experiments/hog26_streamed_features:experiments/hog26_parallel_expansion:experiments/hog26_parallel_collection_probe:experiments/hog26_training_expansion:experiments/hog26_data_scaling:experiments/hog26_terminal_auxiliary:experiments/hog26_semantic_margin:experiments/hog26_public_semantics:experiments/hog26_residual_margin:experiments/hog26_scalar_pilot:src:. /Users/sam/Desktop/code/clasher/.venv/bin/python
```

Online encoder:
```sh
PYTHONPATH=experiments/hog26_online_value_features:experiments/hog26_overlap_margin:experiments/hog26_phase_value_eval:experiments/hog26_phase_margin:experiments/hog26_threaded_value_fit:experiments/hog26_expanded_value_eval:experiments/hog26_scaling_review:experiments/hog26_scaling_eval:experiments/hog26_seed_transfer:experiments/hog26_expanded_value_fit:experiments/hog26_expanded_tree_value:experiments/hog26_expanded_corpus:experiments/hog26_streamed_features:experiments/hog26_parallel_expansion:experiments/hog26_parallel_collection_probe:experiments/hog26_training_expansion:experiments/hog26_data_scaling:experiments/hog26_terminal_auxiliary:experiments/hog26_semantic_margin:experiments/hog26_public_semantics:experiments/hog26_residual_margin:experiments/hog26_scalar_pilot:src:. /Users/sam/Desktop/code/clasher/.venv/bin/python
```

All commands run from the worktree. The Python/Ruff/pytest environment is /Users/sam/Desktop/code/clasher/.venv. Keep source, datasets, checkpoints, and reports from every previous lineage. Do not modify src/clasher, scripts, or frozen experiment directories. No subagents are authorized. Do not commit, reset, clean, stash, merge, push, or disturb unrelated work.

The ten-minute continuation scheduler targets goal thread01a09804-13c8-77f1-a297-cdea4701e0c5. No memory files were edited. Earlier memory guidance was used (MEMORY.md:83; rollout01a0827e-f864-7101-a29c-6e79553f8f1d); a future final response must follow memory citation rules.

