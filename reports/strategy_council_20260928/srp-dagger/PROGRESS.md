# SRP DAgger progress

<!-- it2-status -->
Iteration 2 COMPLETE. Diagnosis, 72-game collection, TBPTT fit, quick gate, full evaluation and final audit passed their execution checks. Quick wins 24/48 versus 23/48; full wins 87/192 versus 88/192. Full paired difference -0.52 percentage points, 95% interval [-8.85, +7.81], exact p=1. No demonstrated improvement; retain the initial student. No owned jobs remain. Reports: DIAGNOSIS.md and it2/RESULTS.md. Total footprint approximately 133 MiB. The current-status block below describes the original pilot.
<!-- /it2-status -->

<!-- current-status -->
Current receipt status: {"baseline_cells": 6, "canonical_ready": true, "complete": true, "final_cells": 6, "fit_complete": true, "fit_epoch": 3, "games": 40, "heavy_processes": 0, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5129064570602937, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": []}

Next: None. Canonical pilot and final receipt/curve review complete; no owned jobs remain.
<!-- /current-status -->

## Done

- Read workspace guidance, oracle qualification, Stage 0 engine report, collection,
  public sequence, fitting, evaluation and TBPTT source.
- Wrote DESIGN.md before coding. Disk available at start: 17 GiB.
- Found the shared fitter anchor uses the opposite KL direction and no prefix state.
  The local fit adapter will implement the requested direction with separate states.

## Running PIDs

None owned by this task yet.

## Next

Implement local collection/fit/eval adapters, validate a complete pilot game, then
collect 40 games, fit once and evaluate both checkpoints on 192 paired games each.

## Commands

Pending implementation. All long jobs will use pilot/detach.sh and nice -n 10.

## Implementation and first launch

- Done: collector, strict TOML, local fit loop, shared-eval adapter. Preflight passed
  workspace Stage 0 source hashes and exact actor/eval action, mask and state parity.
- Running: first complete collection game PID 259; initial evaluation launcher PID
  451, one worker. Both launched at nice 10; at most two heavy processes.
- Next: validate first complete NPZ and planner statistics, then launch remaining
  collection. Initial eval runs concurrently during first-game validation.
- Exact commands, from workspace root:
  `.venv/bin/python -B reports/strategy_council_20260928/srp-dagger/kit.py preflight`
  `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/first-game.log nice -n 10 .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/kit.py collect --start 0 --stop 1`
  `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/eval-initial.log nice -n 10 .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/evaluate.py --checkpoint reports/strategy_council_20260928/pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt --name srp-dagger-initial-s2902 --parallel 1 --trace-games 0`

## 2026-10-03T23:01:46Z

Coordinator PID 3362. Waiting on owned first-game PID 259; initial evaluation PID 451 remains active. Next: validation, collection, fit, final evaluation.

- Coordinator launch command:
  `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/coordinator.log .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/run.py --first-pid 259 --initial-pid 451`
- Added corpus invariant checks and exact paired statistical analysis before final
  evaluation. Asymmetric KL direction, zero-at-identity and finite-gradient checks
  passed. Complete-game checks will run when the first game finishes.

## 2026-10-03T23:06:16Z

Running verify-first, PID 5405. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/verify.py`

## 2026-10-03T23:06:26Z

Done: verify-first, PID 5405, exit 0.

## 2026-10-03T23:06:26Z

Running collect-01-19, PID 5442. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 1 --stop 20`

- First complete-game gate passed: 722 rows, 162 queried labels, 67 teacher waits, 3261 root values, zero rejected executions. 509.506 planner core-s; 155809 NPZ bytes. Source actor/eval parity and all corpus invariants passed.

## Recurrence readiness correction before any fit

The TBPTT README does not declare readiness and ends with A/B acceptance still open. Switched the local fit adapter to the existing full-prefix helper for both student and frozen anchor. No training has started. This supersedes earlier stored-state plans; collection and the fixed three-epoch loss protocol are unchanged.

- Receipt status 2026-10-03T23:17:40Z: {"baseline_cells": 2, "complete": false, "final_cells": 0, "fit_complete": false, "games": 2, "labels": 322, "planner_core_s": 991.6}

- Receipt status 2026-10-03T23:22:19Z: {"baseline_cells": 2, "complete": false, "final_cells": 0, "fit_complete": false, "games": 2, "heavy_processes": 2, "labels": 322, "planner_core_s": 991.6, "running_pids": [451, 3362, 5442, 9330]}

- Receipt status 2026-10-03T23:25:54Z: {"baseline_cells": 3, "complete": false, "final_cells": 0, "fit_complete": false, "games": 3, "heavy_processes": 2, "labels": 482, "planner_core_s": 1421.0, "running_pids": [451, 3362, 5442, 15593]}

- Historical-reference check: all 96 completed fresh holdout games share the reference checkpoint/config/seeds, but 66 trajectory records and 8 outcomes differ from human-prior-p16/evaluation/v7r4h-1M-s2902. Do not reuse that historical baseline. Both comparison arms use the workspace now. This is not a new full frozen-runtime parity certificate; cause was not diagnosed. Evidence: baseline-parity.json.

- The historical baseline has a DIFFERENT recorded gamedata hash. Checkpoint, model config, seed, sampling mode, interval and horizon match. The fresh paired evaluation avoids mixing these baselines; the gamedata mismatch alone is not a proven explanation of every trajectory difference.

- Receipt status 2026-10-03T23:33:08Z: {"baseline_cells": 3, "complete": false, "final_cells": 0, "fit_complete": false, "games": 4, "heavy_processes": 2, "labels": 617, "planner_core_s": 1818.5, "running_pids": [451, 3362, 5442, 15593]}

- Receipt status 2026-10-03T23:36:13Z: {"baseline_cells": 4, "complete": false, "final_cells": 0, "fit_complete": false, "games": 4, "heavy_processes": 2, "labels": 617, "planner_core_s": 1818.5, "running_pids": [451, 3362, 5442, 23584]}

- Receipt status 2026-10-03T23:38:55Z: {"baseline_cells": 4, "complete": false, "final_cells": 0, "fit_complete": false, "games": 5, "heavy_processes": 2, "labels": 735, "planner_core_s": 2140.7, "running_pids": [451, 3362, 5442, 23584]}

- Receipt status 2026-10-03T23:44:48Z: {"baseline_cells": 5, "complete": false, "final_cells": 0, "fit_complete": false, "games": 6, "heavy_processes": 2, "labels": 867, "planner_core_s": 2491.9, "running_pids": [451, 3362, 5442, 27539]}

## 2026-10-03T23:51:49Z

Done: initial evaluation, six cells x 32 games. Next: second collection worker.

## 2026-10-03T23:51:49Z

Running collect-20-39, PID 30997. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 20 --stop 40`

- Receipt status 2026-10-03T23:52:09Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 6, "heavy_processes": 1, "labels": 867, "planner_core_s": 2491.9, "running_pids": [3362, 5442]}

## 2026-10-03T23:54:48Z

Coordinator PID 33330. Waiting on owned first-game PID 259; initial evaluation PID 451 remains active. Next: validation, collection, fit, final evaluation.

## 2026-10-03T23:54:48Z

Adopt existing owned collector PID 5442; do not relaunch games 1-19.

## 2026-10-03T23:54:48Z

Done: initial evaluation, six cells x 32 games. Next: second collection worker.

## 2026-10-03T23:54:48Z

Running collect-20-39, PID 33333. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 20 --stop 40`

## Source review and coordinator recovery

- Done: all 192 baseline games completed. Source-guard failure in worker PID 30997
  occurred before game 20 began. The only changed file was c56_champions.py.
- Verified the preserved Stage 0 source matches the original hash. Its full diff
  is one `and e.card_stats is not None` guard in GoblinsteinTether.on_attach. This
  code is unreachable for the declared P16 decks. Allowed exactly that old/new
  hash pair in the local source guard; every other source hash remains pinned.
- Stopped only our waiting coordinator PID 3362 and replaced it with PID 33330.
  Existing collector PID 5442 was adopted without restarting or duplicating it.
  Second collector PID 33333 is now running games 20-39. Two heavy processes total.
  Initial evaluation PID 451 has exited. No foreign process was signalled.
- Next: finish both collection ranges, validate all games, fit once, final eval.
- Exact recovery command:
  `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/coordinator.log .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/run.py --first-pid 259 --initial-pid 451 --resume-collector-pid 5442`
- The first coordinator log is preserved as logs/coordinator-before-source-review.log.
  source-drift.json records both hashes. The replacement collection log records
  the successful new worker; the failed worker produced no game data.

- Receipt status 2026-10-03T23:55:48Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 7, "heavy_processes": 0, "labels": 1080, "planner_core_s": 3081.6, "running_pids": []}

