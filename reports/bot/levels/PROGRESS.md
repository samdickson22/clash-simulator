# Level-aware search pilot: progress (exploration)

Design: [DESIGN.md](DESIGN.md). Scope: [SCOPE.md](SCOPE.md). Worktree: 127x05 `/mpac/sdicks02/repos/clasher-bot-levels`
(branch bot/levels, synced to 127x01 by `rsync -a bot/`). Job dir: `/mpac/sdicks02/jobs/clasher/bot-levels/` (05 master,
01 runs). Runtime: copy of live16402b-r2 at `jobs/clasher/bot-levels/runtime/live16402b-r2` on 01 (pins verified by
Runtime()); 03/04/08 use `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r2`.

## Log

- 08:56Z 10-16: scope read; worktree created from origin/main 5b55e3aa; deferred probes (SCOPE.md exact command,
  N=4 on 03) queued behind 03's full-pool generation (03 at 107/105 python processes).
- RoyaleSim mixed-level reset confirmed on 01 (`probe.py rsim`, job dir `rsim-probe-01.txt`): tower level 6 = king 3312 /
  princess 2030 HP, level 8 = 3768/2352; Musketeer 375/496/721 HP at L4/7/11.
- Exporter check (dev/explore2.txt): `differential.config(cards, level=11)` == R.config for 20 pilot cards and all their
  side tables; level 5 changes only hp/max_hp/damage/special_damage/payload_key (+ spell damage/crown damage).
  Native looks every secondary payload up by payload_key ⇒ level-specific rollouts need no Rust rebuild.
- Hooks: `royalesim_match` levels/tower_levels (None = unchanged call); `MultiSearchPlayer.root_fn` (None = R.root).
- Sol harness worker `bot-levels-harness-sol-r1` (bank/run/report) started.

## Next

1. Level export cache (L3–9, 11) on 01; gates (`python -m bot.levels.gates`); all-11 forced-B parity games.
2. Draw the pilot BASE (os.urandom) and record it here with the decision rule; run 100 cases × A/B/B0.
3. s27-m02 replay diagnostic (BOT LEAD request): live decision states at L11 vs level-aware, 2:56–2:14 window.

## Sol resumption audit — 2026-10-16 09:05:10 UTC (02:05 PT)

Sam direction: preserve ownership/gates/data; no major decisions or strategy/runtime/model promotion before Opus
returns. Routine fixes, tests, evidence and existing jobs continue. Heavy compute never on 05; never hosts 09–18;
no GPU use. New host-touching scripts require independent review before launch. No account actions.

- Recovered durable thread history via t3_thread_read and read current DESIGN/PROGRESS/SCOPE plus source files.
  Existing worktree HEAD 5b55e3aa8, branch bot/levels. No changes in other worktrees.
- Liveness (09:03–09:04 UTC): `ssh 127x01 'ps -u sdicks02 -o pid=,ppid=,etime=,pcpu=,args= | grep -E "bot.levels|configs-build|bot-levels|probe.py" | grep -v grep'`.
  Existing config build parent 2918000, lease wrapper 2918006, exporter 2918593,
  command `cpu_job.sh 1 nice $PY -m bot.levels.configs --levels 11,5` remains alive.
  `tail -c 1500 /mpac/sdicks02/jobs/clasher/bot-levels/dev/configs-build1.txt` on 01:
  L11 121 cards, 0 errors, 352 CPU seconds; L5 ongoing. No duplicate launched.
- Liveness: `ssh 127x03 'ps -u sdicks02 -o pid=,ppid=,etime=,pcpu=,args= | grep -E "bot-levels|probe.py" | grep -v grep'`.
  Deferred probe timeout PID46360/wrapper46361 still queued; original timeout is 30 minutes.
