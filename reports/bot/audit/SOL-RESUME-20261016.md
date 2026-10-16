# BOT LEAD Sol continuation audit — 2026-10-16 (exploration)

## Authority and scope

Sam's latest instruction in this thread overrides old model routing: Sol high continues existing work; no major
strategy/runtime/model promotion before Sam returns to Opus. Resume only genuinely stopped unfinished work,
preserving original ownership and gates. Astra high is allowed only a small bounded deep diagnostic. Images,
crops and zooms use Sol. No account actions, emulator work or data access was needed by this continuation.

Repository work is in `/mpac/sdicks02/repos/clasher-bot` on 127x05, branch bot/lead; 05 remains light only.
Host compute stays with the existing owners on 01/03/04/08. Never hosts 09–18. Screen/input-only fairness,
Mac-only emulator scope, heldout exclusions and review before new host-touching scripts remain unchanged.

## Actions and evidence (UTC)

- **09:03:15Z:** command-center clock confirmed by `date -u '+%Y-%m-%dT%H:%M:%SZ'`. Initial inspection in the
  environment's `clasher` root found no reports/bot; corrected to the established `clasher-bot` worktree. No writes
  in the initial root. Read README, bot PROGRESS, exit/fullpool/noise handoffs and ownership/fairness/commit notes.
- **09:03–09:05Z:** inspected T3 live capabilities, project thread list (includeSubagents, pages of 100), durable
  last results and follow-up state. Full inventory is in `sol-resume-descendants-20261016.json`. Deduplicating
  threadId yields 67 descendants: 4 running / 57 completed / 3 interrupted / 2 cancelled / 1 idle. All 4 running
  descendants use Sol. No agent was spawned or reconfigured by this continuation.
- **Stopped-state reconciliation:** noise r2/r3 are superseded by r4 and the round-7 patch/collector; ExIt it10 by
  it11's completed verdict; r9v4 verdict round 1 by round 2 (path correction); calibration batch 2 had already
  delivered its completed A/B; the idle throughput researcher had delivered its report. None should restart.
  Completed fullpool and revset parents have active Sol descendants; their parents were not revived.
- **Parent notification:** sent T3 message with idempotency key `bot-sol-resume-inventory-20261016T0907Z` to
  coordinator `0523ae6f-baa3-4d4e-b233-b392671670db`. Key suffixes are identifiers, not observed action times.
- **Existing workers steered in place:** keys `bot-sol-current-steer-g1k1-20261016T0907Z`,
  `bot-sol-current-steer-revset-20261016T0907Z`, `bot-g1k1-cap-readonly-20261016T0905Z`,
  `bot-sol-level-ack-20261016T0910Z`. No new review round requested; no jobs duplicated.
- **G1/K1 receipt collection:** read the existing 05 JSONL monitor log only, reducing the last record per
  (host, kind, shard). Latest source sample **08:55:24Z**, not a new live host measurement: G1 4,881 rows,
  1,936,547 labels, 52 known errors; K1 1,171 games, 719,578 recording rows, 7 known errors. All 13 PGIDs alive.
  Live-python receipt counts 01=87,03=108,04=93,08=106. Babysitter asked to reconcile conservative overcount and
  add no work above cap; existing caps/leases unchanged.
- **GPU owner reconciliation:** notified LIVE via `bot-gpu-idle-owner-fyi-20261016T0912Z`. Owners confirmed
  04 V7lo1024 rc0/end **08:39:34Z**, 08 V6lo rc0/end **08:53:40Z**; eval loops alive. 01 V8 PID1967844 remains
  active around e9/20, GPU82–88%. No failed-job restart or replacement trainer is authorized or launched.
- **09:05:46–47Z, collector's read-only 03 evidence:** floorchk0/60, smoke0/40. Waiting children4019888/4019915,
  PGIDs4019880/4019902, request9/7, cwd `clasher-bot-revfix7`, execute canonical
  `/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh`; default cap105, live107, leased_idle0, no overrides or
  max-live contents. All five lease owners and all three claim owners alive. G1 groups3862002 want/used12/12,
  3874483 22/22,3889910 51/51; K1 group3862040 4/4; playdet3965663 8/16. Command-string accounting also counts
  eight playdet bash wrappers and two queued noise parent wrappers. No stale lease or deadlock established.
  Source command/output: `/tmp/clasher-r7-eval.CiIS6E/gate-inspection-command.sh` and
  `gate-inspection-output.txt` on05. No accounting/lease/priority change or signal sent.
- **LIVE tests already completed, not rerun:** unpatched178passed/9failed/7skipped/4warnings in530.46s;
  patched217passed/9failed/7skipped/4warnings in583.05s. FAILED/ERROR names identical; comparison PASS.
  This does not clear the pending floorchk/smoke gates.