- Receipt status 2026-10-03T23:56:01Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 7, "heavy_processes": 2, "labels": 1080, "planner_core_s": 3081.6, "running_pids": [5442, 33330, 33333]}

- Receipt status 2026-10-04T00:04:51Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 8, "heavy_processes": 2, "labels": 1248, "planner_core_s": 3555.6, "running_pids": [5442, 33330, 33333]}

- Receipt status 2026-10-04T00:09:52Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 9, "heavy_processes": 2, "labels": 1476, "planner_core_s": 4336.7, "running_pids": [5442, 33330, 33333]}

- Receipt status 2026-10-04T00:15:22Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 10, "heavy_processes": 2, "labels": 1679, "planner_core_s": 4896.7, "running_pids": [5442, 33330, 33333]}

- Added fitting and final-report guards for unreviewed source drift; fitting also
  checks the collected gamedata digest. All local scripts compile.
- PID status correction: the first status snapshot after coordinator replacement
  reported an empty PID list because its PID regex was overescaped. Corrected
  immediately. Collectors 5442 and 33333 were both active throughout that snapshot;
  no extra worker was launched. Current status at the top uses the corrected parser.

- Pre-fit review fixed the wait/play metric breakdown: ability follows wait in the action space, so wait is NUM_HAND_SLOTS * NUM_TILES, not the last logit. Collection, teacher labels and CE already used the correct IDs. No fit has run.

- The full-prefix fit now also reuses imitation.sequence_chunks with preserve_tails=True. Only the unsupervised terminal row is padded, and an assertion checks that each supervised label appears once. This replaces separate short-tail buckets and keeps the existing fitter minibatch convention. Held-out label/wait counts are checked against independently recorded game receipts before any optimizer step.

- Receipt status 2026-10-04T00:28:14Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 12, "heavy_processes": 2, "labels": 2170, "planner_core_s": 6381.6, "running_pids": [5442, 33330, 33333]}

- Receipt status 2026-10-04T00:49:01Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 13, "heavy_processes": 2, "labels": 2496, "planner_core_s": 7623.8, "running_pids": [5442, 33330, 33333]}

- Added process CPU measurement for the final evaluation launcher and its children. The final projection will distinguish planner-only cost, total collection cost, and an approximate full recipe with linearly scaled BC plus evaluation. Initial-evaluation CPU was not captured; any second evaluation estimate will explicitly use final-evaluation CPU as a proxy.

- The sole fit process will use two Torch threads, matching the existing human-prior fitter default and using the two CPU slots after both collectors finish. Collection and each evaluation worker remain single-threaded. Loss, split, LR and three-epoch protocol are unchanged. Thread count is recorded in the checkpoint and fit receipt.

- Receipt status 2026-10-04T01:05:43Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 14, "heavy_processes": 2, "labels": 2898, "planner_core_s": 8890.2, "running_pids": [5442, 33330, 33333]}

- Receipt status 2026-10-04T01:08:44Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 15, "heavy_processes": 2, "labels": 3211, "planner_core_s": 9844.8, "running_pids": [5442, 33330, 33333]}

- Receipt status 2026-10-04T01:13:45Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 16, "heavy_processes": 2, "labels": 3588, "planner_core_s": 11225.4, "running_pids": [5442, 33330, 33333]}

- Added teacher.json to distinguish the environment objective-v1 reward metadata from the teacher defense-v2 leaf potential plus elixir term. Saved root values are raw scores, not probabilities. The fitted checkpoint will record this manifest digest.

- Receipt status 2026-10-04T01:26:31Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 17, "heavy_processes": 2, "labels": 3798, "planner_core_s": 11810.5, "running_pids": [5442, 33330, 33333]}

- Final verification will replay the saved public inputs through the initial student for games 0 and 21, covering both seats and a long trajectory. It must reproduce every recorded stochastic student action with the original Torch seed. This forward-only check runs after both collectors exit, before the single fit.

## 2026-10-04T01:41:37Z

Coordinator PID 82538. Drain owned collectors at their next completed game, then schedule remaining games with two workers.

- Receipt status 2026-10-04T01:45:23Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 19, "heavy_processes": 2, "labels": 4339, "planner_core_s": 13601.3, "running_pids": [5442, 33333, 82538]}

## Balance the remaining collection

- Replaced only our waiting coordinator PID 33330 with boundary coordinator PID
  82538. Collectors 5442 and 33333 finish a complete game before receiving SIGTERM.
  The controller verifies each PID still has the exact owned collector command.
- Completed NPZ/JSON receipts are preserved. Remaining games will run as single-game
  commands in two concurrent slots, avoiding an idle worker after one fixed range
  finishes. A newly started, uncommitted game may lose a fraction of a second at
  the boundary; no completed game is repeated. Any incomplete publication is moved
  into interrupted/ before that uncompleted game is retried.
- The fixed collection and fit settings are unchanged. New workers check the TOML
  values against preflight as well as the reviewed source and checkpoint pins.
- Exact command:
  `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/coordinator.log .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/rebalance.py --first-pid 5442 --second-pid 33333`
- Original coordinator log preserved in logs/coordinator-before-rebalance.log.
  Next: finish collection, all corpus checks and saved-action replay, one fit, final
  paired evaluation and report. No foreign process was signalled.

## 2026-10-04T01:45:28Z

Stopped owned collector PID 33333 after complete game receipt(s) [26]. Preserved all completed data; no completed game will be repeated.

- Receipt status 2026-10-04T01:48:31Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 20, "heavy_processes": 1, "labels": 4536, "planner_core_s": 14124.1, "running_pids": [5442, 82538]}

## 2026-10-04T01:51:42Z

Stopped owned collector PID 5442 after complete game receipt(s) [13]. Preserved all completed data; no completed game will be repeated.

## 2026-10-04T01:51:42Z

Next: collect remaining game IDs [14, 15, 16, 17, 18, 19, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]; at most two concurrent processes.

## 2026-10-04T01:51:42Z

Running collect-game-014, PID 86263. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 14 --stop 15`

## 2026-10-04T01:51:42Z

Running collect-game-015, PID 86264. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 15 --stop 16`

## 2026-10-04T01:51:44Z

FAILED: RuntimeError('collect-game-014 PID 86263 failed, exit 1'). No completion receipt written.

- Receipt status 2026-10-04T01:53:50Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 21, "heavy_processes": 0, "labels": 4849, "planner_core_s": 15330.2, "running_pids": []}

## 2026-10-04T01:56:37Z

Coordinator PID 88451. Drain owned collectors at their next completed game, then schedule remaining games with two workers.

## 2026-10-04T01:56:37Z

Next: collect remaining game IDs [14, 15, 16, 17, 18, 19, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]; at most two concurrent processes.

## 2026-10-04T01:56:37Z

Running collect-game-014, PID 88454. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 14 --stop 15`

## 2026-10-04T01:56:37Z

Running collect-game-015, PID 88455. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 15 --stop 16`