- Existing harness task recovered via task_status:
  `node:delegated-task:command%3Amcp%3A529e902e-53e4-463b-833d-26ef111d2c40%3Adelegate-task%3Abot-levels-harness-sol-r1`.
  It was already active (no stopped helper to restart). Sent current Sam routing to same child.
  `ssh 127x01 'cat /mpac/sdicks02/jobs/clasher/bot-levels/harness-dev/audit.json'`:
  DEV base1, 4 cases twice; 4/4 command hashes match, all A wins, zero errors/rejections/failures;
  smoke1 96.36 CPU s/game and 98.58 wall s/game; smoke2 97.32 CPU s/game and 99.50 wall s/game.
  These are harness diagnostics, not pilot results. Worker reported pytest 4 passed in 0.40 s.
- Fresh independent Sol high read-only review started:
  `node:delegated-task:command%3Amcp%3A16f055f2-eb2e-4de8-811b-8f2250362499%3Adelegate-task%3Abot-levels-review-sol-r1-20261016`.
  Scope all bot/levels code and minimal hooks; explicitly review run.sh before any more use.
  Review output: jobs/clasher/bot-levels/review-sol-r1.md.
- Parent notified via t3_thread_send, request levels-resume-status-20261016-0904; parent acknowledged.
- Source audit concern: forced all11 B still uses fixed median5 opponent estimate in player.py; parity
  needs an explicit diagnostic-only all11 estimate. Reviewer notified. No pilot bank drawn or games started.
- Deferred decisions for Opus: any profile/arm redesign, leaf metadata interpretation changes, confirmation
  run sizing/launch, runtime/model/strategy promotion. s27-m02 replay is offline diagnostic only.
- Files modified this resumption: this PROGRESS.md only so far. No commits, rollbacks, signals, account actions,
  runtime writes or new host jobs. Next: finish independent review, repair routine gate defects, run gates on01.

- 2026-10-16T09:07:03.537818+00:00 audit: harness worker completed; 4 tests, 8 games, 4/4 repeat hashes. Copied receipt with `mkdir -p reports/bot/levels/receipts` then `rsync -a 127x01:/mpac/sdicks02/jobs/clasher/bot-levels/harness-dev/audit.json reports/bot/levels/receipts/harness-dev-audit.json`; SHA256 1af0433ddcf729c3fe8d4292e0ef5956154e2be10ffa5bbf46044921ad8b4bdd. First rsync failed (missing destination directory); retry succeeded, no source changes.
- Bounded Astra high diagnostic requested for leaf_native metadata effects on scripted/learned features and Linux/Mac pool propagation. Task `node:delegated-task:command%3Amcp%3A16f055f2-eb2e-4de8-811b-8f2250362499%3Adelegate-task%3Abot-levels-leaf-astra-diagnostic-r1-20261016`; read-only, no code/design choice; output jobs/clasher/bot-levels/leaf-diagnostic-astra-r1.md.
- Deferred probe PID46360 no longer present on03 at09:06 UTC, with no probe logs: expired its original30min admission timeout before obtaining CPU room. No restart while03 is full; exact deferred command remains in SCOPE.md.

- 2026-10-16T09:08:01.919233+00:00 launcher review: run.sh NOT approved yet (host/worker cap and override validation absent). Reviewer explicitly allowed direct existing cpu_job.sh1 commands on01 for disjoint exports and towers gate; L11 cache publication verified before launch.

  Job towers local exec session 58016:

  ```bash
  ssh 127x01 'source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.gates towers > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-towers-r1.txt 2>&1'
  ```

  Job export4 local exec session 24379:

  ```bash
  ssh 127x01 'source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 30m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.configs --levels 4 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/configs-L4-r1.txt 2>&1'
  ```

  Job export6 local exec session 43599:

  ```bash
  ssh 127x01 'source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 30m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.configs --levels 6 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/configs-L6-r1.txt 2>&1'
  ```

  Job export7 local exec session 81817:

  ```bash
  ssh 127x01 'source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 30m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.configs --levels 7 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/configs-L7-r1.txt 2>&1'
  ```

  Job export9 local exec session 9945:

  ```bash
  ssh 127x01 'source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 30m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.configs --levels 9 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/configs-L9-r1.txt 2>&1'
  ```

  Existing11/5 exporter left untouched. New work <=5 slots through existing admission wrapper, one process each, nice10, GPU hidden; all01, bounded15/30min including admission. No pilot games.

