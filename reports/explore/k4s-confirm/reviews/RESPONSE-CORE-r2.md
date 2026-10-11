# Response to SOL-REVIEW-CORE-r2 (APPROVE_WITH_FIXES)

Author: K4S prep worker (Opus), 2026-10-11.

| # | Fix |
|---|---|
| 2 (partial) / 8 | `check_games.py` validates an outcome-free identity/configuration projection of **every** game against an explicit expected spec per group, mode and arm. The spec covers seed, seed_index, population, cell, seat, sorted decks, deadline (None / 0.2 injected / 0.0 zero / arm budget), threads (1 injected, else 4), kernel (T1 `K2-anytime`; K4S per arm), arm, and the K4S settings (speed_cell, budget_ms, inference_scale with zero-mode overrides, scale_mode, default_source, s_default_rule, c_star). Placement (worker affinity = the driver receipt's cores[:width], nice ∈ {10,19}, SCHED_OTHER; K4S slot/slot_cores/attempt_dir) is checked against the driver receipt. No-deadline evidence must have no deadline rows but non-empty latency records. Any identity error fails, exit 1. `health.py --validate` (smoke) adds value and nullability checks: `frozen_action` null iff unscored; default_source/threads per arm; SD1 fields present iff SD1; per-game K4S metadata values and block_id/rotation. |
| 4 (partial) / 9 | New `source_binding.py`. `record` (before the first battery) snapshots every staged K4S overlay file (recursive) and the staged T1 tree. It requires the T1 tree to equal `t1-reference-expected.json`, generated from git ef4c073a (92 files, no missing or extra; `plan.json` compared after reversing only the job-path substitution; reference receipts included). `verify` (after games and STOP) requires an identical snapshot, all 11 driver receipts present, each naming the staged run.py/plan.json of its runtime, and every listed game hash matching. The receipt assembler requires `source-binding-end.json` `passed` and binds both binding files' SHAs. Checked on 05 against a real export: 92/92 files, 0 errors. |
| 7 (partial) / 10 | Crowns use `BattleState.get_crown_count(player)` (earned crowns), seat first. |
| 11 | `rebind.py verify` also requires inventory completeness: no unclassified file and no missing manifest entry. The manifest is rebuilt after all edits. |
| 12 | The eleven game slots are exactly the planned cores 0–54 (slot k = 5k..5k+4). `qualify_games.py` asserts a contiguous, 5-aligned slot within 0–54, the observed affinity, and SCHED_OTHER. QUALIFICATION.md is updated: cores, seeds 5/7, verifier tests on a checkout, the guard projection wording, and the source-binding steps. |
| 13 | `stop_test.py` requires positive evidence: the game was running when STOP was written, it exited nonzero with `InterruptedError: owned K4S stop`, it drained within 5 min, and 0 owned processes remain. It removes the STOP only if the bytes are its own token, preserving any external STOP. The assembler requires `interrupted_by_owned_stop` and `game_running_at_touch`, writes a diagnostic receipt, and exits 1 on FAIL, so the `set -e` driver fails. |
| 1 | QUALIFICATION.md wording is corrected ("byte-identical" → projection without `utc`). |

**Virtual-clock scope.** We agree with your bounded-equivalence characterisation. Observation, belief work, candidates,
sampling and root have zero simulated duration. Belief entry cutoffs are exercised; belief mid-suspension and sample
cutoffs crossed in virtual time are not, and are covered by the inherited belief battery and the 125-state collector
tests. QUALIFICATION.md and the receipts describe it this way.