- Receipt status 2026-10-04T01:57:52Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 21, "heavy_processes": 2, "labels": 4849, "planner_core_s": 15330.2, "running_pids": [88451, 88454, 88455]}

## Second source review and queue resume

- Both original collectors stopped after completed receipts, leaving 21 complete
  games. No incomplete publication was found. New workers 86263/86264 exited in
  the source guard before querying the teacher.
- The new mismatch is council_pilot.py. Verified the Stage 0 reference has the
  original preflight hash; its diff adds opt-in PPO recurrent config fields,
  training-runtime admission handling, and CLI validation/launch arguments.
  None is called by this collector, direct local BC fitter or shared eval runner.
  The model config builder, engine, actor inference and BC helpers are unchanged.
  Allowed only that exact reviewed hash pair in addition to the Goblinstein guard.
- The TBPTT README now reports 45 passing tests and completed 150k A/B runs, but
  explicitly leaves learning-quality acceptance unproven and does not declare
  readiness. Keep the full-prefix fallback.
- Resumed with no active collectors. Coordinator PID 88451 schedules only missing
  games in two slots. Failed guard logs and coordinator log were preserved with
  source-guard suffixes; source-drift-2.json records the exact hashes.
- Exact resume command:
  `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/coordinator.log .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/rebalance.py`

## 2026-10-04T02:14:55Z

Done: collect-game-015, PID 88455, exit 0.

## 2026-10-04T02:14:56Z

Running collect-game-016, PID 95124. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 16 --stop 17`

## 2026-10-04T02:16:13Z

Done: collect-game-014, PID 88454, exit 0.

## 2026-10-04T02:16:14Z

Running collect-game-017, PID 95832. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 17 --stop 18`

- Receipt status 2026-10-04T02:18:31Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 23, "heavy_processes": 2, "labels": 5455, "planner_core_s": 17408.1, "running_pids": [88451, 95124, 95832]}

## 2026-10-04T02:20:54Z

Done: collect-game-017, PID 95832, exit 0.

## 2026-10-04T02:20:55Z

Running collect-game-018, PID 97471. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 18 --stop 19`

## 2026-10-04T02:21:27Z

Done: collect-game-016, PID 95124, exit 0.

## 2026-10-04T02:21:28Z

Running collect-game-019, PID 97663. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 19 --stop 20`

- Receipt status 2026-10-04T02:21:42Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 25, "heavy_processes": 2, "labels": 5705, "planner_core_s": 18009.1, "running_pids": [88451, 97471, 97663]}

## 2026-10-04T02:39:49Z

Done: collect-game-018, PID 97471, exit 0.

## 2026-10-04T02:39:50Z

Running collect-game-027, PID 15706. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 27 --stop 28`

- Receipt status 2026-10-04T02:42:10Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 26, "heavy_processes": 2, "labels": 6007, "planner_core_s": 19054.4, "running_pids": [15706, 88451, 97663]}

## 2026-10-04T02:42:29Z

Done: collect-game-019, PID 97663, exit 0.

## 2026-10-04T02:42:31Z

Running collect-game-028, PID 16631. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 28 --stop 29`

- Receipt status 2026-10-04T02:43:25Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 27, "heavy_processes": 2, "labels": 6323, "planner_core_s": 20218.6, "running_pids": [15706, 16631, 88451]}

## 2026-10-04T02:47:41Z

Done: collect-game-027, PID 15706, exit 0.

## 2026-10-04T02:47:42Z

Running collect-game-029, PID 18974. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 29 --stop 30`

- Receipt status 2026-10-04T02:48:02Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 28, "heavy_processes": 2, "labels": 6526, "planner_core_s": 20651.3, "running_pids": [16631, 18974, 88451]}

## 2026-10-04T02:57:04Z

Done: collect-game-029, PID 18974, exit 0.

## 2026-10-04T02:57:05Z

Running collect-game-030, PID 25125. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 30 --stop 31`

- Receipt status 2026-10-04T02:59:30Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 29, "heavy_processes": 2, "labels": 6709, "planner_core_s": 21152.3, "running_pids": [16631, 25125, 88451]}

## 2026-10-04T03:05:43Z

Done: collect-game-028, PID 16631, exit 0.

## 2026-10-04T03:05:44Z

Running collect-game-031, PID 35399. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 31 --stop 32`

- Before fitting, replaced repeated frozen-anchor prefix replay with cached reference logits from the initial full-episode baseline pass. This is an exact constant-reference optimization for the fixed, unaugmented corpus; student recurrence still uses current-weight full-prefix reconstruction. The first loss-bearing batch checks initial KL against the cache is within 1e-4 before any optimizer step. No training has started and the loss/split/LR/epoch protocol is unchanged.

- Receipt status 2026-10-04T03:13:55Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 30, "heavy_processes": 2, "labels": 7036, "planner_core_s": 22339.9, "running_pids": [25125, 35399, 88451]}

## 2026-10-04T03:27:24Z

Done: collect-game-031, PID 35399, exit 0.

## 2026-10-04T03:27:25Z

Running collect-game-032, PID 57867. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 32 --stop 33`

## 2026-10-04T03:27:27Z

FAILED: RuntimeError('collect-game-032 PID 57867 failed, exit 1'). No completion receipt written.

- Receipt status 2026-10-04T03:28:02Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 31, "heavy_processes": 1, "labels": 7300, "planner_core_s": 23288.4, "running_pids": [25125]}

- Receipt status 2026-10-04T03:41:33Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 32, "heavy_processes": 0, "labels": 7678, "planner_core_s": 24682.7, "running_pids": []}

## 2026-10-04T03:42:38Z

Coordinator PID 75976. Drain owned collectors at their next completed game, then schedule remaining games with two workers.

## 2026-10-04T03:42:38Z

Next: collect remaining game IDs [32, 33, 34, 35, 36, 37, 38, 39]; at most two concurrent processes.

## 2026-10-04T03:42:38Z

Running collect-game-032, PID 75979. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 32 --stop 33`

## 2026-10-04T03:42:38Z

Running collect-game-033, PID 75980. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 33 --stop 34`

## SRP Python-path audit and final collection resume

- Game 32 stopped in the source guard before any teacher query. The last existing
  worker then finished game 30, leaving 32 complete games and no active collectors.
- The new script_rollout_planner.py change adds an opt-in Rust backend. This pilot
  stays on Python. audit_planner_source.py compares the new file with the exact
  preflight source preserved in Stage 0. After removing disabled native branches
  and unused native bookkeeping, all eight original method ASTs and module imports
  match. Receipt: planner-python-source-audit.json. No extra games were played.
- Allowed only this exact audited source hash. The collector now passes
  backend='python' when the planner exposes that parameter; the original Python-only
  signature remains supported. No native extension is imported or used by the pilot.
- Coordinator PID 75976 resumes only missing games 32-39 in two slots. Guard failure
  logs were preserved in logs/coordinator-source-guard-3.log and
  logs/collect-game-032-source-guard-failure.log; source-drift-3.json records hashes.
- Exact resume command:
  `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/coordinator.log .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/rebalance.py`
- Next: finish eight games, verify all corpora and saved actor replay, fit once,
  evaluate and report. The initial baseline remains 83/192 wins on the workspace.

- Receipt status 2026-10-04T03:45:37Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 32, "heavy_processes": 2, "labels": 7678, "planner_core_s": 24682.7, "running_pids": [75976, 75979, 75980]}

## 2026-10-04T03:51:24Z

Done: collect-game-033, PID 75980, exit 0.

## 2026-10-04T03:51:25Z

Running collect-game-034, PID 84742. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 34 --stop 35`

- Receipt status 2026-10-04T03:51:57Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 33, "heavy_processes": 2, "labels": 7812, "planner_core_s": 25063.7, "running_pids": [75976, 75979, 84742]}

## 2026-10-04T03:56:52Z

Done: collect-game-032, PID 75979, exit 0.

## 2026-10-04T03:56:53Z

Running collect-game-035, PID 90391. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 35 --stop 36`

