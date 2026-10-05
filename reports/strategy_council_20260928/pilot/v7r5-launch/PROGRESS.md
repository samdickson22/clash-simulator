# v7r5 progress

Build in progress. No v7r5 training launched.

Done: read project guidance, v7r4h kit, v5 manifest/build tool, TBPTT report and admission-scope implementation. All existing overlay targets are TRAINING_ONLY; tbptt.py is new. v5 shares the workspace .venv.

Blockers found: unchanged council_pilot.py rejects new tbptt.py, strictly forbids the three config fields, and binds PPO/collector definitions at AST level. Investigating without changing that file or bypassing validation.

Running PIDs: none.

Next: construct exact four-file overlay, verify all 342 admission-bound module hashes, run focused tests from v6, record concrete scope/config failures. No launch until validation and the host gate pass.

Exact build command:
```
nice -n 10 .venv/bin/python -B reports/strategy_council_20260928/pilot/v7r5-launch/build_runtime.py
```

## Runtime and kit checkpoint

Runtime built at 2026-10-04T01:06:09Z. All 342 admission-bound modules equal v5 and the admission receipt. Only train_recurrent.py, parallel_rollout.py, imitation.py and new tbptt.py were overlaid. .venv is the same workspace symlink. Hashes are in logs/runtime-build.json.

Two configs and copied launch/verification/rebind/early-check tools created. Config parity checks pass. Launcher defaults to nominal, rejects league and seed 2903, and checks the explicit v7r4h host gate before training. orchestrate.sh only refuses and exits.

Static verification: 49/54 passed. Real source-scope rejection: new tbptt.py. Both config loads reject the three extra fields. Warm-start checks cannot proceed. Independent AST inspection also found changed bound definitions: RolloutBatch, collect_rollout, collect_rollout_stationary_opponents, ppo_update, ActorWorkerConfig, _actor_worker_main and concatenate_rollouts. See logs/blockers.json. No enforcement was changed.

Initial pytest from runtime cwd: 35 passed, 3 failed, 7 errors, all failures/errors were missing cwd-relative test/config fixtures. Rerun uses asserted v6 module imports and workspace cwd for those fixtures.

Running: focused test process; no owned training. Dry-run/preflight stage-1 refusal receipts pending. Next: finish evidence and report the integration blockers.

## Validation checkpoint

Runtime manifest SHA256: e6405dfcb67cb4bc27e2dcd7896ea8f9827c6ee8bc742f608860a7ccc37e74c5
Pilot source pins SHA256: 1e77d89e5b751634f7dfe2eb1066f1380c64a164190d155f45129698bd0b7bdb

Final focused suite: 43 passed, 2 failed in 60.95 seconds (logs/pytest-v6-final.log). All four learner imports were asserted to come from v6. Workspace cwd supplies test fixtures. A previous stdin-based runner could not spawn multiprocessing workers and was interrupted by SIGINT to owned PID 66630 only; that attempt is superseded.

The two remaining reference failures concern actor/critic card_stat_features and semantic_card_features buffers. v5 reproduces exactly the same differences from the saved references. Default PPO and BC outputs from v6 equal v5 recursively for every tensor, numpy array, field and RNG state tested. Receipts: logs/default-v5-comparison.json and logs/default-v6-comparison.json. Existing reference files were not changed.

Dry runs 2901/2902: exit 3 at stage 1. Preflight commands 2901/2902: exit 3 at stage 1; no-update trainer preflights never reached. Static verification: 49/54 checks passed. Config parity checks passed for both seeds. No warm starts copied and no run directory created.

Launch: none; no launch time or owned training PID. Host gate was false: neither stop marker present, v7r4h trainers 87474/93325 alive. No foreign process was signaled or stopped.

Baseline throughput across first 20 warm-up updates: v7r4h seed 2901 = 18.8573 decisions/s, seed 2902 = 20.7640 decisions/s. Update 20 alone: 27.9 / 30.2. Aggregates use 163840 decisions divided by summed collect_s + learn_s + sync_s; source log paths are in logs/v7r4h-first20-throughput.json. v7r5 throughput unavailable because launch is blocked.

