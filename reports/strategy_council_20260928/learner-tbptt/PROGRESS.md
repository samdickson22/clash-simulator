# Learner TBPTT progress

## Final state
- Implementation and requested experiments finished; no owned training or supervisor jobs remain active.
- Final suite: 45 passed in 72.57s. Default PPO byte identity, BC payload identity, whole-episode equivalence, reset gradient isolation and 256-token minibatches pass.
- Corrected benchmarks, full/T32/T64: 50.72/10.61/11.29 update ms per decision; 13.43/40.89/36.70 end-to-end decisions/s. Speedups 3.04x T32 and 2.73x T64; <=2 ms update target missed.
- Both final A/B runs completed 150000 decisions. Full: 26 wins/174 losses, 12.99 decisions/s. T64: 30 wins/146 losses, 36.56 decisions/s. Both checkpoints reload with finite model/optimizer and nonzero actor/critic changes.
- Numerical sanity passes; learning-quality acceptance remains unproven. Early-to-late training win rates declined in both, despite better critic fit. No superiority claim.
- README.md contains design, flags, scope, results, final assessment and reviewed curves. results/final-validation.json and results/final-checkpoints.json contain verification receipts.
- Only one final checkpoint per A/B remains. Owned outputs are about 80 MiB, below 1 GiB. Benchmark checkpoints, duplicate scratch checkpoints and owned Python caches removed.
- Production learner files match the tested fixed source snapshot; model.py is unchanged. No foreign process or forbidden directory was modified.

## Earlier history

## Done
- Read CLAUDE.md, AGENTS.md, environments/AGENTS.md; AGENTS.local.md absent.
- Read engine-speed profile and recurrent collector/update/BC paths.
- Preserved pre-edit copies of four already-dirty source files in before/.
- The critic is a separate feed-forward encoder, with no recurrent critic state.

## Running PIDs
None owned yet. Existing pilot, extraction and evaluation processes are untouched.

## Next
Capture unchanged deterministic PPO reference, implement opt-in collection/update and BC state cache, test, benchmark, and run 150k-decision A/B.

## Commands
Initial inspection used sed/rg/cat and read-only git status. Source preservation:
`cp src/clasher/rl/{train_recurrent,imitation,model,parallel_rollout}.py reports/strategy_council_20260928/learner-tbptt/before/`

## Step 2: opt-in implementation and initial checks
Done: stored-state capture in all three collectors and worker transport; chunk PPO with exact tail coverage and no-grad burn-in; BC epoch cache; unchanged model.py. Default PPO/BC references were captured before editing their respective files. PPO tensor/optimizer/RNG/args and normalized torch serialization bytes match. Initial tests: 7 passed in 6.88s.
The first test attempt used a second random environment reset that exceeded its tiny 32-entity fixture capacity. Fixed the fixture to recreate the original seeded environment. No engine code changed.

Running: PID 16991, full-prefix benchmark, nice 10.
Command: `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/learner-tbptt/logs/bench-full.log nice -n 10 .venv/bin/python reports/strategy_council_20260928/learner-tbptt/run_experiment.py reports/strategy_council_20260928/learner-tbptt/configs/bench-full.toml`
Tests: `nice -n 10 .venv/bin/python -m pytest -q tests/test_recurrent_tbptt.py` (logs/tests-second.log).
Next: BC cache equivalence/reset tests, full collector regressions, stored-state benchmarks, 150k A/B. Benchmarks use equal loss-bearing tokens per minibatch: full 2x128, T32 8x32, T64 4x64.

## Step 3: regressions and timing
Done: 40 tests passed in 94.02s, including existing PPO contract, learner inference, rollout transport and resume RNG suites. BC whole-episode fit and cached-state refresh checks pass. Added a strict standalone TOML recurrent config shared by both CLIs. Opt-in learner crops trailing packed entity padding, including burn-in; default is untouched.
Command: `nice -n 10 .venv/bin/python -m pytest -q tests/test_recurrent_tbptt.py tests/test_council_ppo_contract.py tests/test_pilot_learner_inference.py tests/test_council_rollout_transport.py tests/test_train_resume_rng.py`
Full-prefix benchmark update 1: 29.70 ms/decision, 19.06 decisions/s. Update 2: 50.60 ms/decision, 13.08 decisions/s. Partial measurements, not completion evidence.
Running: full benchmark PID 16991; T32 benchmark launched via detach.sh (PID in tool receipt and runs/bench-t32/provenance.json). No other owned heavy process.
T32 command: `reports/strategy_council_20260928/pilot/detach.sh reports/strategy_council_20260928/learner-tbptt/logs/bench-t32.log nice -n 10 .venv/bin/python reports/strategy_council_20260928/learner-tbptt/run_experiment.py reports/strategy_council_20260928/learner-tbptt/configs/bench-t32.toml`
Next: final tests of TOML and cropped paths, T64 benchmark and long A/B.

