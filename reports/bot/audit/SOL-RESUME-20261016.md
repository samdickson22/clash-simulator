# BOT LEAD Sol continuation audit — 2026-10-16 (exploration)

## Current authority (updated 09:17–09:21 UTC)

Sam superseded the initial blanket Opus hold: make confident, routine, reversible decisions now within project
authority, with meaningful passing checks, required reviews and concrete rollback. Defer only consequential
hard-to-undo AND sufficiently uncertain choices where Opus could materially change approach. Sol high default,
bounded Astra where useful, no Claude limit retries. Scientific/review failures still block acceptance.

Coordination questions go DIRECT via `t3_thread_send(mode='auto')` to the parent
`0523ae6f-baa3-4d4e-b233-b392671670db` or existing owner; include question/evidence/paths/recommendation/dependent
wait and continue independent work. No user-input tools. This was sent to all3active descendants (levels owner,
G1K1babysitter,r7collector), with recursive propagation and future-brief instruction. No old pending input reported.
Actual permission controls, fairness, host/resource rules and required host-script review remain.

## Initial authority and scope (historical; blanket hold superseded above)

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
- **09:10:15Z:** documentation commit `5da7369307c07de542a2d5812cc99363978cbc22` pushed to main via an isolated
  temporary index on parent `2b7049fae3c60fadb425a4e6e14f0d645da7e396`. Three explicit paths only. JSON parsing,
  staged whitespace check and mandatory secret scan passed; shared worktree index SHA and HEAD unchanged.
  Exact helper launch: `python3 /mpac/sdicks02/jobs/clasher/bot-sol-resume-20261016/commit_docs.py`.
- **09:10Z, MATERIAL correction from level owner:** original11/5 exporter completed. L11 121cards/0errors;
  L5 118cards/3errors(Clone,Earthquake,Tornado). Full-runtime check11 matches only3/121 cards to R.config;
  118 unsupported INCLUDING pilot cards. Current B would silently keep L11 for most cards. **Pilot HOLD before
  bank/game**; earlier20-card preliminary mapping claim is not upheld. Existing disjoint4/6/7/9 exports remain
  alive/valid. Source/schema diagnosis stays with original owner and existing reviewers; no duplicate work or
  promotion. Coordinator immediately notified via `bot-level-blocker-20261016T0910Z`; owner acknowledged via
  `bot-level-blocker-ack-20261016T0910Z`. First attempt to patch PROGRESS used a nonmatching context line and was
  rejected without edits; corrected the patch and recorded this blocker here and in PROGRESS.

## Follow-up evidence and decisions

### 09:17–09:21 UTC decision rule, schema confirmation and serial pilot

- Read existing level DESIGN/RESULTS, root/player/config source and bounded Astra receipt; no new Astra task or
  duplicate diagnostic. Propagated corrected decision rule to levels owner, active launcherreviewer, G1K1babysitter,
  r7collector and CARDlead; owner handles recursive propagation. Keys `bot-obvious-decisions-*`,
  `bot-card-root-rule-update-20261016-r1`; coordination keys `bot-coordination-rule-20261016-<taskname>`.
- Level owner runtime confirmation09:18Z: raw3/121 vs canonicalnativeJSON121/121, noerrors. Musketeer/Archers/
  Fireball tunnel_origin is tuple(0,0) inruntime vs list[0,0] ondisk. Schema-only mismatch confirmed. Mapping hold
  lifted. Tower13checksPASS(8curvesL10/12+L4–8RoyaleSimHP); configs pytest2passed0.19s. Original exports unchanged;
  L4/6/7/9 completed118cards/3knownerrors at359/355/377/382CPUseconds.