- 2026-10-16T09:13:04.588232+00:00 material audit: original exporter completed. L11 121/0errors; L5 118/3errors (Clone/Earthquake/Tornado),342CPU s. check11 rawdict equality accepted3/rejected118 inclpilotcards. Parent notified request levels-material-export-mismatch-20261016-0910 and acknowledged HOLD before bank/game. Preserved original export/cache/log.
- Source-derived schema hypothesis: native exporter differential.entity.coord returns tuples (engine-rs/differential.py:292–293) for tunnel_origin/destination; diskJSON converts these tolists. Prior20card check compared in-memory objects before diskroundtrip. Routine patch configs.py compares sorted nativeJSON and versions supported.json against canonical reference hash, leaving all exports unchanged. gate_exports prints rawvscanonical counts and concrete tuple/list fields; runtime confirmation pending independentreview.
- Tower gate r1 failed after8towercurve passes: RoyaleSim catalogue key Archers raisesKeyError (canonicalname Archer). Patched gate to use existing royalesim_adapter.royalesim_card aliasmap. Log preserved dev/gates-towers-r1.txt on01.
- Owner routinefixes awaiting freshreview: player.py diagnostic-only constant11 opponent estimator/forcedroot/cacheinjection; root.py towerprojectiles preserve maxHP1 while applying towerdamage; root.py failsclosed when any playable/rootbody card lacks exactlevel export; gates.py checkedcasts+actualrawfc LearnedPooltransport (2CPUslots); configs.py JSONcomparison/cacheversion/defaultL9; regressionfixtures test_configs.py. Harnessworker implementing launcher/resume/all11/cachepreload fixes in its ownedfiles. No changes in frozenruntimes.
- Astra smallbounded diagnostic completed (sourceonly), receipt reports/bot/levels/receipts/leaf-diagnostic-astra-r1.md. Tower metadata adjustment is NOT leaf-only: affects native scripted crown lethality/Lightning targeting too. Learned featurevector remains equal foridenticalstate; candidates/fallback directlyunchanged. Existing pooledworkers retainoldnative; fork/spawn recoverydiverges. Decisions on normalization/pooledlive adaptation remainparked forOpus. Defaultserial pilot itself has nopool.
- IndependentSol r1 completed; receipt reports/bot/levels/receipts/review-sol-r1.md. Pilot/launcher NOTREADY. No pilotbankdrawn; no realpilot games.

- 2026-10-16T09:14:33.515037+00:00 freshSol ownerfixreview task `node:delegated-task:command%3Amcp%3A16f055f2-eb2e-4de8-811b-8f2250362499%3Adelegate-task%3Abot-levels-review-sol-r2-ownerfixes-20261016` running; priorfindings/responses/unresolvedOpusissues included. Separatefromharnessworker; no duplicatedjobs. DESIGN/RESULTS updated tohold andbounded evidence.

- 2026-10-16T09:15:56.595102+00:00 ownerfixreview r2 quickverdict explicitly approves directwrapper1/nice01 schema/towers andconfigs tests only. Source synced with `rsync -a bot/levels/configs.py bot/levels/root.py bot/levels/player.py bot/levels/gates.py bot/levels/test_configs.py 127x01:/mpac/sdicks02/repos/clasher-bot-levels/bot/levels/`.

  Job schema-towers session 41004:

  ```bash
  ssh 127x01 'source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.gates exports towers > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-schema-towers-r2.txt 2>&1'
  ```

  Job pytest-configs session 99937:

  ```bash
  ssh 127x01 'source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh; cd "$REPO"; timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -m pytest -q -p no:cacheprovider bot/levels/test_configs.py > /mpac/sdicks02/jobs/clasher/bot-levels/dev/pytest-configs-r2.txt 2>&1'
  ```

## Updated decision and coordination rules — 2026-10-16T09:21:32.833035+00:00