## 2026-10-04T04:01:52Z

Done: collect-game-034, PID 84742, exit 0.

## 2026-10-04T04:01:53Z

Running collect-game-036, PID 95677. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 36 --stop 37`

## Native backend switch (user authorized)

- 35 Python games (000-034) completed and retained. Stopped owned controller 75976 and unfinished workers 90391 (035), 95677 (036) with SIGTERM after checking exact commands. No foreign process touched.
- Game 032 failure was the strict source-hash guard reacting to the new opt-in native planner code before collection began, not a gameplay failure. Exact Python AST preservation was verified and the retry completed.
- Verified the retained native extension, Rust sources and Python adapters against the successful Stage 3 manifest; native-runtime.json pins the bytes. No rebuild needed.
- Next: one complete native replay against saved Python game 000, then finish missing games with native labels, one fit, final paired evaluation.

- Native parity running PID 98714 (nice 10). Exact command: `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/native-parity.log nice -n 10 .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/native_parity.py`.

## 2026-10-04T04:05:10Z

Native parity passed: complete game 000, 721 decisions, 162 teacher labels; all public observations, masks, sampled student actions, mixed executed actions, labels and candidate IDs exactly equal. 1 root scores differ; retained as diagnostics, not training targets. QA replay excluded from the 40-game training corpus. See native-parity.json.

- Parity QA finished (PID 98714). Array-key ordering was corrected to set comparison; all action/public arrays are exact. One root value at decision 600 differs by 0.0002074162458643447 (1/3261 candidates); selected label unchanged. Native planner CPU 5.65762 s versus Python 509.50569 s for 162 calls. Sparse values remain diagnostic only; soft targets are deferred. No engine files were edited.
- Native is now the default for this kit and future collections. Existing games 000-034 remain untouched. Next: native games 035-039, then verification, one fit and final evaluation.

## 2026-10-04T04:05:31Z

Coordinator PID 2364. Drain owned collectors at their next completed game, then schedule remaining games with two workers.

## 2026-10-04T04:05:31Z

Next: collect remaining game IDs [35, 36, 37, 38, 39]; at most two concurrent processes.

## 2026-10-04T04:05:31Z

Running collect-game-035, PID 2367. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 35 --stop 36`

## 2026-10-04T04:05:31Z

Running collect-game-036, PID 2368. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 36 --stop 37`

## 2026-10-04T04:06:09Z

Done: collect-game-035, PID 2367, exit 0.

## 2026-10-04T04:06:10Z

Running collect-game-037, PID 3153. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 37 --stop 38`

## 2026-10-04T04:06:15Z

Done: collect-game-036, PID 2368, exit 0.

## 2026-10-04T04:06:16Z

Running collect-game-038, PID 3277. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 38 --stop 39`

## 2026-10-04T04:06:32Z

Done: collect-game-037, PID 3153, exit 0.

## 2026-10-04T04:06:33Z

Running collect-game-039, PID 3613. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 39 --stop 40`

## 2026-10-04T04:06:35Z

Done: collect-game-038, PID 3277, exit 0.

- Receipt status 2026-10-04T04:06:35Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 39, "heavy_processes": 1, "labels": 8965, "planner_core_s": 26172.1, "running_pids": [2364, 3613]}

- Resume controller PID 2364. Exact command: `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/coordinator.log .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/rebalance.py`. Child commands/PIDs follow in this log.
- Native projection will use native-only per-call timing and non-planner CPU per decision, normalized to the full pilot workload; Python collection CPU is retained separately as actual spent cost.

## 2026-10-04T04:06:57Z

Done: collect-game-039, PID 3613, exit 0.

## 2026-10-04T04:06:58Z

Running verify-all, PID 4075. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/verify.py`

## 2026-10-04T04:07:18Z

Done: verify-all, PID 4075, exit 0.

## 2026-10-04T04:07:18Z

Running fit, PID 4436. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/fit.py`

- Receipt status 2026-10-04T04:07:42Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": false, "games": 40, "heavy_processes": 1, "labels": 9202, "planner_core_s": 26179.1, "running_pids": [2364, 4436]}

- Collection complete: {"decisions": 37687, "games": 40, "labels": 9202, "native_core_s_per_call": 0.030884501501501474, "native_games": 5, "native_labels": 999, "native_planner_cpu_s": 30.85361699999997, "projected_300_native_collection_core_hours": 1.7545162585204248, "projected_300_native_planner_core_hours": 0.5920816308683678, "saved_actor_replays": [{"decisions": 721, "exact_actions": true, "game": 0}, {"decisions": 1201, "exact_actions": true, "game": 21}], "teacher_waits": 4183, "verification_games": 40}. Native projections exclude fit/eval and will be combined with measured fit/eval CPU in results.json.

- Fit baseline: 7,350 training labels and 1,852 held-out labels. Held-out CE 5.825464557622988, agreement 0.4524838012958963 (wait agreement 1.0, play agreement 0.0). First-batch KL(student || initial) 3.0764608638378377e-09 passed the full-prefix/cache parity gate. Fitting remains PID 4436, nice 10, two Torch threads; final checkpoint is fixed epoch 3.

- Epoch 1 complete: {"elapsed_s": 440.61157974996604, "epoch": 1, "heldout": {"agreement": 0.4519438444924406, "ce": 3.7863966383635352, "labels": 1852, "play_agreement": 0.0, "teacher_waits": 838, "wait_agreement": 0.9988066825775657}, "train": {"agreement": 0.4545578231292517, "ce": 3.7053543755148546, "labels": 7350, "play_agreement": 0.0, "teacher_waits": 3345, "wait_agreement": 0.9988041853512706}}. Epoch 2 running, same owned fit PID 4436.

- Epoch 2 complete: {"elapsed_s": 814.3350993748754, "epoch": 2, "heldout": {"agreement": 0.4519438444924406, "ce": 3.4761261291174343, "labels": 1852, "play_agreement": 0.0, "teacher_waits": 838, "wait_agreement": 0.9988066825775657}, "train": {"agreement": 0.4542857142857143, "ce": 3.4051472910407448, "labels": 7350, "play_agreement": 0.0, "teacher_waits": 3345, "wait_agreement": 0.9982062780269059}}. Final epoch 3 running, same fit PID 4436.

- Added the existing source/data pin checks before launching final evaluation, so concurrent unreviewed drift fails before expensive cells rather than only at final reporting. No shared evaluation code changed.

## 2026-10-04T04:27:19Z

Done: fit, PID 4436, exit 0.

## 2026-10-04T04:27:19Z