- DECISION: accept original SERIAL100casepaired A/B/B0 physics experiment after remaining mandatorygatesPASS.
  A unchangedL11; B0existingLevelRootrootonly; Bexactownlevels/towers/per-seattemplates+qualifiedpayloads/spells,
  fairfixedopponentmediancommon5/rare4/epic6/legendary9,crownmetadata2030/3312. The metadata affects leaf AND
  scriptedcrownspelllethality/Lightning; identical-state learnedfeatures unchanged. Honest scope resolves the
  normalization deferral. Serial experiment does not depend on pooledLIVE deployment; no claim about pooled
  startup/recovery equivalence. Existing rawfc transport gate retained. RollbackselectA/removeexperimenthooks;
  no frozenruntime,pin or weights writes. Levelowner notified key `bot-level-design-decision-20261016-r2`;
  parent `bot-serial-level-decision-20261016-r1`.
- Pre-bank scope audit `levels/receipts/scope-audit-r1.json`: originalcatalogSHA
  80de4afb5b63c7dbdcb0ab285a715f9a93f4d6eeacffdfbe9f8c300ea7fecd8a,2925decks/69380frequency.
  ExcludingClone/Earthquake/Tornado removes425decks/15371frequency=22.1547996541%;2500decksremain.
  All54selectedtrue-gameprojections unchanged. Earthquake385decks,Tornado43,overlap3,Clone0.
- DECISION: accept fixed supported-prior restriction identically A/B/B0 and policy pollers BEFORE bank/outcomes,
  keeping original projection catalog immutable. Conditional-population physics pilot only; not literal current
  live-prior equivalence or immediate deployment evidence. Require same ordered-prior digest inallarms/pollers,
  no unsupportedcard reachable inroot hand/cycle, forcedall11 on same subset, provenance and deterministicresume
  scope checks. No silentL11 or post-outcome exclusion. Rollbackomitexperimental prior replacement/selectoriginalA
  outsidepilot. Owner `bot-level-supported-prior-decision-20261016-r1`; parent
  `bot-level-supported-scope-to-parent-20261016-r1`. Owner implements; no extra compute launched by BOTLEAD.
- Remaining blockers are evidence-based: forcedall11bothseats/controllers, rootperseatcard/spellimpact,
  rootfixtures/fairnessdecisioninvariance, fc/snapshot/rawpooltransport, freshlauncherreview, scope/provenance/
  completeness. No bank drawn. No blanket design/promotion hold remains.
- G1K1babysitter09:16:32Z normalcheck:all13PGIDsaliveprogressing;G15927attempts/5865ok/2350972labels/62knownerrors
  (51Freeze11BarbarianRage);K11713attempts/1704ok/1055727recrows/9knownerrors(3Freeze6BarbarianRage).
  No original shard finished,no retry due;03r2preflightstillqueued,logempty/noPASS.
  Literalcounts03=108,08=105,04=91,01=95;actualPython03=97,08=102,04=89,01=86(includes31YOLOloaders).
  No new workers/oversubscription. GPU01=56%firstqualifyinglow,computePID1967844;04/08idle/nocompute. No logins.
  Existing GPUbackoff rule unchanged; nohalving/kills/launches inthischeck.
- CARDlead confirms no new root/pin release yet. Corrected native-only translator/board-root coverage and fresh
  independentreview stillpending; existing08wrapper2432076 retained. PriorK4L12/12,assembler11,55834Nonechecks,
  8496rankcomparisonsPASS; oldr2BarbarianRage crash reproduced negativecontrol. Exact immutable release receipts,
  source/native hashes,host preflights and rollback to retainedr2 required before migration.
- Exact read commands this interval included `cat reports/bot/levels/DESIGN.md`,
  `cat reports/bot/levels/receipts/leaf-diagnostic-astra-r1.md`, `cat reports/bot/levels/RESULTS.md`,
  `sed -n '1,230p' bot/levels/root.py`, `sed -n '1,230p' bot/levels/player.py`,
  `cat reports/bot/levels/receipts/scope-audit-r1.json`, `cat reports/bot/levels/receipts/configs-L6-r1.txt`,
  `sed -n '1,235p' bot/levels/configs.py`, all in the existing levelownerworktree, read-only.