Running PIDs: no owned long-lived processes.

Next: resolve council_pilot config/argv and source-scope integration beyond the four-file overlay, preserving the 342 module hashes and unchanged admitted engine. Resolve or explicitly rebase reference fixtures to the frozen runtime. Rerun verification, dry runs and actual no-update preflights before waiting for the host gate. Do not launch this candidate as-is.

## Exact commands

```
ROOT=/Users/sam/Desktop/code/clasher
RC=$ROOT/reports/strategy_council_20260928
RT=$RC/m0/runtime-snapshots/pilot-runtime-v6
K=$RC/pilot/v7r5-launch
export CLASHER_ROOT=$RT PYTHONPATH=$RT/src:$RT/scripts PYTHONDONTWRITEBYTECODE=1
export NUMBA_CACHE_DIR=$K/logs/numba-cache OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$RT"
nice -n 10 "$RT/.venv/bin/python" -B "$K/test_runtime.py"
nice -n 10 "$RT/.venv/bin/python" -B "$K/verify_v7r5_launch.py" --protocol
"$RT/.venv/bin/python" -B "$K/inspect_blockers.py"
nice -n 10 bash "$K/launch.sh" 2901 scripted --dry-run --through nominal
nice -n 10 bash "$K/launch.sh" 2902 scripted --dry-run --through nominal
nice -n 10 bash "$K/launch.sh" 2901 scripted --through preflight
nice -n 10 bash "$K/launch.sh" 2902 scripted --through preflight
```

Prospective launch commands, NOT executed. First repair validation and pass the gate; start the second command at least 600 seconds after the first. Do not use orchestrate.sh.

```
bash "$RC/pilot/detach.sh" "$K/logs/detached-s2901.log" --cwd "$RT" env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 bash "$K/launch.sh" 2901 scripted --through nominal
bash "$RC/pilot/detach.sh" "$K/logs/detached-s2902.log" --cwd "$RT" env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 bash "$K/launch.sh" 2902 scripted --through nominal
```

Build is write-once. Do not rerun build_runtime.py or make_configs.py against existing outputs. Only the new v6 and v7r5 directories were written by this task.

## Authorized integration resume (2026-10-04T01:22Z)

Read PROGRESS, README and all present workspace guidance. Coordinator explicitly authorizes the workspace council_pilot integration and its v6 overlay. No runner change is currently needed. Preserving v7r4h argv and source-scope output against v5 will be tested directly. Existing foreign jobs and snapshots remain untouched. Stop markers are still absent; no owned training process.

## Council integration and pins (2026-10-04T01:24Z)

Workspace council_pilot.py now accepts and forwards stored-state/T32/B16, validates trainer args, and admits only the named new tbptt.py module. Seven learner definitions may differ when that module is present; definitions imported by admission-bound code remain AST-bound. Old runtimes keep the original bindings. scripts/run_council_pilot.py needed no edit.

v6 overlay/pins regenerated by extend_runtime.py. All 342 module hashes equal v5 and the admission receipt. Manifest c5391ff5d39f5591c04a7e47a8337c0547e21c252aaa459e8e86c239abf069a4; pins d668bb086e9e6331815f196708215a63bc5608650fd43cc8635c091943209214. Full receipt: logs/council-integration-build.json.

Integration tests: 9 passed in 22.36s. Both v7r4h seed configs retain byte-identical argv in smoke/nominal/league and identical serialized source-binding reports and recipe records versus frozen v5. Negative control confirms an admission import overrides the learner exception. Initial test-loader Pydantic namespace failure was corrected by registering the reference module, without changing v5.

First expanded verifier reached 105/107. Corrected two kit-only stale assumptions: compare the changed module list sorted; validate the human checkpoint seed 2903 against declared config seeds rather than the two launch seeds. Launch restriction remains 2901/2902. Next: rerun verify, dry runs, and actual no-update preflights.