Running eval-final, PID 26203. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/evaluate.py --checkpoint /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/student.pt --name srp-dagger-it1-s2902 --parallel 2 --trace-games 0`

- Receipt status 2026-10-04T04:28:22Z: {"baseline_cells": 6, "complete": false, "final_cells": 0, "fit_complete": true, "games": 40, "heavy_processes": 2, "labels": 9202, "planner_core_s": 26179.1, "running_pids": [2364, 26203, 26209, 26210]}

- Single fit complete, PID 4436 exited 0, final checkpoint reload passed. Final held-out metrics: {"agreement": 0.4519438444924406, "ce": 3.4029856593253545, "labels": 1852, "play_agreement": 0.0, "teacher_waits": 838, "wait_agreement": 0.9988066825775657}. Fit wall seconds 1193.7543177918997, core-seconds 1484.488453.
- Final evaluation launcher PID 26203; two owned workers 26209 and 26210. Fresh seed base 770031, six cells x 32 games, output human-prior-p16/evaluation/srp-dagger-it1-s2902/. No further fit planned. Next: all six cells, paired test, curve figure, final receipt audit.

- report.py now writes RESULTS.md alongside machine-readable results.json and fit-curves.png. The report records the root-score discrepancy, unchanged held-out top-1 agreement, exact paired test, and native-only projection assumptions. Report syntax check passed; final values await six evaluation cells.

- Receipt status 2026-10-04T04:35:20Z: {"baseline_cells": 6, "complete": false, "final_cells": 2, "fit_complete": true, "games": 40, "heavy_processes": 2, "labels": 9202, "planner_core_s": 26179.1, "running_pids": [2364, 26203, 35482, 35483]}

- Final evaluation cells 1–2 completed, exit 0: holdout-balanced 7/32 versus initial 17/32; holdout-pressure 3/32 versus 8/32. Both have zero draws. This is preliminary regression evidence; finish the fixed six cells before the paired test. Current workers 35482/35483 (owned children of 26203), at most two heavy processes. No extra fit or tuning.

- Partial behavioral diagnostic: holdout-balanced noop-when-playable fell from about 94.5% to 63.1%, while wins fell 17→7. Added per-cell initial/final playable-wait rates to the result receipt. This does not identify a causal explanation. Remaining cells continue unchanged.

## Canonical-data restart required by coordinator

- Stopped owned controller 2364, eval launcher 26203 and workers 35482/35483 after checking their commands. No collector was active. No foreign jobs touched.
- All 40 games / 9,202 labels, fitted checkpoint and preliminary evaluations are INVALID for the canonical pilot: workspace data had Ice Spirit HP 90 (admitted 84), Goblin stab damage 47 (admitted 49). Both initial and final evals in this run selected workspace runtime and also used noncanonical data; regenerate both.
- Archived prior data, fit, pins, logs and owned shared evaluation directories under archive/noncanonical-3d99987c/ (26611305 bytes). No old games or metrics will enter the replacement pilot.
- No heavy processes remain owned by this task. Waiting for reports/strategy_council_20260928/GAMEDATA_CANONICAL_READY; it is currently absent.
- Next after marker: verify canonical data/native runtime, run one full Python-vs-native label equality check, collect 40 native games from scratch, fit once on those games, rerun both 192-game evaluations and report only canonical results.

- Prepared canonical.py to overlap one fresh-baseline worker with one parity/collection/fit job (maximum two heavy processes), then run final eval with two workers. native_parity.py now generates fresh Python and native QA copies outside the training corpus. Source/data guards require the canonical marker and verified receipt. Every new game records its gamedata SHA. Reports reject any non-native or mismatched-data training game. Initial/final evaluation CPU will be measured separately. Syntax checks passed. Still waiting for marker; no jobs launched.

- Readiness check 2026-10-04T04:50:18.224593+00:00: GAMEDATA_CANONICAL_READY absent. Workspace data digest has changed, but no launch is allowed until the marker exists. Native preflight now checks runtime pins too; no owned jobs active.

- Canonical task update (read-only engine-speed/PROGRESS.md): broader P16/random/C56 checks progressed; native canonical recertification exposed a movement pending-lethal recheck mismatch and is rebuilding/retesting a narrow Rust fix. Still no readiness marker, no owned jobs. New native pins must bind the post-fix verified extension rather than the old Stage 3 binary.

- canonical.py now prepares its own reproducible pins after the marker: compares all non-meta data with admitted v5, checks Ice Spirit HP 84/Goblin damage 49, verifies current Stage 2 whole-runtime fingerprint and both canonical Stage 3 source/binary maps, writes canonical-data.json/native-runtime.json/teacher.json, then runs preflight. It refuses reinitialization when preflight.json already exists. Native binary is reused only when the certified fingerprint matches. No launch yet; marker still absent.

- Added source/data pin checks at every game start and again before publishing its NPZ. This also covers both fresh parity games and prevents a mid-collection gamedata change from being silently accepted. No games started; still waiting for the canonical marker.

## 2026-10-04T05:53:23Z

Canonical data matches admitted non-meta data; digest 892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65. Post-fix native binary and source fingerprints match canonical Stage 2/3 receipts; no rebuild needed.

## 2026-10-04T05:53:23Z

Running preflight, PID 26713. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py preflight`

## 2026-10-04T05:53:33Z

Done: preflight, PID 26713, exit 0.

## 2026-10-04T05:53:33Z

Canonical coordinator PID 26710. Start fresh baseline (one worker) alongside parity, then native collection and the sole canonical fit.

## 2026-10-04T05:53:33Z

Running eval-initial, PID 26730. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/evaluate.py --checkpoint /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt --name srp-dagger-initial-s2902 --parallel 1 --trace-games 0`

## 2026-10-04T05:53:33Z

Running native-parity, PID 26731. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/native_parity.py`

- Canonical marker published 2026-10-04T05:51:20Z. Replacement coordinator PID 26710 launched. Exact command: `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/srp-dagger/logs/coordinator.log .venv/bin/python -B reports/strategy_council_20260928/srp-dagger/canonical.py`. Marker binds workspace data 892fbfa0, admitted data daa58b28, rebuilt native binary 552e200c, and the canonical report digest. Next: verify pins/preflight, one full backend parity game, all-native collection, one canonical fit and both fresh evals.

- Receipt status 2026-10-04T05:54:34Z: {"baseline_cells": 0, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 0, "heavy_processes": 2, "labels": 0, "native_parity_passed": false, "planner_core_s": 0, "running_pids": [26710, 26730, 26731, 26732]}

- Resume and fit aggregation now reject any game lacking the canonical gamedata digest or backend=native. This prevents the archived cohort or Python QA copy from entering the replacement fit even if a file is accidentally copied into games/. Collection behavior and the fixed fit recipe are unchanged.

- Receipt status 2026-10-04T06:00:48Z: {"baseline_cells": 1, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 0, "heavy_processes": 2, "labels": 0, "native_parity_passed": false, "planner_core_s": 0, "running_pids": [26710, 26730, 26731, 32806]}

## 2026-10-04T06:01:14Z

Native parity passed: complete game 000, 721 decisions, 192 teacher labels; all public observations, masks, sampled student actions, mixed executed actions, labels and candidate IDs exactly equal. 6 root scores differ; retained as diagnostics, not training targets. QA replay excluded from the 40-game training corpus. See native-parity.json.

## 2026-10-04T06:01:23Z

Done: native-parity, PID 26731, exit 0.

## 2026-10-04T06:01:23Z