- Follow-up commit command:
  `BOT_AUDIT_COMMIT_TITLE='Bot: accept gated serial level pilot under updated Sam direction' python3 /mpac/sdicks02/jobs/clasher/bot-sol-resume-20261016/commit_docs.py`.

## Existing job identifiers (no launch in this continuation)

### 09:31–09:32 UTC published receipt verification

- Verified ownerpublication `f85c66d375a949e007d9aeff6983c3f028c64b50` afterfetch:24changedpaths allunder
  reports/bot/levels, no implementation staged; required Opuscoauthor retained. Owner reports tempindex+secret
  scanPASS. BOT read commit metadata/paths; did not rerun owner's commit operation or tests.
- Exact mapping/towerSHA256 both localreceipt and committedblob:
  `cd30432de666b2e58929f59702c358b630298f36bb7c93127038b93a31b04645`.
  Exact scopeauditSHA256 bothlocal and committedblob:
  `c7f2c5beac6c67da79ddb4295900978b6ae6f41af40d8dbe5fb841005ef8334d`.
- Additional reviewed01scope/configtestreceipt `pytest-scope-configs-r5.txt`:4passed0.24s; localSHA256
  `9c714207acdb4637742c0d3473ba4d87be7b978f65d5b0063c39ad919e6fa9d7`. This newerreceipt is separate from
  publicationf85's earlier2-testreceipt. Source reviewr5 found no new concrete scope/projectionblocker and approved
  this lightweight test invocation only; no bank/gameapproval or exactrootgate waiver.
- Gateimplementation finished, fresh independent executionreview next; harnessprovenance continues. No pilotbank/
  outcomes. Parent notified `bot-level-published-receipts-verified-20261016T0932Z`; existing owners retain work.
- Exact commands inlevelworktree:
  `git fetch origin`; `git show --format=fuller --stat f85c66d375a949e007d9aeff6983c3f028c64b50`;
  `sha256sum reports/bot/levels/receipts/gates-schema-towers-r2.txt reports/bot/levels/receipts/scope-audit-r1.json`;
  `cat reports/bot/levels/receipts/pytest-scope-configs-r5.txt`;
  `sha256sum reports/bot/levels/receipts/pytest-scope-configs-r5.txt`;
  `head -24 reports/bot/levels/receipts/review-sol-r5-scope.md`;
  `git show f85c66d375a949e007d9aeff6983c3f028c64b50:reports/bot/levels/receipts/gates-schema-towers-r2.txt | sha256sum`;
  `git show f85c66d375a949e007d9aeff6983c3f028c64b50:reports/bot/levels/receipts/scope-audit-r1.json | sha256sum`.
- Follow-up commitcommand:
  `BOT_AUDIT_COMMIT_TITLE='Bot: verify published level receipts and scope tests' python3 /mpac/sdicks02/jobs/clasher/bot-sol-resume-20261016/commit_docs.py`.

### 09:28 UTC scope implementation and queued original probe

- Existing levelowner implemented accepted scope in `bot/levels/scope.py`, experimental playerfactory and bank
  projection equality guard. Read-only BOT check confirms ordered-prior digests, deep-copied preserved original,
  idempotency guard and fixed excluded cards in scope.py. This source inspection is not a runtime/review PASS.
  Fresh independent scope review remains active; original/standardAoutsidepilot untouched.
- Gateworker drafts actualroot/fairdecision fixtures onbothseats and explicit productionrawfc A→B→A reuse;
  harnessworker repairs fullmanifest-before-resume, nonzero failure/completeness/parity and ownedchildcleanup.
  Fresh review covers completed gate/harness bytes before tests. No bank drawn or primary games.
- All01disjointexports finished; no01compute until reviewedgates. Exact finalreceiptSHAs await owneraudit; partial
  digests/filenames are not evidence. Existingmapping/towerPASS status unchanged.