## Static verification passed (2026-10-04T01:27Z)

verify_v7r5_launch.py --protocol passes 107/107 (logs/verify-integration.log). Both stale verifier assumptions are fixed. Seed 2901 dry-run completed hash-checked warm-start rebinding and is checking the admitted ledger. No owned training. README and sidecar-generator descriptions now reflect the authorized integration.

## Seed 2901 dry run passed (2026-10-04T01:29Z)

Dry run 2901 exited 0 with full admission and rebind verification. Evidence: logs/dry-run-integration-2901.log and timestamped launch/verify receipts. Seed 2902 dry run is now rebinding and validating. No training launch.

## Both dry runs passed (2026-10-04T01:33Z)

2901 dry run exited 0 at 01:28:57Z; 2902 exited 0 at 01:32:49Z. Both include real admission-ledger verification, rebind verification, frozen pins, and planned nominal argv. Logs: logs/dry-run-integration-2901.log and logs/dry-run-integration-2902.log. Starting sequential nice-10 no-update preflights through launch.sh, with all checks retained. Gate still closed; no training launched.

Preflight seed 2901 finished at 2026-10-04T01:36:42Z, exit 0. Evidence: logs/preflight-integration-2901.log.

Preflight seed 2902 finished at 2026-10-04T01:40:16Z, exit 0. Evidence: logs/preflight-integration-2902.log.

## Validation complete; waiting for host gate (2026-10-04T01:41Z)

Both real no-update preflights passed: seed 2901 at 01:36:42Z and seed 2902 at 01:40:16Z. Each used 64 envs/8 workers and exercised critic warm-up plus PPO; zero optimizer steps, unchanged initializer file and weight digest, no checkpoint written. Summary: logs/validation-complete.json. Rechecked all v5 manifest source/script files against their frozen hashes and all 342 v6 modules against v5 plus admission. No owned heavy process remains. No v7r5 training launched; waiting for both stop markers and absence of both v7r4h trainers.

## Host gate wait (2026-10-04T02:00Z)

Latest v7r4h monitor totals: 2901 = 1,917,504; 2902 = 1,942,080. Both old trainers remain (87474, 93325); neither stop marker exists. Validation is complete and unchanged. Read-only gate samples are appended to logs/host-gate-wait.jsonl. No v7r5 launch or delayed launch process exists.

## Host gate wait (2026-10-04T02:30Z)

Seed 2902's training monitor reached 2,000,000 decisions; this is not the launch gate. Neither stop-log marker is present, and both v7r4h train_recurrent PIDs remain. Seed 2901 is at 1,958,464. No v7r5 launch.

02:31Z gate transition: seed 2902 stop marker present and trainer 93325 absent. Seed 2901 marker absent and trainer 87474 remains. Waiting for 2901; no v7r5 launch.

## Seed 2901 launched (2026-10-04T02:46:29.091302+00:00)

Gate passed: both explicit 2M stop markers present and no old trainer remains. Detached through pilot/detach.sh with --through nominal, nice 10. Launcher PID 18564. Receipt logs/detach-receipt-2901.json; log logs/detached-s2901.log. Seed 2902 may launch no earlier than 2026-10-04T02:56:29.091302+00:00. Waiting for trainer startup and enforcing the stagger.

02:51Z: seed 2901 trainer PID 20302, runner PID 19395. Process argv confirms stored-state / chunk 32 / burn-in 16. First update pending; seed 2902 remains held until 02:56:29Z.

## Seed 2902 launched (2026-10-04T02:57:04.473303+00:00)

Gate rechecked successfully. Detached through pilot/detach.sh with --through nominal, nice 10. Launcher PID 25086. Stagger 635.382 seconds after seed 2901. Receipt logs/detach-receipt-2902.json; log logs/detached-s2902.log. Seed 2901 trainer 20302 is active. Next: confirm 2902 trainer, then first-20-update throughput for both.