Running collect-canonical, PID 34432. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/kit.py collect --start 0 --stop 40`

- Receipt status 2026-10-04T06:02:09Z: {"baseline_cells": 1, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 2, "heavy_processes": 2, "labels": 544, "native_parity_passed": true, "planner_core_s": 14.5, "running_pids": [26710, 26730, 32806, 34432]}

- Canonical full-game parity PASS: 192 teacher labels / 721 mixed-policy decisions; all public and action arrays exact, root-score differences 6. Python planner core-seconds 437.78729600000014, native 4.916827999999953. Both QA copies remain outside games/. Native-only collection now running PID 34432, alongside one initial-eval worker.

- Residual canonical score parity detail: {"root_candidates": 3846, "different_scores": 6, "max_abs_difference": 1.607587163035898e-05, "decision": 531, "tick": 2655, "chosen": 1935, "best_python_value": 0.0030734643257269555, "second_best_python_value": -0.004079290493640888}. All 192 selected labels and the full live trajectory still match. Retain scores as diagnostics only; no soft-target equivalence claim. Exact action IDs and both float scores are in native-parity.json.

- Receipt status 2026-10-04T06:06:21Z: {"baseline_cells": 2, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 15, "heavy_processes": 2, "labels": 3637, "native_parity_passed": true, "planner_core_s": 103.0, "running_pids": [26710, 26730, 34432, 40111]}

- Receipt status 2026-10-04T06:07:30Z: {"baseline_cells": 2, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 19, "heavy_processes": 2, "labels": 4519, "native_parity_passed": true, "planner_core_s": 127.4, "running_pids": [26710, 26730, 34432, 40111]}

- Receipt status 2026-10-04T06:07:57Z: {"baseline_cells": 2, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 20, "heavy_processes": 2, "labels": 4666, "native_parity_passed": true, "planner_core_s": 131.5, "running_pids": [26710, 26730, 34432, 40111]}

- Receipt status 2026-10-04T06:08:52Z: {"baseline_cells": 2, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 22, "heavy_processes": 2, "labels": 5154, "native_parity_passed": true, "planner_core_s": 144.8, "running_pids": [26710, 26730, 34432, 40111]}

- Receipt status 2026-10-04T06:10:20Z: {"baseline_cells": 2, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 26, "heavy_processes": 2, "labels": 6580, "native_parity_passed": true, "planner_core_s": 184.8, "running_pids": [26710, 26730, 34432, 40111]}

- Receipt status 2026-10-04T06:11:33Z: {"baseline_cells": 2, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 30, "heavy_processes": 2, "labels": 7415, "native_parity_passed": true, "planner_core_s": 208.3, "running_pids": [26710, 26730, 34432, 40111]}

- Receipt status 2026-10-04T06:12:41Z: {"baseline_cells": 3, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 35, "heavy_processes": 2, "labels": 8379, "native_parity_passed": true, "planner_core_s": 233.9, "running_pids": [26710, 26730, 34432, 46471]}

- Receipt status 2026-10-04T06:13:49Z: {"baseline_cells": 3, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 37, "heavy_processes": 2, "labels": 8935, "native_parity_passed": true, "planner_core_s": 250.8, "running_pids": [26710, 26730, 34432, 46471]}

## 2026-10-04T06:14:24Z

Done: collect-canonical, PID 34432, exit 0.

## 2026-10-04T06:14:24Z

Running verify-all, PID 49270. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/verify.py`

## 2026-10-04T06:14:34Z

Done: verify-all, PID 49270, exit 0.

## 2026-10-04T06:14:34Z

Running fit, PID 49332. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/fit.py`

- Receipt status 2026-10-04T06:15:25Z: {"baseline_cells": 3, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 40, "heavy_processes": 2, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 26730, 46471, 49332]}

- Canonical collection and verification complete: {"collection_cpu_s": 773.3234650000002, "decisions": 38936, "games": 40, "labels": 9565, "native_core_s_per_call": 0.02799245185572386, "native_games": 40, "planner_cpu_s": 267.7478019999987, "projected_300_collection_core_hours": 1.6110905520833336, "projected_300_planner_core_hours": 0.5578079208333308, "saved_actor_replays": [{"decisions": 721, "exact_actions": true, "game": 0}, {"decisions": 1201, "exact_actions": true, "game": 21}], "teacher_waits": 4229, "verification_games": 40}. Fit PID 49332 now runs with one baseline-eval worker; maximum two heavy processes. Initial held-out CE 5.9921086674, top-1 agreement 0.4275546518 on 1,967 labels. No noncanonical games entered aggregation.

- Receipt status 2026-10-04T06:20:08Z: {"baseline_cells": 4, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "games": 40, "heavy_processes": 2, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 26730, 49332, 53102]}

- Receipt status 2026-10-04T06:20:59Z: {"baseline_cells": 4, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "fit_epoch": 1, "games": 40, "heavy_processes": 2, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.884792555754234, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 26730, 49332, 53102]}

- Receipt status 2026-10-04T06:23:56Z: {"baseline_cells": 4, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": false, "fit_epoch": 2, "games": 40, "heavy_processes": 2, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5858876548809757, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 26730, 49332, 53102]}

## 2026-10-04T06:26:04Z

Done: fit, PID 49332, exit 0.

- Receipt status 2026-10-04T06:26:55Z: {"baseline_cells": 5, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": true, "fit_epoch": 3, "games": 40, "heavy_processes": 1, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5129064570602937, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 26730, 58981]}

- Single canonical fit completed and checkpoint reload passed: {"bytes": 54047044, "checkpoint_sha256": "2c54aaa109fc1a2ea4bd07cdd38a35498c2fa5eb67ec1ba431532620157176e2", "corpus_sha256": "28d6ec11a255b8b5af3b75355ea0ecde206108a3eac08d214fa08ff502069839", "cpu_s": 1242.4828949999999, "torch_threads": 2, "wall_s": 683.9221473750658}. Held-out CE 5.9921→3.5129; exact agreement 42.7555%→42.7046%, with zero exact play matches. Last fresh baseline cell remains active; final eval will start with two workers after it finishes.

## 2026-10-04T06:30:45Z

Done: eval-initial, PID 26730, exit 0.

## 2026-10-04T06:30:45Z

Running eval-final, PID 64975. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/evaluate.py --checkpoint /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/student.pt --name srp-dagger-it1-s2902 --parallel 2 --trace-games 0`

- Receipt status 2026-10-04T06:31:14Z: {"baseline_cells": 6, "canonical_ready": true, "complete": false, "final_cells": 0, "fit_complete": true, "fit_epoch": 3, "games": 40, "heavy_processes": 2, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5129064570602937, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 64975, 64987, 64988]}

- Canonical initial evaluation complete: [{"cell": "hog26-nominal-balanced", "games": 32, "wins": 18, "draws": 0}, {"cell": "hog26-nominal-defense", "games": 32, "wins": 14, "draws": 0}, {"cell": "hog26-nominal-pressure", "games": 32, "wins": 14, "draws": 0}, {"cell": "holdout-nominal-balanced", "games": 32, "wins": 17, "draws": 0}, {"cell": "holdout-nominal-defense", "games": 32, "wins": 15, "draws": 0}, {"cell": "holdout-nominal-pressure", "games": 32, "wins": 10, "draws": 0}], total 88/192 wins. Final evaluation launched by owned controller: launcher 64975, first workers 64987/64988. Exact command recorded above; shared output name srp-dagger-it1-s2902.
- Final report now records maximum absolute native/Python root-score discrepancy in addition to all six raw differences; hard-label parity passed, soft targets remain deferred.

- Receipt status 2026-10-04T06:37:31Z: {"baseline_cells": 6, "canonical_ready": true, "complete": false, "final_cells": 2, "fit_complete": true, "fit_epoch": 3, "games": 40, "heavy_processes": 2, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5129064570602937, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 64975, 70328, 70329]}

- Canonical final eval first two cells completed: [{"cell": "holdout-nominal-balanced", "final_wins": 6, "initial_wins": 17, "games": 32}, {"cell": "holdout-nominal-pressure", "final_wins": 4, "initial_wins": 10, "games": 32}]. Remaining four cells continue, no retuning.

- Receipt status 2026-10-04T06:42:41Z: {"baseline_cells": 6, "canonical_ready": true, "complete": false, "final_cells": 4, "fit_complete": true, "fit_epoch": 3, "games": 40, "heavy_processes": 2, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5129064570602937, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 64975, 76354, 76355]}

- Canonical final eval four cells complete: [{"cell": "hog26-nominal-balanced", "final_wins": 0, "initial_wins": 18, "games": 32}, {"cell": "holdout-nominal-balanced", "final_wins": 6, "initial_wins": 17, "games": 32}, {"cell": "holdout-nominal-defense", "final_wins": 5, "initial_wins": 15, "games": 32}, {"cell": "holdout-nominal-pressure", "final_wins": 4, "initial_wins": 10, "games": 32}]. Last two Hog26 cells are active under workers 76354/76355; at most two heavy processes.