- At09:26:07.950341Z owner verified old03probe absent, then requeued originalN4probe ONCE undernice10 and original
  30min admission/execution timeout,queuedPIDs287537/287538. Fullpoolpriority still enforced by admission.
  Exact ownercommand preserved:
  `ssh 127x03 'nice -n 10 timeout --kill-after=10s 30m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4 bash /mpac/sdicks02/jobs/clasher/bot-levels/run_all.sh'`.
  Another timeout is recorded asdeferral,notspin-retried. No duplicateprobe or BOTLEADcompute launch.
- Parent notified `bot-level-implemented-scope-and-probe-20261016T0928Z`. Read-only commands inlevelworktree:
  `sed -n '1,240p' bot/levels/scope.py`; `rg -n 'scope|PRIOR|projection|manifest|resume' bot/levels/run.py bot/levels/profile.py bot/levels/player.py bot/levels/bank.py bot/levels/factory.py`;
  `tail -45 reports/bot/levels/PROGRESS.md`. factory.py doesnotexist; actualfactory isplayer.py,which rg located.
- Follow-up commitcommand:
  `BOT_AUDIT_COMMIT_TITLE='Bot: record level scope implementation and bounded probe requeue' python3 /mpac/sdicks02/jobs/clasher/bot-sol-resume-20261016/commit_docs.py`.

### 09:13 UTC follow-up

- Level owner reports likely cause of the3/121 result: Python tuple coordinates (`tunnel_origin`/`destination`)
  become lists in disk-cached JSON, while the preliminary20-card comparison skipped JSON roundtripping. Canonical
  native-JSON comparison and versioned support receipt patched by that owner, preserving exports. This is a
  hypothesis awaiting runtime confirmation and fresh review; **pilot HOLD remains before bank/games**.
- Bounded Astra diagnostic reports leaf_native affects scripted spell lethality and Lightning ranking as well as
  the leaf; learned feature vectors remain identical for identical states. Native pool startup/recovery differs
  under fork/spawn. Normalization and pool design remain parked for Opus; no scope-changing decision made here.
- Tower catalogue alias Archers→Archer fixed by existing owner through the existing alias map.
- Coordinator heartbeat corrects the earlier descendant snapshot: revset-fix-r2 received a NEW report-handling
  turn on Claude which failed after the collector's saturation diagnosis. Coordinator switched that exact owner
  thread to Sol high and resumed ONLY report/handoff acknowledgment. Completed coding work was not restarted;
  existing Sol collector/jobs/gates/priorities unchanged. Running-thread pending-request checks empty.
- Heartbeat host loads01/03/04/08 about65/94/95/101; GPUs01=89%,04=3%,08=0% (04/08 completed trainers and existing
  evals only). No host intervention. BOT LEAD relayed material level scope findings and acknowledged this correction
  to parent with idempotency key `bot-level-schema-leaf-evidence-20261016T0913Z`.
- Follow-up documentation command:
  `BOT_AUDIT_COMMIT_TITLE='Bot: log level schema diagnostic and resumed report owner' python3 /mpac/sdicks02/jobs/clasher/bot-sol-resume-20261016/commit_docs.py`.

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
- Current r5v10 remains unchanged because no stronger student is confirmed. Reviewed/gated/rollbackable changes
  may proceed under the updated rule; no blanket promotion hold. Serial level pilot is accepted subject to gates.
- Defer only consequential hard-to-undo and materially uncertain choices. Serial normalization scope and fixed
  supported-prior experiment are now decided; pooledLIVE integration remains outside this serial experiment.
- Conservative wrapper overcount is documented; no scheduler/cap-policy change is made during this continuation.
- No rollback needed: no compute/runtime/account mutation was made. To undo this documentation update, revert
  only its explicit report/audit paths on the then-current main; never reset a shared index or other workers' files.