02:57Z: seed 2901 completed update 1 (8,192 learner decisions), confirming training. Seed 2902 launcher is checking admission. Throughput will use complete first-20 update timings from train logs, matching the v7r4h baseline method; buffered stdout is not treated as absent progress.

03:03Z: seed 2902 trainer PID 32205, runner PID 28740. Live argv confirms stored-state / chunk 32 / burn-in 16. Both detached launchers and trainers are active; seed 2901 has completed update 3. Waiting for first 20 timings per seed.

03:07Z: seed 2902 completed update 1 (8,192 decisions). Both seeds have now reached training. Seed 2901 completed update 4; the first three flushed timing rows average 43.7256 decisions/s, preliminary only. Final comparison still waits for 20 timing rows per seed.

03:22Z: seed 2901 reached update 10 / 81,920 decisions; seed 2902 reached update 6 / 49,152 decisions. Both trainers active. Buffered train logs currently expose 5 / 4 timing rows; provisional aggregates 43.5069 / 44.4047 decisions/s. These are not the requested final first-20 figures. Monitoring continues.

03:31Z: seed 2901 update 14 / 114,688 decisions; seed 2902 update 10 / 81,920 decisions. Both trainers active; waiting for all first-20 timing rows to flush.

03:42Z: seed 2901 reached update 20 / 163,840 decisions; seed 2902 reached update 16 / 131,072 decisions. Train stdout currently exposes 15 / 14 timing rows, so the exact first-20 throughput comparison remains pending. Both trainer PIDs are active. No process was signaled to force a log flush.

03:51Z: both seeds have completed at least 20 updates. Seed 2902 reached update 20 / 163,840 decisions; seed 2901 is at update 24. Timing rows exposed so far remain 15 / 14 because stdout is buffered. Waiting for a natural flush to compute the exact first-20 comparison; both trainers continue toward nominal.

03:53Z: seed 2901's first 20 timing rows flushed. Aggregate 55.3181 decisions/s versus v7r4h 18.8573 (about 2.93x), using 163,840 decisions / summed collect_s + learn_s + sync_s. Seed 2902 first-20 timings still pending; its trainer has completed update 21. These are critic warm-up measurements, not PPO learning-quality acceptance.

## Requested launch and early measurement complete (2026-10-04T04:02:37.558008+00:00)

First 20 updates, 163,840 decisions each: 2901: 55.3181 vs 18.8573 decisions/s (2.9335x); 2902: 59.3881 vs 20.7640 decisions/s (2.8602x). All 20 updates are critic warm-up. Timings sum collect_s + learn_s + sync_s, matching independently re-read v7r4h logs. Full timing rows and stable first-20 line hashes: logs/first20-throughput.json. Buffered stdout required waiting until updates 28 / 24 to observe the full timing rows; the comparison uses exactly updates 1-20.

Final recheck: all 342 admission-bound v6 modules equal v5 and admission; every v6 pin and v5 source manifest hash still matches. Workspace council integration equals the v6 copy. Both old trainers remain absent. Detached launcher PIDs 18564 / 25086; current trainer PIDs 20302 / 32205; runner PIDs 19395 / 28740. Launch UTC times 02:46:29.091 / 02:57:04.473, stagger 635.382 seconds. Both continue through nominal only. No foreign process was touched.

Files changed in this resume: workspace src/clasher/rl/council_pilot.py; its v6 copy, pilot-source-pins.json and pilot-runtime.json; kit test_council_integration.py and extend_runtime.py (new), verify_v7r5_launch.py, make_sidecar.py, orchestration-pins-pilot-runtime-v6.json, launch.sh (comment only), README.md and PROGRESS.md, plus validation/launch/preflight/training receipts under this kit. scripts/run_council_pilot.py was not changed.

Open: nominal training/evaluation continues. These measurements establish early warm-up throughput, not learning quality or post-warm-up PPO throughput. The prior two saved-reference fixture mismatches also reproduce in v5 and remain documented; fixtures were not changed. No remaining launch blocker. Final receipt: logs/final-evidence.json.