Sam: make obvious decisions. This supersedes the blanket hold on major choices. Confident, reversible changes within authority may proceed after meaningful checks, required reviews, and a concrete rollback. Defer only consequential, hard-to-undo AND sufficiently uncertain choices where Opus could materially alter the approach. No Claude retries.

Parent accepted the minimal serial A/B/B0 experiment and lifted the mapping hold: canonical native JSON 121/121, 13 tower checks, and 2 regression tests pass. B tower metadata affects both leaf normalization and scripted crown spell lethality/Lightning; identical-state learned feature invariance is limited to that layer. No pooled LIVE claim/deployment. Rollback selects A/removes level root/native hook; frozen runtimes, pins and models remain untouched. Mandatory remaining gates still block bank/games.

Coordination: questions/missing information/constraints go DIRECT by t3_thread_send(mode=auto) to immediate BOT parent thread thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-bot-lead-20261014-r1. Include question, evidence/paths, recommendation and whether dependent work waits; continue independent work. No user-input tools. Coordinator 0523ae6f-baa3-4d4e-b233-b392671670db remains above BOT parent. Actual permission controls unchanged. No pending old user-input requests. Rule sent to active harness owner in new bounded provenance/completeness follow-up; completed reviewers not revived for acknowledgement.

- Existing independent launcher review r3 used the CORRECT worktree; wrong brief suffix levels05 was disclosed and corrected. No duplicate review solely for path correction. Conditional DEV launcher approval after harness tests; pilot provenance/completeness defects still being repaired.
- Schema/tower command completed successfully on01; 121/121 canonical configs, concrete tuple/list field evidence, 13 tower checks, fails[]. Tests2 passed0.19s. Receipts copied under reports/bot/levels/receipts/; original exporter logs preserved including pre-fix check output.
- Unsupported scope audit: 0/54 projected true-game rows affected, but 425/2925 belief decks and 15371/69380 prior frequency (22.1548%) contain Clone/Earthquake/Tornado. Proposed fixed identical prior restriction for every arm before any bank/outcome; parent notified. Scope-audit-r1.json records exact counts and catalog hash. No outcome-dependent exclusions.

- 2026-10-16T09:25:51.451609+00:00 BOT LEAD accepted common supported-card scope before bank/outcomes. Implemented scope.py/install and test_scope.py, bank.py original-catalog projection plus restricted equality assertions, factory installs common scope before every experimental arm. Preserves original prior; no standard player outside pilot changed. Root now fails closed for unmapped producers or missing body template rather than silently retaining L11. Fresh review/runtime fixtures pending. DESIGN updated with accepted serial semantics, exact scope mass, rollback and remaining gates.
- Active owners: harness provenance/completeness worker owns run.py/test_harness.py/report.py; gate fixture worker owns gates.py. Coordination rule and updated Sam decision rule propagated in both briefs/messages. No other active descendants.

- 2026-10-16T09:26:07.950341+00:00 verified no existing deferred probe on03 (107 live Python processes). Requeued original SCOPE N=4 command once, with nice10 outside original timeout/wrapper; full-pool priority remains enforced by admission. Exact command:

```bash
ssh 127x03 'nice -n 10 timeout --kill-after=10s 30m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4 bash /mpac/sdicks02/jobs/clasher/bot-levels/run_all.sh'
```

No duplicate probe. Admission/execution bounded30min; if it expires again, record deferral, do not spin-retry.

- 2026-10-16T09:29:37.436374+00:00 isolated worktree refreshed with `git fetch -q origin; git merge --ff-only origin/main`: HEAD 5b55e3aa8 → bd3eec30d. Only two owned tracked hooks remained modified; their diff versus origin/main stayed exactly17 additions/5 deletions. No frozen runtime touched.
- Completed exec sessions: exports4/6/7/9, schema/towers and regression tests all returned0. Original failed tower session returned1 and is preserved. 01 has no remaining owned level jobs. Deferred03 retry session47270 holds timeout PID287537/wrapper287538, admission only.
