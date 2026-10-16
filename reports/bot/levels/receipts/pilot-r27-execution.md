# Primary R27 execution audit

Status: STOPPED / INVALID / INCOMPLETE. Owner-directed SIGTERM at12:43:32Z;
bounded cleanup finished12:43:33Z, parent/shell exit143. No restart or retries.
The original launch receipt is preserved as pilot-r27-execution-initial.md.

Preflight2026-10-16T12:38:18Z: output/log absent, no other levels Python job;
1327 exact SHA checks passed against completed all11 R25 identity plus all seven
registered caches and immutable primary registration/bank. All107 reviewed
source hashes also matched05. Registration/base/rule and bank were published
before games; no bank was redrawn. Fixed BASE1273808234825296,100cases/300games.

Existing reviewed launch on01 at2026-10-16T12:39:01Z:

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
export CLASHER_LEVELS_PLACEMENT_PROOF=/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.json
timeout --kill-after=10s 4h bash bot/levels/run.sh 8 --bank /mpac/sdicks02/jobs/clasher/bot-levels/pilot-r27-bank.json --out /mpac/sdicks02/jobs/clasher/bot-levels/pilot-r27 --arms A,B0,B --start 0 --count 100
```

Exclusive noclobber log:job/pilot-r27.txt. Local exec session54283; remote shell
632368; parent Python632390. run.sh8 reserves9 Python processes through the
existing lease, nice10, one serial search/no pool per game, Runtime once before
fork. One auxiliary reportCPU1 may raise aggregate reservation to10<=16.
Source/cache/runtime/model/proof/bank/registration are frozen until terminal.
No source/launcher changes, sync, new scripts, duplicate jobs or descendants.

Preflight data:job/pilot-r27-preflight.sha256 and -preflight-check.txt(1327OK),
-cache-before.sha256(all7), -processes-before.txt, -launch-utc.txt and
-operator-process.txt. Broad preflight environment was captured privately
on01 with mode0600; it is excluded from copyback/public receipts. Only named
effective behavior fields from immutable runner identity will be published.

First interim12:41:33Z preserved22rows/6cleanpairs and the B/case0 failure.
Post-stop report12:46:48Z exited1:55/300 rows,47terminal,43clean,8interrupted,
245missing;16GAME_OVER refusals across4terminal rows, all raw wins retained.
All1327 frozen SHA entries and all7 cache byte hashes still match after stop.
The unsorted cache inventory initially differed only by list order; sorted
inventories are identical. All58 output files copied01→05 and SHA verified.

Verified gone: parent632390, wrapper632373, timeout632372, shell632368 and
all8 children active at stop. Only the verified parent received our signal;
its reviewed cleanup signalled/reaped its children. Session54283 consumed143.
Raw rows/logs/receipts remain intact, no outcome exclusions or source edits.
Detailed stop receipt:pilot-r27-stop-audit.json. Public phase/API source-only
audit and minimal common no-dispatch proposal:pilot-r27-terminal-order-audit.md.
Owner review of preserved failure is required before implementation/tests or
restart. No preregistered strength decision or confirmation sizing applies.