## Resume: process and receipt audit
Read progress first, then ps: old full PID 16991 and T32 runner are absent. Both completion.json receipts report completed=true, 4096 decisions. Full: 56.9524 update ms/decision, 11.3996 decisions/s; T32: 19.2341, 20.2754. Existing whole-episode PPO loss/gradient and BC fit equivalence tests cover no-burn full chunks. TOML stored-state config parsed successfully. Disk 17 GiB free, own outputs 65 MiB. No foreign processes touched. Next: T64 benchmark plus full A/B, then stored A/B; at most two heavy processes, nice 10, detach.sh.
Launched T64 benchmark and full A/B with validated configs; exact PIDs in provenance.json and launch receipts. Full A/B uses 150000 decisions, same 8-env/public-script recipe, two epochs, 256 nominal loss tokens/minibatch; max 24h. Only final.pt is written.
Running PIDs: T64 benchmark 46191; full A/B 46211. Added strict-TOML/override and padding-hole tests; strengthened PPO equivalence to include a terminal at the end of the short episode. Test execution waits for a heavy-process slot.
Wrote README design, flags, test scope, measurement limitations and file ownership. Measured results remain explicitly pending.
T64 completed 4096 decisions: 12.5051 update ms/decision, 33.8619 decisions/s, 121.11s. Speedup versus original full receipt 2.9704x; ≤2 ms target missed. T64 PID exited; resumed regression suite launched nice 10 into logs/tests-resumed.log, second heavy slot alongside full A/B PID 46211.
T64 final receipt recorded; generated README benchmark table and partial A/B summary via summarize.py. Tests still running, new padding test failed pending traceback; default identity/equivalence tests passed so far. Removed only own completed benchmark final.pt files and duplicate results/bc.pt/control.pt scratch; preserved reference .pt files. model.py cmp and focused git diff --check pass.
Resumed suite: 41 passed, 1 failed in 85.29s. Failure was the newly added crop test invalidating masked entity level metadata; corrected the test to clear levels/confidence. Reran all 11 TBPTT tests: 11 passed in 5.21s. Combined coverage: all 42 tests pass, default PPO byte serialization identity and BC payload identity, terminal whole-episode PPO loss/gradient equivalence and BC fit equivalence. No production fix was needed. Stored A/B launched next; exact PID in launch receipt and runs/ab-t64/provenance.json. Both A/B runs retain only final checkpoint, no intermediate saves.
Source provenance audit found engine source drift across original benchmarks and entities.py drift between A/B launches. Stopped only owned A/B PIDs 46211 and 53889 after ps ownership check, preserving partial monitors and interrupted.json. Copied current src/clasher to own runtime-src/clasher, verified full .py hash equality after copying; source manifest results/runtime-source-sha256.json. Restart both A/B using identical pinned source. Original benchmark table is confounded by source drift as well as contention; no clean isolated speedup claim.
Pinned A/B PIDs: full 54561, T64 54580, both nice 10 and detached. run_experiment.py now hashes the actually imported source root. summarize.py now follows the pinned A/B labels.
2026-10-03T21:44:04.199466+00:00 Supervisor PID 55239: pinned A/B source and checkpoint hashes match. At most two experiment processes.
2026-10-03T21:44:04.200775+00:00 ab-full-pinned: 1024 decisions, completed=False
2026-10-03T21:44:04.218161+00:00 ab-t64-pinned: 2048 decisions, completed=False
Detached lightweight supervisor PID 55239, logs/supervisor.log, finish_when_done.py. It checks the two owned A/B processes every 30s, records 10k milestones, derives matching first-4096 full/T64 benchmark receipts, starts a pinned T32 benchmark only after a completed A/B process exits, then generates summary/plot after all complete. Final model/curve review remains manual. Own footprint ~14 MiB after cleanup; only two heavy processes.
2026-10-03T21:45:34.344684+00:00 Pinned benchmark prefix saved: bench-t64-pinned: {'completed': True, 'decisions': 4096, 'updates': 4, 'derived_from': 'ab-t64-pinned: first 4096 decisions', 'update_ms_per_decision': 13.96132552099516, 'decisions_per_second': 29.054941700440292}
2026-10-03T21:48:04.521195+00:00 Pinned benchmark prefix saved: bench-full-pinned: {'completed': True, 'decisions': 4096, 'updates': 4, 'derived_from': 'ab-full-pinned: first 4096 decisions', 'update_ms_per_decision': 50.720035420965814, 'decisions_per_second': 13.429623462104965}
2026-10-03T21:48:34.548330+00:00 ab-t64-pinned: 10240 decisions, completed=False
2026-10-03T21:54:05.096609+00:00 ab-t64-pinned: 20480 decisions, completed=False
2026-10-03T21:59:05.707522+00:00 ab-full-pinned: 10240 decisions, completed=False
2026-10-03T21:59:35.763331+00:00 ab-t64-pinned: 31744 decisions, completed=False
2026-10-03T22:04:36.303846+00:00 ab-t64-pinned: 40960 decisions, completed=False
2026-10-03T22:09:06.675485+00:00 ab-t64-pinned: 50176 decisions, completed=False
2026-10-03T22:14:37.239506+00:00 ab-t64-pinned: 60416 decisions, completed=False
2026-10-03T22:15:37.302640+00:00 ab-full-pinned: 20480 decisions, completed=False
2026-10-03T22:19:37.651108+00:00 ab-t64-pinned: 70656 decisions, completed=False
2026-10-03T22:25:08.072317+00:00 ab-t64-pinned: 80896 decisions, completed=False

