# Resume S1 r2 — 127x07 unavailable

Last verified state: 2026-10-08 01:16:58 UTC.
Authority: 127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/search-noise-v2/.
127x05 holds only docs/source/small audit artifacts. No heavy work there.

## Frozen seal and passed preflight

Manifest: 3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677.
Sealed once at 2026-10-08 01:07:36 UTC; 468 files.
Native: 13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309.
Fresh runtime matches 459 qualified source pins, with 434 copied runtime files.
All 24 original replays / 23,058 observation checks, original terminal
assertions, 14 Linux tests, four fork-pilot children, 18 terminal timing
cells, and optimized/reference full-game action-digest equality passed.
Fresh r2 preflight CPU: 0.7188388889 core-hours.
All peers verified the 468 frozen hashes before launch. The seal and
preflight were mirrored to 05 before confirmation began.

The original design, 192 worlds, seeds, 4,992 games, arms, analysis,
bootstrap seed, pass rules and job-index modulo 248 assignment are unchanged.
R1's surviving artifacts remain under r1-archive/<host> on 01/04/07/08/05.
The original surviving copy had 8 missing / 32 differing files of 465.
No r1 outcomes were inspected or admitted. Never contact 127x02 or merge
its receipts; archive them unread if it returns.

## Active and failed processes

All labels live under /mpac/sdicks02/jobs/clasher/ on their named host.
Verify PID identity, ancestry, lock and exit receipts before any action.
Never infer that an unreachable process has stopped.

- 127x04: s1-confirm-node-127x04-r2, launcher PID 2218782, ACTIVE.
  Fixed worker indices 0–47, cap 48, expected 992 games.
- 127x07: s1-confirm-node-127x07-r2, launcher PID 3322105, STATE UNKNOWN.
  Fixed indices 48–147, cap 100, expected 2,000 games.
  Last observed launch had all 100 workers; last observed terminal count was 0.
  Direct SSH from 05 timed out; one bounded hub check returned No route to host.
  No network changes or repeated connectivity retry loop were attempted.
- 127x08: s1-confirm-node-127x08-r2, launcher PID 3375468, ACTIVE.
  Fixed indices 148–247, cap 100, expected 2,000 games.
- 127x01: s1-collect-r2, launcher PID 3336667, EXIT 1 at 01:14:25 UTC.
  Cause: rsync/SSH to 127x07 returned No route to host (255).
  Its log/exit are preserved under operations/ as well as jobs/.
- 127x01: s1-reachable-backup-r2, launcher PID 3345125, ACTIVE.
  Runs operations/reachable_backup_r2.py at nice 10. Copies only receipts/status
  from 04 and 08, with --ignore-existing for immutable game receipts.
  No 07 probing, analysis, reassignment, or frozen-file edits.
  Stops after both reachable supervisors finish, on validation failure, or
  after its six-hour operational window (approximately 07:16:55 UTC).
  See operations/reachable-monitor-r2.json and the job log/exit.

All launch who checks were empty; nice 10 and one native/BLAS thread.
Console users reduce a node to four concurrent S1 workers; --concurrency
supports a lower technical cap without changing assignments. 04's separate
C56 extraction cap remains 32.

## Counts and compute

At 01:16:58 UTC, the hub's outcome-blind validator confirmed 286 / 4,992
terminal receipts: 04 = 110, 08 = 176. No 07 receipts were collected.
0 / 248 completed partitions. No 04/08 worker failure was observed.
Completed-game CPU recorded in these 286 receipts: 14.7149011330 core-hours.
This is a partial lower bound; live/incomplete games and 07 CPU are unknown.
Use the live backup monitor for newer counts. No outcomes have been inspected.

## Recovery steps

1. Restore 127x07 availability externally. Do not touch network daemons,
   crontab, other-project hosts, or 127x02. Do not migrate its partitions.
2. Once 07 is reachable, inspect its original supervisor and all assigned
   worker PIDs/ancestry/locks/exit/current/done receipts. Preserve every receipt.
   If still running, leave it running. Do not duplicate it.
3. Only a permitted technical failure may resume identical inputs under a new
   attempt label. Example after verified termination and diagnosis:
   fleet_run.sh s1-confirm-node-127x07-r2a .venv/bin/python -B
   reports/strategy_council_20260928/search-noise-v2/launch_node.py --attempt r2a
   Keep valid terminal receipts; the frozen worker validates and skips them.
   Wrong identity/hash receipts are hard failures, not overwrite candidates.
   A correctness bug in frozen code means STOP and report for a new protocol
   with fresh seeds; never patch or use an outcome-based rerun.
4. When 07 is reachable and its state is reconciled, restart the unchanged
   collector on 01 under a fresh label:
   fleet_run.sh s1-collect-r2a .venv/bin/python -B
   reports/strategy_council_20260928/search-noise-v2/collect.py --wait
   Retain s1-collect-r2's exit 1. Retire the reachable-only backup only after
   verifying its actual process identities and confirming full collection works.
5. Monitor technical fields only. operations/technical_status.py checks
   manifest, job, seeds, seat, cell, host and terminal status without accessing
   score/winner fields. The frozen collector invokes the unchanged analysis
   only after all partitions succeed; analysis validates all 4,992 receipts.
6. Only after completion inspect RESULTS.md/result.json. The unchanged
   analyze.py retains an r1 narrative sentence about known engine defects;
   preserve its generated report, then correct that report text to identify
   the qualified r2 build/deviation without changing statistical output.
7. Mirror PREREG, PROGRESS, RESUME, manifest, preflight, execution, small
   audits and final RESULTS.md/result.json to 05. Keep raw confirmation/
   and runtime binaries on the fleet. No commits, engine/gamedata edits,
   data deletions, broad process kills, or network changes.

Do not rerun prepare.py, seal.py, registration, tests, pilots or distribution.
Do not edit any manifest-listed file. No RESULTS.md/result.json exists yet;
the pre-registered verdict and per-cell intervals remain unavailable.

## Latest handoff checkpoint

2026-10-08 01:19:05 UTC: handoff checkpoint 397/4992 validated receipts, 0/248 completed partitions; per-host {'127x04': 149, '127x08': 248}; completed-game CPU 20.15272840 core-hours. 04/08 and reachable-only backup remain active; 07 unresolved. No outcomes inspected.

This dated checkpoint supersedes earlier receipt/CPU counts above. Full machine-readable state: operations/handoff-r2.json. Live detached backup status: operations/reachable-monitor-r2.json.