- **09:07Z, level-owner update:** DEV harness4pytest pass; four A cases repeated with4/4 exact command/log/
  tower-HP matches, 8/8wins, zero errors/rejections/failures, about96–97CPU s/game. Receipt
  `reports/bot/levels/receipts/harness-dev-audit.json` is owned by the level worker. 01 exporter PID2918593 alive;
  L11 exported121cards/0errors, L5 ongoing. Original03 deferred probe PID46360 wrapper expired its30min admission
  timeout without running; no probe log and no requeue. Existing Sol independent source/launcher review active;
  small Astra high read-only normalization diagnostic delegated by level owner. Pilot bank remains undrawn.
- **Daily automation:** read `list_scheduled_tasks`; daily HEADLINE enabled, next13:00Z, same bound BOT LEAD
  thread and existing fresh-bank protocol. No schedule edited, run manually or created.
- **09:08:07Z:** `git diff --check origin/main -- reports/bot/PROGRESS.md` passed; prepared current handoff in
  the existing PROGRESS and this audit. Parent updated via `bot-sol-reconciled-20261016T0907Z`.
- **Commit preparation:** first run of the local documentation helper stopped before creating an index/commit:
  installed Git does not support `rev-parse --path-format=absolute`. Replaced it with `rev-parse --git-path index`
  plus Python path resolution. The error and exact commands are retained in the local command log; no rollback
  or remote mutation resulted from that failed attempt.

## Existing job identifiers (no launch in this continuation)

| host | job | original PGID | workers |
|---|---|---:|---:|
|03|G1s0 / G1s3 / G1s6|3862002 / 3874483 / 3889910|11 / 21 / 50|
|03|K1s0|3862040|3|
|04|G1s1 / G1s4 / G1s7|2819527 / 2936118 / 2656021|11 / 30 / 40|
|04|K1s1|2819629|3|
|08|G1s2 / G1s5|2850130 / 3611792|11 / 40|
|08|K1s2 / K1s11|2850352 / 3163805|3 / 40|
|01|K1s10|1704106|50|
|03|floorchk-r7 / smoke-r7|4019880 / 4019902|8 / 6, queued|
|03|r2 preflight|4043492|queued; child claim4043519|

Data/job logs remain under `/mpac/sdicks02/jobs/clasher/bot-fullpool` and `bot-noise` on their original hosts.
Current new-shard tree is `bot-fullpool/repo-93c1fe1af8ca`; existing old shards finish with their original pin.
New/retry r2 pin was already authorized before this continuation. Its03 preflight must pass before use there.
Existing receipts and original arguments are authoritative if a PID exits/reuses after this audit.

## Exact commands and files

Read-only commands used in the established worktree included:

```sh
hostname
date -u '+%Y-%m-%dT%H:%M:%SZ'
tail -130 reports/bot/PROGRESS.md
tail -85 reports/bot/exit/PROGRESS.md
git fetch origin
git log -1 --format='%h %cI %s' origin/main
git status --short --untracked-files=no
git diff -- reports/bot/PROGRESS.md
git diff origin/main -- reports/bot/PROGRESS.md
git show origin/main:reports/bot/PROGRESS.md
git show origin/main:reports/bot/fullpool/PROGRESS.md
git show origin/main:reports/bot/fullpool/PLAN.md
git show origin/main:reports/bot/noise-robust/PROGRESS.md
git show origin/main:reports/bot/HEADLINE.md
git show origin/main:bot/fullpool/run/fit_f1.sh
git show origin/main:bot/fullpool/run/fit_kf1.sh
git show origin/main:bot/fullpool/run/pack_g1.sh
cat bot/exit/cpu_room.sh
cat bot/exit/cpu_job.sh
git diff --check origin/main -- reports/bot/PROGRESS.md
```

T3 inventory/steering arguments and responses remain in the durable thread activity; the inventory JSON records
full descendant IDs and states. No external web search, account connection, host SSH mutation or image inspection
was performed by this BOT LEAD continuation. Only current handoff/audit documents are being committed. Exact
commit/validation commands, UTC outputs, commit SHA, file hashes and rollback status are retained under
`/mpac/sdicks02/jobs/clasher/bot-sol-resume-20261016/` on05 (commit receipt after push), and reported to parent.

## Deferred work and rollback

- Keep G1/K1 generation and the existing round-7 collector active. Resume no superseded agent or finished eval.
- Keep C56 feeders off for G1; retain r9/r10 checkpoints and LIVE GPU ownership. Do not start a replacement
  trainer because a planned run completed. Existing F1/KF1 fits stay behind their data/resource/review gates.
- Promote no student, runtime, card pin or level-aware search. The current r5v10 student remains unchanged.
- Defer major normalization/strategy choices to Opus after the bounded diagnostic and independent review.
- Conservative wrapper overcount is documented; no scheduler/cap-policy change is made during this continuation.
- No rollback needed: no compute/runtime/account mutation was made. To undo this documentation update, revert
  only its explicit report/audit paths on the then-current main; never reset a shared index or other workers' files.