## Sanity finding and targeted correction
At ~80k stored-state decisions, wins stalled at 18/99 games; 50k-75k window won 2/34, while full-prefix at 25k won 9/24. Found an actual minibatch weighting issue: splitting at resets produced short terminal-tail optimizer minibatches with full step weight. Changed only stored-state chunk construction to fixed temporal windows; existing model episode-start masks reset state and its gradient inside windows. Added reset state/gradient isolation test and updated coverage test. Default path unchanged. New tests pending heavy slot. Existing full and first T64 runs continue as comparison evidence. Stopped owned lightweight supervisor PID 55239, which targeted the original candidate; no experiment process stopped. Created runtime-src-fixed from pinned original source, replacing only tbptt.py. Will run corrected T64 after the first T64 ends, and benchmark corrected T32.
Fixed-window tests: 12 passed in 5.09s, including default byte identity, complete-episode equivalence and reset gradient isolation. Combined relevant coverage now 43 passing tests. Briefly SIGSTOP/SIGCONT only owned first T64 PID 54580 during tests to keep at most two heavy processes. New supervisor waits for that candidate to finish, launches ab-t64-fixed from runtime-src-fixed, then schedules bench-t32-fixed into a free slot. Full control source differs only in unused stored-state chunk helper; checkpoint/engine hashes match. No engine or default-mode change.
2026-10-03T22:30:05.159846+00:00 Supervisor PID 82577: waiting for first T64 to finish, then launch corrected T64 into its slot.
First T64 rejected at 96256 completed decisions after wins stayed at 18 for >40 more games. Stopped only own T64 PID 54580 and old controller PID 82577 after command verification. runs/ab-t64-pinned/rejected.json records incomplete negative evidence. Corrected 150k candidate starts immediately to avoid spending compute on a known weighting defect; full control PID 54561 continues untouched.
2026-10-03T22:32:12.033030+00:00 Supervisor PID 83471: waiting for first T64 to finish, then launch corrected T64 into its slot.
2026-10-03T22:32:12.061888+00:00 Corrected T64 launched PID 83478, fixed windows with reset masks.
2026-10-03T22:32:15.089712+00:00 A/B source differs only in the intentional tbptt.py chunk correction; checkpoint and engine sources match, default byte identity reverified.
2026-10-03T22:32:15.090286+00:00 ab-full-pinned: 30720 decisions, completed=False
2026-10-03T22:32:15.095002+00:00 ab-t64-fixed: 0 decisions, completed=False
2026-10-03T22:34:15.311487+00:00 Pinned benchmark prefix saved: bench-t64-fixed: {'completed': True, 'decisions': 4096, 'updates': 4, 'derived_from': 'ab-t64-fixed: first 4096 decisions', 'update_ms_per_decision': 11.292692271069882, 'decisions_per_second': 36.69720686879551}
2026-10-03T22:37:15.485423+00:00 ab-t64-fixed: 10240 decisions, completed=False
2026-10-03T22:41:46.063328+00:00 ab-t64-fixed: 20480 decisions, completed=False
2026-10-03T22:46:16.640998+00:00 ab-t64-fixed: 30720 decisions, completed=False
2026-10-03T22:46:46.658432+00:00 ab-full-pinned: 40960 decisions, completed=False
2026-10-03T22:51:17.165245+00:00 ab-t64-fixed: 40960 decisions, completed=False
2026-10-03T22:55:47.550780+00:00 ab-t64-fixed: 51200 decisions, completed=False
2026-10-03T22:59:47.985199+00:00 ab-full-pinned: 50176 decisions, completed=False
2026-10-03T23:00:18.016895+00:00 ab-t64-fixed: 60416 decisions, completed=False
2026-10-03T23:05:18.718145+00:00 ab-t64-fixed: 70656 decisions, completed=False
2026-10-03T23:09:49.415739+00:00 ab-t64-fixed: 80896 decisions, completed=False
2026-10-03T23:13:19.812159+00:00 ab-full-pinned: 60416 decisions, completed=False
2026-10-03T23:14:19.960603+00:00 ab-t64-fixed: 90112 decisions, completed=False
2026-10-03T23:18:50.549361+00:00 ab-t64-fixed: 100352 decisions, completed=False
2026-10-03T23:23:21.202523+00:00 ab-t64-fixed: 110592 decisions, completed=False
2026-10-03T23:25:51.541613+00:00 ab-full-pinned: 70656 decisions, completed=False
2026-10-03T23:27:51.951699+00:00 ab-t64-fixed: 120832 decisions, completed=False
2026-10-03T23:32:22.855860+00:00 ab-t64-fixed: 130048 decisions, completed=False
2026-10-03T23:36:23.299342+00:00 ab-t64-fixed: 140288 decisions, completed=False
2026-10-03T23:38:23.496325+00:00 ab-full-pinned: 80896 decisions, completed=False
2026-10-03T23:40:53.846239+00:00 ab-t64-fixed: 150000 decisions, completed=True
2026-10-03T23:40:53.873833+00:00 Launched pinned T32 benchmark PID 26290 into freed A/B slot.
Corrected T64 complete: 150000 decisions, 4102.59s, 30 wins/146 losses, 11.4476 update ms/decision and 36.5647 decisions/s. Corrected T32 benchmark complete: 4096 decisions, 10.6055 update ms/decision, 40.8855 decisions/s; removed its final.pt. Corrected T64 4096-decision prefix: 11.2927 ms, 36.6972 decisions/s. Full control 4096 prefix remains 50.7200 ms, 13.4296 decisions/s. Added explicit T32/T64 256-token-minibatch checks despite episode resets; final entire focused suite running logs/tests-final.log. Full A/B still active PID 54561.
Final whole focused suite: 45 passed in 72.57s (logs/tests-final.log), including default PPO byte serialization/BC payload identity, whole-episode PPO/BC equivalence, internal reset gradient isolation, strict config, padding parity, and 256-token minibatches at T32/T64 despite resets. model.py cmp still identical to before/model.py; focused git diff --check clean. Final stored checkpoint validation started with verify_checkpoints.py; full checkpoint will be checked when its 150k run finishes.
Stored final checkpoint reload validation passed: finite model and optimizer; 146 actor and 49 critic tensors differ from initialization. SHA and receipt in results/final-checkpoints.json. Own footprint 55 MiB after benchmark-checkpoint cleanup. Full A/B remains the only heavy process; controller is lightweight.
2026-10-03T23:49:24.477647+00:00 ab-full-pinned: 90112 decisions, completed=False
2026-10-04T00:00:55.535900+00:00 ab-full-pinned: 100352 decisions, completed=False
2026-10-04T00:11:26.181645+00:00 ab-full-pinned: 110592 decisions, completed=False
2026-10-04T00:21:26.916595+00:00 ab-full-pinned: 120832 decisions, completed=False
2026-10-04T00:31:57.813376+00:00 ab-full-pinned: 130048 decisions, completed=False
2026-10-04T00:42:58.708766+00:00 ab-full-pinned: 140288 decisions, completed=False
2026-10-04T00:55:29.804076+00:00 ab-full-pinned: 150000 decisions, completed=True
2026-10-04T00:55:30.602285+00:00 Both 150k A/B receipts and pinned T32 benchmark complete; summary and monitor plot generated, benchmark checkpoint removed. Final model/curve review still required.

2026-10-04T00:59:57.257548+00:00 Final review complete. Full A/B receipt: 150000 decisions, 11549.22s, 49.5545 update ms/decision, 12.9883 decisions/s, 26 wins/174 losses. Full checkpoint reload passed, 146 actor/49 critic tensors changed, all finite. Reviewed completed six-panel plot. Both early-to-late win rates declined; report explicitly leaves learning-quality gate unaccepted and <=2 ms target unmet. All owned jobs exited; final checks and cleanup recorded in results/final-validation.json.