- Receipt status 2026-10-04T06:47:46Z: {"baseline_cells": 6, "canonical_ready": true, "complete": false, "final_cells": 5, "fit_complete": true, "fit_epoch": 3, "games": 40, "heavy_processes": 1, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5129064570602937, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": [26710, 64975, 76355]}

## 2026-10-04T06:48:05Z

Done: eval-final, PID 64975, exit 0.

## 2026-10-04T06:48:05Z

Running report, PID 81895. Exact command: `nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/report.py`

## 2026-10-04T06:48:15Z

Done: report, PID 81895, exit 0.

## 2026-10-04T06:48:15Z

Done: canonical parity, 40 native games, one canonical fit, two fresh 192-game evaluations and paired report. No owned heavy jobs remain.

- Receipt status 2026-10-04T06:50:17Z: {"baseline_cells": 6, "canonical_ready": true, "complete": true, "final_cells": 6, "fit_complete": true, "fit_epoch": 3, "games": 40, "heavy_processes": 0, "heldout_agreement": 0.42704626334519574, "heldout_ce": 3.5129064570602937, "labels": 9565, "native_parity_passed": true, "planner_core_s": 267.7, "running_pids": []}

## Final canonical result and audit

- COMPLETE: 40 native games, 9,565 labels, 267.747802 planner core-seconds; one canonical fit and both fresh 192-game evaluations. Initial wins 88; fine-tuned wins 16. Score change -37.5 percentage points, paired 95% interval [-45.8333, -29.6875] points, exact two-sided sign-flip p=1.3766765505351941e-14 over 96 deck/seat pairs. This pilot regressed.
- Held-out agreement 42.7555%→42.7046%; CE 5.9921→3.5129; exact play agreement 0%. Curves visually reviewed.
- Projected 300 games: 0.5578 planner / 1.6111 collection core-hours; 4.7439 including scaled BC and one eval, 5.3631 with both initial/final evals. Linear CPU estimates, same recipe; archived and QA work excluded.
- Open issue: full-game backend labels/actions/public arrays match, but six root scores differ (max 1.6076e-5); no soft targets used. Privileged teacher and one-seed small pilot limit generalization.
- Final audit passed all game/checkpoint hashes, 12 eval-cell counts, local Python syntax, source guard and disk budget. final-audit.json records 54449975 bytes, including the invalid archive. No owned jobs remain. No additional iteration, fit or evaluation launched.
- Files owned by this task: srp-dagger/ scripts, TOML, design/readme/progress/results, checkpoint/corpora/curves/receipts and small archive; shared evaluation/srp-dagger-initial-s2902/ and evaluation/srp-dagger-it1-s2902/. No engine, frozen runtime, pilot, oracle, C56 or learner-TBPTT files were edited.

## Iteration 2 started

Read guidance, pilot code/data/results and current TBPTT README. Canonical SHA 892fbfa0 and source guard pass. Pilot artifacts total 53 MiB; disk free 20 GiB. No prior task jobs active. Plan: diagnose provenance, probabilities, behavior and action/tick alignment; collect 72 games with student candidates; one soft-target anchored TBPTT epoch; paired 48-game gate before any full evaluation. Existing pilot artifacts remain intact.

- 2026-10-04T06:59:37.832370+00:00 it2: Diagnostic worker PID 95242 and trace supervisor PID 94467 started through pilot/detach.sh at nice 10. Trace supervisor runs one heavy eval worker at a time. Config validated: 72 games; local design written. Pilot kit change is an optional planner hook plus sampled-action assignment.

- 2026-10-04T07:01:04.990012+00:00 it2: Pilot diagnostics complete: 3614/5336 play labels from random candidates, 1722 script and 4229 wait labels. All saved tick/action checks and eight live play-label replays passed. No pipeline bug found. Started collection range 0-35 after diagnostics exited; trace eval remains the other heavy worker.

- 2026-10-04T07:01:18.593036+00:00 it2: Collected game 000, 191 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:01:31.438586+00:00 it2: Collected game 001, 154 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:01:43.902986+00:00 it2: Collected game 002, 183 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:01:56.421352+00:00 it2: Collected game 003, 189 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:02:08.512510+00:00 it2: Collected game 004, 145 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:02:21.299484+00:00 it2: Collected game 005, 100 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:02:44.008195+00:00 it2: Collected game 006, 282 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:02:59.283018+00:00 it2: Collected game 007, 192 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:03:10.954244+00:00 it2: Collected game 008, 121 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:03:32.038626+00:00 it2: Collected game 009, 250 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:03:41.122233+00:00 it2: Iteration-2 coordinator PID 99906, adopting only owned trace supervisor 94467 and collector 97281.

- 2026-10-04T07:03:44.170750+00:00 it2: Collected game 010, 157 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:03:57.025584+00:00 it2: Collected game 011, 197 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:04:10.829779+00:00 it2: Collected game 012, 162 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:04:23.503383+00:00 it2: Collected game 013, 131 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:04:46.147676+00:00 it2: Collected game 014, 261 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:05:08.924466+00:00 it2: Collected game 015, 256 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:05:33.623124+00:00 it2: Collected game 016, 351 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:05:56.270192+00:00 it2: Collected game 017, 285 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:06:09.202985+00:00 it2: Collected game 018, 145 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:06:26.599691+00:00 it2: Traced diagnosis complete: {"initial": {"plays_per_game": 44.791666666666664, "wait_rate_when_playable": 0.9406667402583067, "elixir_at_play_mean": 5.634773488372092}, "it1": {"plays_per_game": 54.375, "wait_rate_when_playable": 0.6393034825870647, "elixir_at_play_mean": 2.5268333333333333}}; DIAGNOSIS.md written.

- 2026-10-04T07:06:26.606272+00:00 it2: Launched collect-36-71, owned PID 4093. Command: nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/it2/collect.py 36 72

- 2026-10-04T07:06:31.918753+00:00 it2: Collected game 019, 293 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:06:40.438019+00:00 it2: Collected game 036, 175 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:06:53.462354+00:00 it2: Collected game 037, 178 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:06:54.140793+00:00 it2: Collected game 020, 290 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:05.383357+00:00 it2: Collected game 038, 188 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:05.664236+00:00 it2: Collected game 021, 144 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:16.396986+00:00 it2: Collected game 039, 124 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:17.980989+00:00 it2: Collected game 022, 162 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:29.051684+00:00 it2: Collected game 040, 123 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:39.572682+00:00 it2: Collected game 023, 304 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:40.187397+00:00 it2: Collected game 041, 71 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:07:55.259679+00:00 it2: Collected game 042, 218 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:03.390130+00:00 it2: Collected game 024, 328 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:12.790362+00:00 it2: Collected game 043, 238 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:14.570580+00:00 it2: Collected game 025, 133 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:24.967697+00:00 it2: Collected game 044, 166 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:26.676444+00:00 it2: Collected game 026, 137 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:37.126075+00:00 it2: Collected game 045, 152 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:39.811606+00:00 it2: Collected game 027, 160 labels, student candidate present on every labelled row; native/canonical guards passed.

- Priority audit: initial detached supervisors inherited nice 10 and their nice-10 children initially ran at nice 20. Attempted to normalize only our coordinator PID 99906 and collector PID 4093 priorities; readback showed no change and Python confirmed permission denial. Retained their lower scheduling priority. All heavy workers have stayed at nice 10 or lower scheduling priority; no foreign process was touched.

- 2026-10-04T07:08:49.029171+00:00 it2: Collected game 046, 153 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:50.702459+00:00 it2: Collected game 028, 139 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:08:59.120423+00:00 it2: Collected game 047, 78 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:09:02.910889+00:00 it2: Collected game 029, 163 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:09:14.342064+00:00 it2: Collected game 048, 205 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:09:26.480031+00:00 it2: Collected game 049, 136 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:09:26.935610+00:00 it2: Collected game 030, 342 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:09:48.875138+00:00 it2: Collected game 050, 311 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:09:52.996744+00:00 it2: Collected game 031, 394 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:04.843923+00:00 it2: Collected game 032, 136 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:10.031059+00:00 it2: Collected game 051, 257 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:18.727112+00:00 it2: Collected game 033, 179 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:20.480539+00:00 it2: Collected game 052, 99 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:32.123153+00:00 it2: Collected game 053, 140 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:39.203484+00:00 it2: Collected game 034, 233 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:44.772311+00:00 it2: Collected game 054, 186 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:10:59.984405+00:00 it2: Collected game 035, 229 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:11:08.764900+00:00 it2: Collected game 055, 300 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:11:32.064969+00:00 it2: Collected game 056, 318 labels, student candidate present on every labelled row; native/canonical guards passed.

- Fit implementation review complete before training: candidate padding is masked, IDs are unique, each retained label occurs once, tau is fitted on training games only, full anchor logits use complete frozen recurrence, and KL covers all queried rows. Candidate-loss reference and outside-set gradient checks passed. Fitter releases per-game arrays after aggregation to limit RAM.

- 2026-10-04T07:11:52.496725+00:00 it2: Collected game 057, 259 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:12:15.447863+00:00 it2: Collected game 058, 271 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:12:39.845156+00:00 it2: Collected game 059, 345 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:12:52.475027+00:00 it2: Collected game 060, 207 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:13:04.681044+00:00 it2: Collected game 061, 177 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:13:16.186693+00:00 it2: Collected game 062, 120 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:13:27.564970+00:00 it2: Collected game 063, 126 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:13:47.160624+00:00 it2: Collected game 064, 230 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:13:58.770414+00:00 it2: Collected game 065, 167 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:14:11.289031+00:00 it2: Collected game 066, 168 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:14:23.161832+00:00 it2: Collected game 067, 131 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:14:36.232138+00:00 it2: Collected game 068, 162 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:14:55.921522+00:00 it2: Collected game 069, 248 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:15:08.372147+00:00 it2: Collected game 070, 135 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:15:21.063551+00:00 it2: Collected game 071, 169 labels, student candidate present on every labelled row; native/canonical guards passed.

- 2026-10-04T07:15:21.338384+00:00 it2: collect-36-71 PID 4093 exited 0.

- 2026-10-04T07:15:22.360136+00:00 it2: All 72 complete games pass pilot invariants; student candidate presence checked at publication. Starting the single fit.

- 2026-10-04T07:15:22.366110+00:00 it2: Launched fit, owned PID 12810. Command: nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/it2/fit_soft.py

- 2026-10-04T07:19:17.674797+00:00 it2: Fit completed: one TBPTT epoch, 206 updates; checkpoint reloaded; initial state parity delta 3.814697265625e-06; see it2/fit.json.

- 2026-10-04T07:19:17.944869+00:00 it2: fit PID 12810 exited 0.

- 2026-10-04T07:19:17.948553+00:00 it2: Launched quick-initial, owned PID 16742. Command: nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/it2/evaluate.py --checkpoint /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt --name quick-initial --games 8 --trace-games 0 --parallel 1 --seed 770031

- 2026-10-04T07:19:17.951414+00:00 it2: Launched quick-it2, owned PID 16743. Command: nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/it2/evaluate.py --checkpoint /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/it2/student.pt --name quick-it2 --games 8 --trace-games 0 --parallel 1 --seed 770031

- 2026-10-04T07:27:48.335069+00:00 it2: quick-initial PID 16742 exited 0.

- 2026-10-04T07:27:55.470230+00:00 it2: quick-it2 PID 16743 exited 0.

- 2026-10-04T07:27:55.577010+00:00 it2: Quick paired gate: {"cells": [{"cell": "holdout-nominal-balanced", "initial_wins": 3, "final_wins": 1, "games": 8, "score_difference": -0.25}, {"cell": "holdout-nominal-pressure", "initial_wins": 3, "final_wins": 2, "games": 8, "score_difference": -0.125}, {"cell": "holdout-nominal-defense", "initial_wins": 6, "final_wins": 6, "games": 8, "score_difference": 0.0}, {"cell": "hog26-nominal-balanced", "initial_wins": 5, "final_wins": 5, "games": 8, "score_difference": 0.0}, {"cell": "hog26-nominal-pressure", "initial_wins": 3, "final_wins": 4, "games": 8, "score_difference": 0.125}, {"cell": "hog26-nominal-defense", "initial_wins": 3, "final_wins": 6, "games": 8, "score_difference": 0.375}], "initial_wins": 23, "final_wins": 24, "games": 48, "score_difference": 0.020833333333333332, "paired_bootstrap_95ci": [-0.14583333333333334, 0.1875], "paired_exact_sign_flip_p": 1.0, "matchup_pairs": 24, "gate_passed": true}

- 2026-10-04T07:27:55.585220+00:00 it2: Launched full-it2, owned PID 25248. Command: nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python -B /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/it2/evaluate.py --checkpoint /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/srp-dagger/it2/student.pt --name full-it2 --games 32 --trace-games 0 --parallel 2 --seed 770031

- Collection summary finalized: 72 games, 63,484 decisions, 14,249 labels, 31,707 teacher executions, zero rejected actions; planner 368.995 CPU-s, total collection 1125.416 CPU-s. Target diagnostics: retained rows span 61 games; 25/267 have a terminal-win best leaf; sampled student is tied best on 48.27% of all queried rows. Reports are it2/collection-summary.json and target-diagnostics.json. Full evaluation remains active with two workers.

- Full evaluation: holdout-balanced and holdout-pressure complete, 64 games total. Both first-eight-game prefixes exactly match the quick iteration-2 receipts. Two workers continue with holdout-defense and hog26-balanced. No evaluation errors.

- Full evaluation: 128/192 games complete across all holdout styles and hog26-balanced. Every completed first-eight-game prefix exactly matches quick evaluation. Final two Hog26 cells are active; two heavy workers, no failed cells.

- 2026-10-04T07:45:56.492598+00:00 it2: full-it2 PID 25248 exited 0.

- 2026-10-04T07:45:56.603980+00:00 it2: Full paired evaluation: {"cells": [{"cell": "holdout-nominal-balanced", "initial_wins": 17, "final_wins": 16, "games": 32, "score_difference": -0.03125}, {"cell": "holdout-nominal-pressure", "initial_wins": 10, "final_wins": 15, "games": 32, "score_difference": 0.15625}, {"cell": "holdout-nominal-defense", "initial_wins": 15, "final_wins": 13, "games": 32, "score_difference": -0.0625}, {"cell": "hog26-nominal-balanced", "initial_wins": 18, "final_wins": 14, "games": 32, "score_difference": -0.125}, {"cell": "hog26-nominal-pressure", "initial_wins": 14, "final_wins": 16, "games": 32, "score_difference": 0.0625}, {"cell": "hog26-nominal-defense", "initial_wins": 14, "final_wins": 13, "games": 32, "score_difference": -0.03125}], "initial_wins": 88, "final_wins": 87, "games": 192, "score_difference": -0.005208333333333333, "paired_bootstrap_95ci": [-0.08854166666666667, 0.078125], "paired_exact_sign_flip_p": 1.0, "matchup_pairs": 96, "gate_passed": false}

- 2026-10-04T07:45:56.647361+00:00 it2: Iteration 2 complete. No owned heavy jobs remain. See it2/RESULTS.md and completion.json.

- Final artifact audit passed: 204 finite checkpoint tensors; original pilot checkpoint/corpus and initial checkpoint/config hashes preserved; 72 new corpus hashes valid; all six full/quick prefixes identical; source/native/canonical guards and gate ordering passed. All owned PIDs exited. Reviewed DIAGNOSIS.md and it2/RESULTS.md; corrected scheduling-priority wording and documented unused legacy checkpoint export metadata. No training or evaluation artifact was rewritten. Full result 87/192 versus 88/192, paired -0.5208 points, CI [-8.8542, +7.8125], exact p=1.0.
